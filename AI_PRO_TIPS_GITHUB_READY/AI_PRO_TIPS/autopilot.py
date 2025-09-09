import random
from datetime import date
from config import Config
from util import now_tz, in_quiet_hours, time_in_range
from templates import (
    render_banter_line, render_stat_flash, render_progress_bar,
    render_story_headline, render_value_scanner
)
from telegram_client import TelegramClient
from repo import emit_count, emit_mark, create_betslip, add_selection
from costruttori import build_safe_combo_for_date
from api_football import APIFootball

class Autopilot:
    def __init__(self, cfg: Config, tg: TelegramClient, api: APIFootball):
        self.cfg = cfg
        self.tg = tg
        self.api = api

    def _pending_counts(self, today: date):
        return {
            "stat_flash": self.cfg.DAILY_COUNTS["stat_flash"] - emit_count("stat_flash", today),
            "banter":     self.cfg.DAILY_COUNTS["banter"]     - emit_count("banter", today),
            "value_scan": self.cfg.DAILY_COUNTS["value_scan"] - emit_count("value_scan", today),
            "story":      self.cfg.DAILY_COUNTS["story"]      - emit_count("story", today),
            "parlays_left": len(self.cfg.DAILY_COUNTS["parlays"]) - emit_count("parlay", today),
        }

    def _current_slot(self, now):
        for name, (a,b) in self.cfg.SLOTS.items():
            if time_in_range(now, a, b):
                return name
        return "none"

    def run_once(self):
        now = now_tz(self.cfg.TZ)
        if in_quiet_hours(now, self.cfg.QUIET_HOURS):
            return
        pending = self._pending_counts(now.date())
        slot = self._current_slot(now)

        if pending["stat_flash"] > 0 and slot in ("morning","lunch"):
            self.post_stat_flash(); emit_mark("stat_flash", now); return
        if pending["value_scan"] > 0 and slot in ("morning","lunch"):
            self.post_value_scan(); emit_mark("value_scan", now); return
        if pending["story"] > 0 and slot in ("afternoon","evening"):
            self.post_story(); emit_mark("story", now); return
        if pending["parlays_left"] > 0 and slot in ("afternoon","evening"):
            idx = emit_count("parlay", now.date())
            plan = self.cfg.DAILY_COUNTS["parlays"][idx]
            legs = plan["legs"]
            if self.post_parlay(legs):
                emit_mark("parlay", now)
                return
        if pending["banter"] > 0:
            self.post_banter(); emit_mark("banter", now); return

    def post_banter(self):
        self.tg.send_message(render_banter_line())

    def post_stat_flash(self):
        today = now_tz(self.cfg.TZ).strftime("%Y-%m-%d")
        fixtures = self.api.fixtures_by_date(today)
        if not fixtures:
            return
        fx = random.choice(fixtures)
        home = fx.get("teams",{}).get("home",{}).get("name","Home")
        away = fx.get("teams",{}).get("away",{}).get("name","Away")
        stat = f"Negli ultimi 8, {home} ha segnato in 6 partite. {home}–{away} oggi può sbloccarsi presto."
        self.tg.send_message(render_stat_flash(stat))

    def post_value_scan(self):
        today = now_tz(self.cfg.TZ).strftime("%Y-%m-%d")
        fixtures = self.api.fixtures_by_date(today)
        if not fixtures:
            return
        random.shuffle(fixtures)
        for fx in fixtures:
            fid = fx.get("fixture",{}).get("id")
            if not fid: 
                continue
            try:
                odds = self.api.odds_by_fixture(fid)
            except Exception:
                continue
            mk = self.api.parse_markets(odds)
            for m in ("Under 3.5","1X","Over 0.5"):
                if m in mk and 1.25 <= mk[m] <= 1.40:
                    home = fx.get("teams",{}).get("home",{}).get("name","Home")
                    away = fx.get("teams",{}).get("away",{}).get("name","Away")
                    note = "Quota stabile e coerente con mismatch."
                    self.tg.send_message(render_value_scanner(f"{home}–{away}", m, mk[m], note))
                    return

    def post_story(self):
        title = "Il leone contro la preda"
        body  = "Oggi scegliamo il colpo facile: solidi e rumorosi. 😉"
        self.tg.send_message(render_story_headline(title, body))

    def post_parlay(self, legs: int) -> bool:
        today = now_tz(self.cfg.TZ).strftime("%Y-%m-%d")
        combo = build_safe_combo_for_date(self.api, today, legs, self.cfg.LEG_ODDS_MIN, self.cfg.LEG_ODDS_MAX)
        if not combo:
            return False
        total_odds = 1.0
        for c in combo:
            total_odds *= float(c["odds"])
        code = now_tz(self.cfg.TZ).strftime("%d%H%M") + "-" + str(random.randint(100,999))
        bid = create_betslip(code, round(total_odds,2), len(combo))
        for c in combo:
            dt = c["start_time"]
            dt = dt[:19]
            add_selection(bid, c["fixture_id"], c["league_id"], dt, c["home"], c["away"], c["market"], c["pick"], c["odds"])
        header = {1:"🎯 Singola Safe",2:"🧩 Doppia Safe",3:"🚀 Tripla Safe",4:"🚀 Quadrupla Safe",6:"🚀 Super Combo (x6)"}.get(legs, f"🚀 Multipla x{legs} Safe")
        self.tg.send_message(f"{header} (#{code})\nQuota totale: <b>{round(total_odds,2):.2f}</b>")
        self.tg.send_message(render_progress_bar(0, legs))
        return True
