import json
import random
from datetime import date
from zoneinfo import ZoneInfo

from .config import Config
from .util import now_tz, parse_dt, short_id5
from .telegram_client import TelegramClient
from .api_football import APIFootball
from .templates import render_value_single, render_multipla, render_stat_flash, render_story_long
from .builders import (
    fixtures_allowed_today,
    build_value_single,
    build_combo_with_range,
    calc_send_at_for_combo,
)
from .repo import (
    kv_get, kv_set,
    create_betslip, add_selection,
    schedule_enqueue, schedule_due_now, schedule_mark_sent,
)


class Autopilot:
    """
    Responsabilità:
    - Alle 08:00 locali genera il piano del giorno (con dedup e degrado) e mette in coda i messaggi (HTML già renderizzati).
    - Durante la giornata processa la coda (invia tutto ciò che è scaduto).
    - Espone metodi che i comandi admin possono usare (/preview, /gen, ecc.).
    """

    def __init__(self, cfg: Config, tg: TelegramClient, api: APIFootball):
        self.cfg = cfg
        self.tg = tg
        self.api = api

    # -----------------------
    # Chiavi KV per pools/marker
    # -----------------------
    def _planned_key(self) -> str:
        # Per evitare rigenerazioni multiple nello stesso giorno
        return "planned_" + now_tz(self.cfg.TZ).strftime("%Y%m%d")

    def _story_key(self) -> str:
        # Per storytelling coerente ai match generati
        return "story_pool_" + now_tz(self.cfg.TZ).strftime("%Y%m%d")

    def _picks_key(self) -> str:
        # Per statistiche coerenti ai pick generati
        return "picks_pool_" + now_tz(self.cfg.TZ).strftime("%Y%m%d")

    # -----------------------
    # Planner (genera e accoda)
    # -----------------------
    def run_daily_planner(self, *, force: bool = False) -> int:
        """
        Genera tutte le schedine del giorno e accoda i messaggi da inviare.
        Ritorna il numero di schedine pianificate.
        """
        now_local = now_tz(self.cfg.TZ)
        # Esegui solo dopo le quiet hours, a partire dalle 08:00 locali
        if now_local.hour < self.cfg.QUIET_HOURS[1] and not force:
            return 0

        # Evita doppia pianificazione nello stesso giorno salvo force=True
        if (kv_get(self._planned_key()) and not force):
            return 0

        planned_ids: list[str] = []
        used_fixtures: set[int] = set()
        today = now_local.strftime("%Y-%m-%d")

        # 1) Singole value
        value_needed = int(self.cfg.DAILY_PLAN["value_singles"])
        for _ in range(value_needed):
            single = build_value_single(self.api, today, self.cfg, used_fixtures)
            if not single:
                continue

            # Crea betslip + selection
            short_id = short_id5()
            code = now_local.strftime("%d%H%M") + "-" + str(random.randint(100, 999))
            bid = create_betslip(code, round(float(single["odds"]), 2), 1, short_id)
            add_selection(
                bid,
                single["fixture_id"],
                single["league_id"],
                (single["start_time"] or "")[:19],
                single["home"],
                single["away"],
                single["market"],
                single["pick"],
                float(single["odds"]),
            )

            # Aggiorna pools (story/picks)
            self._story_add_match(single["home"], single["away"])
            self._picks_add(single["home"], single["away"], single["market"], single["fixture_id"])

            # Renderizza messaggio finale e calcola send_at (T-3h >= 08:00 locali)
            msg_html = render_value_single(
                single["home"],
                single["away"],
                single["market"],
                float(single["odds"]),
                single["kickoff_local"],
                link="https://t.me/AIProTips",
            )
            send_at_utc = calc_send_at_for_combo([single], self.cfg.TZ)
            schedule_enqueue(short_id, "value", msg_html, send_at_utc.strftime("%Y-%m-%d %H:%M:%S"))
            planned_ids.append(short_id)

        # 2) Combos secondo piano (con degrado interno)
        for spec in self.cfg.DAILY_PLAN["combos"]:
            legs = spec["legs"]
            if isinstance(legs, str) and legs == "8-12":
                legs = random.randint(8, 12)

            combo = build_combo_with_range(self.api, today, legs, float(spec["leg_lo"]), float(spec["leg_hi"]), self.cfg, used_fixtures)
            if not combo:
                # non forziamo; degrade già fatto: se <2 leg, viene []
                continue

            # Calcolo total odds e costruzione betslip
            total_odds = 1.0
            legs_block = []
            for c in combo:
                total_odds *= float(c["odds"])
                legs_block.append({"home": c["home"], "away": c["away"], "pick": c["market"], "odds": float(c["odds"])})

            short_id = short_id5()
            code = now_local.strftime("%d%H%M") + "-" + str(random.randint(100, 999))
            bid = create_betslip(code, round(total_odds, 2), len(combo), short_id)
            for c in combo:
                add_selection(
                    bid,
                    c["fixture_id"],
                    c["league_id"],
                    (c["start_time"] or "")[:19],
                    c["home"],
                    c["away"],
                    c["market"],
                    c["pick"],
                    float(c["odds"]),
                )
                self._story_add_match(c["home"], c["away"])
                self._picks_add(c["home"], c["away"], c["market"], c["fixture_id"])

            # Messaggio finale + T-3h
            kickoff_local = combo[0]["kickoff_local"]
            msg_html = render_multipla(
                legs_block,
                float(total_odds),
                kickoff_local,
                link="https://t.me/AIProTips",
            )
            send_at_utc = calc_send_at_for_combo(combo, self.cfg.TZ)
            schedule_enqueue(short_id, "combo", msg_html, send_at_utc.strftime("%Y-%m-%d %H:%M:%S"))
            planned_ids.append(short_id)

        # Marca “pianificato oggi” e notifica admin
        kv_set(self._planned_key(), json.dumps(planned_ids, ensure_ascii=False))
        if planned_ids:
            self.tg.notify_admin(f"Planner 08:00: generate & enqueue {len(planned_ids)} schedine.")
        else:
            self.tg.notify_admin("Planner 08:00: nessuna schedina generata (pochi match idonei).")
        return len(planned_ids)

    # -----------------------
    # Scheduler (pubblica ciò che è scaduto)
    # -----------------------
    def process_scheduled_queue(self) -> int:
        """
        Invia i messaggi in coda con send_at <= NOW().
        Ritorna quanti messaggi ha inviato in questo giro.
        """
        due = schedule_due_now(limit=10)
        count = 0
        for rec in due:
            try:
                self.tg.send_message(rec["payload"])
                schedule_mark_sent(rec["id"])
                count += 1
            except Exception as e:
                # Lascia QUEUED: retry al prossimo giro, e logga
                from .repo import log_error
                log_error("scheduler_send", f"{e}")
        return count

    # -----------------------
    # Pool helpers (story/stat)
    # -----------------------
    def _story_add_match(self, home: str, away: str):
        key = self._story_key()
        try:
            arr = json.loads(kv_get(key) or "[]")
        except Exception:
            arr = []
        pair = f"{home}–{away}"
        if pair not in arr:
            arr.append(pair)
            kv_set(key, json.dumps(arr, ensure_ascii=False))

    def _picks_add(self, home: str, away: str, pick: str, fixture_id: int):
        key = self._picks_key()
        try:
            arr = json.loads(kv_get(key) or "[]")
        except Exception:
            arr = []
        arr.append({"home": home, "away": away, "pick": pick, "fixture_id": int(fixture_id)})
        kv_set(key, json.dumps(arr, ensure_ascii=False))

    # -----------------------
    # Extra (facoltativi, usati dai comandi admin)
    # -----------------------
    def post_stat_flash(self):
        """
        Sceglie una delle partite nei picks_pool del giorno e genera una statistica coerente col pick.
        """
        # prova dal pool
        try:
            arr = json.loads(kv_get(self._picks_key()) or "[]")
        except Exception:
            arr = []
        if not arr:
            return
        pick_rec = random.choice(arr)
        fx = self.api.fixture_by_id(pick_rec.get("fixture_id", 0))
        if not fx:
            return
        try:
            from .stats import craft_coherent_stat_line
            line = craft_coherent_stat_line(self.api, fx, pick_rec.get("pick", ""))
        except Exception:
            line = None
        if line:
            self.tg.send_message(render_stat_flash(pick_rec.get("home", "Home"), pick_rec.get("away", "Away"), line_override=line))

    def post_story(self):
        """
        Sceglie un match dallo story_pool giornaliero e pubblica storytelling lungo (3–4 frasi).
        """
        try:
            arr = json.loads(kv_get(self._story_key()) or "[]")
        except Exception:
            arr = []
        if not arr:
            return
        pick = random.choice(arr)
        if "–" in pick:
            home, away = pick.split("–", 1)
        else:
            home, away = pick, ""
        self.tg.send_message(render_story_long(home, away))

    # -----------------------
    # Tick principale (chiamato dal thread autopilot)
    # -----------------------
    def run_once(self):
        """
        - Esegue il planner (una sola volta al giorno, dopo le 08:00).
        - Processa la coda e invia ciò che è scaduto.
        - Gli extra (stat/story/banter) sono gestiti dai comandi admin o da una futura logica di slot.
        """
        # 1) Pianifica se non già fatto
        self.run_daily_planner()

        # 2) Invia ciò che è pronto
        self.process_scheduled_queue()
