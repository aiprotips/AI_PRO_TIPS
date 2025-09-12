import json, random
from .config import Config
from .util import now_tz, short_id5
from .telegram_client import TelegramClient
from .api_football import APIFootball
from .templates import render_value_single, render_multipla, render_stat_flash, render_story_long
from .builders import fixtures_allowed_today, build_value_single, build_combo_with_range, calc_send_at_for_combo
from .repo import kv_get, kv_set, create_betslip, add_selection, schedule_enqueue

class Autopilot:
    def __init__(self, cfg: Config, tg: TelegramClient, api: APIFootball):
        self.cfg = cfg; self.tg = tg; self.api = api

    def _planned_key(self) -> str: return "planned_" + now_tz(self.cfg.TZ).strftime("%Y%m%d")
    def _story_key(self) -> str:   return "story_pool_" + now_tz(self.cfg.TZ).strftime("%Y%m%d")
    def _picks_key(self) -> str:   return "picks_pool_" + now_tz(self.cfg.TZ).strftime("%Y%m%d")

    # --- pool di supporto per storytelling/statistiche coerenti
    def _story_add_match(self, home: str, away: str):
        key=self._story_key()
        try: arr=json.loads(kv_get(key) or "[]")
        except Exception: arr=[]
        pair=f"{home}–{away}"
        if pair not in arr:
            arr.append(pair); kv_set(key, json.dumps(arr, ensure_ascii=False))

    def _picks_add(self, home: str, away: str, pick: str, fixture_id: int):
        key=self._picks_key()
        try: arr=json.loads(kv_get(key) or "[]")
        except Exception: arr=[]
        arr.append({"home":home, "away":away, "pick":pick, "fixture_id":int(fixture_id)})
        kv_set(key, json.dumps(arr, ensure_ascii=False))

    # --- contenuti random “hype”
    def post_stat_flash(self):
        try:
            from .stats import craft_coherent_stat_line
            today = now_tz(self.cfg.TZ).strftime("%Y-%m-%d")
            fixtures = fixtures_allowed_today(self.api, today, self.cfg)
            if not fixtures: return
            fx = random.choice(fixtures)
            home = (fx.get("teams",{}) or {}).get("home",{}).get("name","Home")
            away = (fx.get("teams",{}) or {}).get("away",{}).get("name","Away")
            line = craft_coherent_stat_line(self.api, fx, "1X")  # safe default
            self.tg.send_message(render_stat_flash(home, away, line_override=line))
        except Exception:
            pass

    def post_story(self):
        try: arr=json.loads(kv_get(self._story_key()) or "[]")
        except Exception: arr=[]
        if not arr: return
        pick=random.choice(arr); home,away=(pick.split("–",1)+[""])[:2] if "–" in pick else (pick,"")
        self.tg.send_message(render_story_long(home, away))

    # --- pianifica alle 08:00 le giocate del giorno con invio a T-3h dal primo kickoff
    def run_daily_planner(self, *, force: bool=False) -> int:
        now_local = now_tz(self.cfg.TZ)
        if now_local.hour < self.cfg.QUIET_HOURS[1] and not force: return 0
        if (kv_get(self._planned_key()) and not force): return 0

        planned_ids = []
        used_fixtures=set()
        today = now_local.strftime("%Y-%m-%d")

        # 1) value singles (payload JSON)
        for _ in range(int(self.cfg.DAILY_PLAN["value_singles"])):
            single = build_value_single(self.api, today, self.cfg, used_fixtures)
            if not single: continue
            short_id = short_id5()
            code = now_local.strftime("%d%H%M") + "-" + str(random.randint(100,999))
            bid = create_betslip(code, round(float(single["odds"]),2), 1, short_id)
            add_selection(bid, single["fixture_id"], single["league_id"], single["start_time"][:19],
                          single["home"], single["away"], single["market"], single["pick"], float(single["odds"]))
            self._story_add_match(single["home"], single["away"])
            self._picks_add(single["home"], single["away"], single["market"], single["fixture_id"])

            send_at_utc = calc_send_at_for_combo([single], self.cfg.TZ)
            payload_json = json.dumps({"type":"value","selection": single}, ensure_ascii=False)
            schedule_enqueue(short_id, "value", payload_json, send_at_utc.strftime("%Y-%m-%d %H:%M:%S"))
            planned_ids.append(short_id)

        # 2) combos (payload JSON)
        for spec in self.cfg.DAILY_PLAN["combos"]:
            legs = spec["legs"]
            if isinstance(legs,str) and legs=="8-12": legs = random.randint(8,12)
            combo = build_combo_with_range(self.api, today, legs, float(spec["leg_lo"]), float(spec["leg_hi"]), self.cfg, used_fixtures)
            if not combo: continue

            total=1.0
            for c in combo: total*=float(c["odds"])

            short_id = short_id5()
            code = now_local.strftime("%d%H%M") + "-" + str(random.randint(100,999))
            bid = create_betslip(code, round(total,2), len(combo), short_id)
            for c in combo:
                add_selection(bid, c["fixture_id"], c["league_id"], c["start_time"][:19],
                              c["home"], c["away"], c["market"], c["pick"], float(c["odds"]))
                self._story_add_match(c["home"], c["away"])
                self._picks_add(c["home"], c["away"], c["market"], c["fixture_id"])

            send_at_utc = calc_send_at_for_combo(combo, self.cfg.TZ)
            payload_json = json.dumps({"type":"combo","selections": combo}, ensure_ascii=False)
            schedule_enqueue(short_id, "combo", payload_json, send_at_utc.strftime("%Y-%m-%d %H:%M:%S"))
            planned_ids.append(short_id)

        # segno che ho pianificato oggi
        kv_set(self._planned_key(), json.dumps(planned_ids, ensure_ascii=False))
        return len(planned_ids)

    def run_once(self):
        # pianifica (alle 08:00 local o su /gen force) — l’invio lo fa SOLO il sender
        self.run_daily_planner()
