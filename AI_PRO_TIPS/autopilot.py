import random, json
from datetime import date, timedelta
from config import Config
from util import now_tz, in_quiet_hours, time_in_range, parse_dt  # <-- aggiunto parse_dt
from templates import (
    render_banter_line, render_stat_flash_phrase, render_progress_bar,
    render_story_for_match, render_value_scanner, render_stat_flash  # <-- aggiunto render_stat_flash per override
)
from telegram_client import TelegramClient
from repo import emit_count, emit_mark, create_betslip, add_selection, kv_get, kv_set
from builders import build_combo_with_range, build_value_single
from api_football import APIFootball

class Autopilot:
    def __init__(self, cfg: Config, tg: TelegramClient, api: APIFootball):
        self.cfg = cfg
        self.tg = tg
        self.api = api

    def _pending_counts(self, today: date):
        rc = self.cfg.DAILY_PLAN["random_content"]
        return {
            "value_single": self.cfg.DAILY_PLAN["value_singles"] - emit_count("value_single", today),
            "combo":        len(self.cfg.DAILY_PLAN["combos"])    - emit_count("combo", today),
            "stat_flash":   rc["stat_flash_per_day"]              - emit_count("stat_flash", today),
            "banter":       rc["banter_per_day"]                  - emit_count("banter", today),
            "story":        rc["story_per_day"]                   - emit_count("story", today),
        }

    def _current_slot(self, now):
        for name, (a,b) in self.cfg.SLOTS.items():
            if time_in_range(now, a, b): return name
        return "none"

    def _today_str(self):
        return now_tz(self.cfg.TZ).strftime("%Y-%m-%d")

    # ---- STORY POOL (per agganciare storytelling alle giocate del giorno)
    def _story_key(self): return "story_pool_" + now_tz(self.cfg.TZ).strftime("%Y%m%d")
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

    # ---- PICKS POOL (per statistiche coerenti con i pick)  <-- AGGIUNTA
    def _picks_key(self): return "picks_pool_" + now_tz(self.cfg.TZ).strftime("%Y%m%d")

    def _picks_add(self, home: str, away: str, pick: str, fixture_id: int):  # <-- AGGIUNTA
        key = self._picks_key()
        try:
            arr = json.loads(kv_get(key) or "[]")
        except Exception:
            arr = []
        arr.append({"home": home, "away": away, "pick": pick, "fixture_id": int(fixture_id)})
        kv_set(key, json.dumps(arr, ensure_ascii=False))

    # ---- FINESTRA DI INVIO Giocate: 3h prima del primo kickoff del giorno  <-- AGGIUNTA
    def _first_kickoff_dt(self):
        """Ritorna il datetime (tz locale) del primo kickoff tra i fixture whitelisted di oggi, oppure None."""
        today = self._today_str()
        try:
            from builders import fixtures_allowed_today
            fixtures = fixtures_allowed_today(self.api, today, self.cfg)
        except Exception:
            fixtures = []
        tz_now = now_tz(self.cfg.TZ).tzinfo
        first_dt = None
        for fx in fixtures:
            iso = (fx.get("fixture",{}) or {}).get("date")
            dt = parse_dt(iso)
            if not dt:
                continue
            # normalizza a tz locale
            try:
                dt = dt.astimezone(tz_now)
            except Exception:
                pass
            if first_dt is None or dt < first_dt:
                first_dt = dt
        return first_dt

    def _quiet_end_today(self):
        """Ritorna il datetime (oggi) dell'uscita dalle quiet hours (es. 08:00)."""
        now = now_tz(self.cfg.TZ)
        q_start, q_end = self.cfg.QUIET_HOURS  # es. (0,8)
        return now.replace(hour=q_end, minute=0, second=0, microsecond=0)

    def _can_emit_bets_now(self):
        """
        True se siamo nella finestra per inviare le GIOCATE:
        - adesso >= (primo_kickoff - 3h), con rispetto quiet hours (se la finestra cade prima di fine quiet -> inizia a fine quiet)
        """
        now = now_tz(self.cfg.TZ)
        fk = self._first_kickoff_dt()
        if not fk:
            return True  # nessun fixture oggi: non bloccare per non paralizzare (giocherà fallback)
        threshold = fk - timedelta(hours=3)
        # rispetta quiet hours: se la soglia è prima della fine-quiet, apri alla fine-quiet
        quiet_end = self._quiet_end_today()
        if threshold < quiet_end:
            threshold = quiet_end
        return now >= threshold

    # ---- Preview/Skip support (per comandi privati)  <-- AGGIUNTA
    def preview_window(self):
        """Restituisce info su primo kickoff e orario da cui partire con le giocate."""
        fk = self._first_kickoff_dt()
        if not fk:
            return {"has_fixtures": False}
        thr = fk - timedelta(hours=3)
        qend = self._quiet_end_today()
        if thr < qend:
            thr = qend
        return {"has_fixtures": True, "first_kickoff": fk, "send_from": thr}

    def _skip_key(self):
        return "skip_next_" + now_tz(self.cfg.TZ).strftime("%Y%m%d")

    def set_skip_next(self, kind: str):
        """kind: 'value' | 'combo'"""
        try:
            data = json.loads(kv_get(self._skip_key()) or "{}")
        except Exception:
            data = {}
        if kind in ("value","combo"):
            data[kind] = True
        kv_set(self._skip_key(), json.dumps(data, ensure_ascii=False))

    def _should_skip(self, kind: str) -> bool:
        try:
            data = json.loads(kv_get(self._skip_key()) or "{}")
        except Exception:
            data = {}
        flag = bool(data.get(kind))
        if flag:
            data[kind] = False  # consumiamo lo skip one-shot
            kv_set(self._skip_key(), json.dumps(data, ensure_ascii=False))
        return flag

    # ---- Emitters ----
    def post_banter(self):
        self.tg.send_message(render_banter_line())

    def post_stat_flash(self):  # <-- MODIFICATA per mapping pick->stat coerente
        # 1) prova a pescare dal picks pool del giorno e genera una frase coerente col pick
        try:
            arr = json.loads(kv_get(self._picks_key()) or "[]")
        except Exception:
            arr = []

        if arr:
            pick_rec = random.choice(arr)
            fx = self.api.fixture_by_id(pick_rec.get("fixture_id", 0))
            if fx:
                try:
                    from stats import craft_coherent_stat_line
                    line = craft_coherent_stat_line(self.api, fx, pick_rec.get("pick", ""))
                except Exception:
                    line = None
                if line:
                    # usa render_stat_flash con override esplicito
                    self.tg.send_message(render_stat_flash(pick_rec.get("home","Home"), pick_rec.get("away","Away"), line_override=line))
                    return

        # 2) fallback: come prima, random su fixture whitelisted e frase generica
        today = self._today_str()
        try:
            from builders import fixtures_allowed_today
            fixtures = fixtures_allowed_today(self.api, today, self.cfg)
        except Exception:
            fixtures = []
        if not fixtures: return
        fx = random.choice(fixtures)
        home = fx.get("teams",{}).get("home",{}).get("name","Home")
        away = fx.get("teams",{}).get("away",{}).get("name","Away")
        self.tg.send_message(render_stat_flash_phrase(home, away))

    def post_story(self):
        # prova a pescare da story pool; altrimenti prendi un match del giorno
        try:
            arr = json.loads(kv_get(self._story_key()) or "[]")
        except Exception:
            arr = []
        if arr:
            pick = random.choice(arr)
            if "–" in pick:
                home, away = pick.split("–", 1)
            else:
                home, away = pick, ""
        else:
            today = self._today_str()
            from builders import fixtures_allowed_today
            fixtures = fixtures_allowed_today(self.api, today, self.cfg)
            if not fixtures: return
            fx = random.choice(fixtures)
            home = fx.get("teams",{}).get("home",{}).get("name","Home")
            away = fx.get("teams",{}).get("away",{}).get("name","Away")
        self.tg.send_message(render_story_for_match(home, away))

    def post_value_single(self) -> bool:  # <-- MODIFICATA per salvare nel picks pool
        today = self._today_str()
        single = build_value_single(self.api, today, self.cfg)
        if not single: return False
        match_str = f"{single['home']}–{single['away']}"
        self.tg.send_message(render_value_scanner(match_str, single["market"], single["odds"], "Value pick (singola)"))
        # Traccia come betslip (1-leg). Niente progress bar.
        code = now_tz(self.cfg.TZ).strftime("%d%H%M") + "-" + str(random.randint(100,999))
        bid = create_betslip(code, round(single["odds"],2), 1)
        dt = single["start_time"][:19]
        add_selection(bid, single["fixture_id"], single["league_id"], dt, single["home"], single["away"], single["market"], single["pick"], single["odds"])
        # Story & Picks pool
        self._story_add_match(single["home"], single["away"])
        self._picks_add(single["home"], single["away"], single["market"], single["fixture_id"])  # <-- AGGIUNTA
        return True

    def post_combo_range(self, legs: int, lo: float, hi: float, label: str) -> bool:  # <-- MODIFICATA per salvare nel picks pool
        today = self._today_str()
        combo = build_combo_with_range(self.api, today, legs, lo, hi, self.cfg)
        if not combo: return False
        total_odds = 1.0
        for c in combo: total_odds *= float(c["odds"])
        code = now_tz(self.cfg.TZ).strftime("%d%H%M") + "-" + str(random.randint(100,999))
        bid = create_betslip(code, round(total_odds,2), len(combo))
        for c in combo:
            dt = c["start_time"][:19]
            add_selection(bid, c["fixture_id"], c["league_id"], dt, c["home"], c["away"], c["market"], c["pick"], c["odds"])
            self._story_add_match(c["home"], c["away"])
            self._picks_add(c["home"], c["away"], c["market"], c["fixture_id"])  # <-- AGGIUNTA
        self.tg.send_message(f"{label} (#{code})\nQuota totale: <b>{round(total_odds,2):.2f}</b>")
        if legs > 1:
            self.tg.send_message(render_progress_bar(0, legs))
        return True

    # ---- Scheduler principale ----
    def run_once(self):
        now = now_tz(self.cfg.TZ)
        if in_quiet_hours(now, self.cfg.QUIET_HOURS): return
        slot = self._current_slot(now)
        today = now.date()
        plan = self.cfg.DAILY_PLAN

        # GATE: giocate (value + multiple) solo da 3h prima del primo kickoff (rispettando quiet hours)  <-- AGGIUNTA
        can_emit_bets = self._can_emit_bets_now()

        # 1) Value singles (2/die), distribuite mattina/pomeriggio
        if can_emit_bets and emit_count("value_single", today) < plan["value_singles"] and slot in ("morning","afternoon","evening"):
            if not self._should_skip("value"):  # <-- AGGIUNTA (skip one-shot)
                if self.post_value_single():
                    emit_mark("value_single", now); return

        # 2) Multiple: doppia, tripla, quintupla, lunga (8–12)
        produced = emit_count("combo", today)
        combos = plan["combos"]
        if can_emit_bets and produced < len(combos) and slot in ("afternoon","evening"):
            if not self._should_skip("combo"):  # <-- AGGIUNTA (skip one-shot)
                c = combos[produced]
                legs = random.randint(8,12) if c["legs"] == "8-12" else c["legs"]
                label = {
                    2:"🧩 Doppia Safe", 3:"🚀 Tripla Safe", 4:"🚀 Quintupla Safe", 5:"🚀 Quintupla Safe"
                }.get(legs, f"🚀 Multipla x{legs} Safe")
                if self.post_combo_range(legs, c["leg_lo"], c["leg_hi"], label):
                    emit_mark("combo", now); return

        # 3) Random content (può uscire anche prima del gate giocate)
        rc = plan["random_content"]
        if emit_count("stat_flash", today) < rc["stat_flash_per_day"]:
            self.post_stat_flash(); emit_mark("stat_flash", now); return
        if emit_count("story", today) < rc["story_per_day"]:
            self.post_story(); emit_mark("story", now); return
        if emit_count("banter", today) < rc["banter_per_day"]:
            self.post_banter(); emit_mark("banter", now); return

        # altrimenti niente in questo tick
