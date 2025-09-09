from typing import Dict
from config import Config
from api_football import APIFootball
from telegram_client import TelegramClient
from repo import (
    get_open_betslips, get_selections_for_betslip, mark_selection_result,
    update_betslip_progress, close_betslip_if_done, cache_get_fixture, log_error
)
from templates import render_live_alert, render_progress_bar, render_celebration, render_quasi_vincente, render_cuori_spezzati

class LiveEngine:
    def __init__(self, cfg: Config, tg: TelegramClient, api: APIFootball):
        self.cfg = cfg
        self.tg = tg
        self.api = api
        self.sent_fav_under_alerts = set()  # fixture_id flagged

    def _is_favorite_losing_early(self, fx: Dict) -> bool:
        """Return True if pre-match favorite is currently losing by minute<=20"""
        info = fx.get("fixture",{})
        goals = fx.get("goals",{})
        fid = int(info.get("id"))
        minute = (info.get("status",{}) or {}).get("elapsed") or 0
        if not minute or minute > 20:
            return False
        cache = cache_get_fixture(fid)
        if not cache or not cache.get("odds_json"):
            return False
        try:
            import json
            mk = json.loads(cache["odds_json"])
        except Exception:
            return False
        # Determine favorite side using 1 or 1X markets; fallback: home as fav if 1 exists
        fav_side = None
        if "1" in mk:
            fav_side = "home"
        elif "1X" in mk:
            fav_side = "home"
        else:
            fav_side = "home"
        h = goals.get("home") or 0
        a = goals.get("away") or 0
        if fav_side == "home":
            return h < a
        else:
            return a < h

    def check_favorite_under_20(self):
        try:
            lives = self.api.live_fixtures()
        except Exception as e:
            log_error("live_fav", f"live_fixtures error: {e}")
            return
        for fx in lives:
            fid = int(fx.get("fixture",{}).get("id"))
            if fid in self.sent_fav_under_alerts:
                continue
            if self._is_favorite_losing_early(fx):
                home = fx.get("teams",{}).get("home",{}).get("name","Home")
                away = fx.get("teams",{}).get("away",{}).get("name","Away")
                goals = fx.get("goals",{})
                score = f"{goals.get('home',0)}–{goals.get('away',0)}"
                minute = (fx.get("fixture",{}).get("status",{}) or {}).get("elapsed") or 0
                self.tg.send_message(render_live_alert(f"La favorita è sotto al {minute}’: {home}–{away} {score}"))
                self.sent_fav_under_alerts.add(fid)

    def _resolve_market(self, market: str, goals_home: int, goals_away: int, status_short: str):
        total = (goals_home or 0) + (goals_away or 0)
        if market == "Over 0.5":
            return "WON" if total >= 1 else ("PENDING" if status_short not in ("FT","AET","PEN") else "LOST")
        if market == "Home to Score":
            return "WON" if (goals_home or 0) >= 1 else ("PENDING" if status_short not in ("FT","AET","PEN") else "LOST")
        if market == "Away to Score":
            return "WON" if (goals_away or 0) >= 1 else ("PENDING" if status_short not in ("FT","AET","PEN") else "LOST")
        if market == "Under 3.5":
            if status_short in ("FT","AET","PEN"):
                return "WON" if total <= 3 else "LOST"
            return "PENDING"
        if market == "1":
            if status_short in ("FT","AET","PEN"):
                return "WON" if (goals_home or 0) > (goals_away or 0) else "LOST"
            return "PENDING"
        if market == "1X":
            if status_short in ("FT","AET","PEN"):
                return "WON" if (goals_home or 0) >= (goals_away or 0) else "LOST"
            return "PENDING"
        if market == "12":
            if status_short in ("FT","AET","PEN"):
                return "WON" if (goals_home or 0) != (goals_away or 0) else "LOST"
            return "PENDING"
        if market == "DNB Home":
            if status_short in ("FT","AET","PEN"):
                if (goals_home or 0) > (goals_away or 0): return "WON"
                if (goals_home or 0) < (goals_away or 0): return "LOST"
                return "VOID"
            return "PENDING"
        if market == "DNB Away":
            if status_short in ("FT","AET","PEN"):
                if (goals_away or 0) > (goals_home or 0): return "WON"
                if (goals_away or 0) < (goals_home or 0): return "LOST"
                return "VOID"
            return "PENDING"
        return "PENDING"

    def update_betslips_progress_and_close(self):
        # iterate open betslips
        open_bets = get_open_betslips()
        if not open_bets:
            return
        # Pull live fixtures once
        live_map = {}
        try:
            lives = self.api.live_fixtures()
            for fx in lives:
                fid = int(fx.get("fixture",{}).get("id"))
                live_map[fid] = fx
        except Exception as e:
            log_error("live_progress", f"live_fixtures error: {e}")

        for b in open_bets:
            bid = int(b["id"])
            sels = get_selections_for_betslip(bid)
            for sel in sels:
                if sel["result"] != "PENDING":
                    continue
                fid = int(sel["fixture_id"])
                fx = live_map.get(fid) or self.api.fixture_by_id(fid)
                if not fx:
                    continue
                info = fx.get("fixture",{})
                status_short = (info.get("status",{}) or {}).get("short") or "NS"
                goals = fx.get("goals",{})
                gh = goals.get("home") or 0
                ga = goals.get("away") or 0

                res = self._resolve_market(sel["market"], gh, ga, status_short)
                if res in ("WON","LOST","VOID"):
                    mark_selection_result(sel["id"], res)
                    w, t = update_betslip_progress(bid)
                    self.tg.send_message(render_progress_bar(w, t))
            # attempt close
            status = close_betslip_if_done(bid)
            if status:
                code = b["code"]
                if status == "WON":
                    self.tg.send_message(render_celebration(code, float(b["total_odds"])))
                elif status == "LOST_1":
                    # find missed leg
                    missed = None
                    for sel in sels:
                        if sel["result"] == "LOST":
                            missed = f"{sel['home']}–{sel['away']} ({sel['market']})"
                            break
                    self.tg.send_message(render_quasi_vincente(code, missed or "1 leg"))
                else:
                    self.tg.send_message(render_cuori_spezzati(code))
