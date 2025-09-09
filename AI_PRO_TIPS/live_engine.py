from api_football import APIFootball
from telegram_client import TelegramClient
from repo import (
    get_open_betslips, get_selections_for_betslip, mark_selection_result,
    update_betslip_progress, close_betslip_if_done, cache_get_fixture, log_error
)
from templates import render_live_alert, render_progress_bar, render_celebration, render_quasi_vincente, render_cuori_spezzati
from config import Config
import json

class LiveEngine:
    def __init__(self, tg: TelegramClient, api: APIFootball, cfg: Config):
        self.tg = tg
        self.api = api
        self.cfg = cfg
        self.sent_fav_under_alerts = set()

    def _favorite_side_from_cache(self, fid: int):
        row = cache_get_fixture(fid)
        if not row or not row.get("odds_json"):
            return None
        try:
            mk = json.loads(row["odds_json"])
        except Exception:
            return None
        if "1" in mk or "1X" in mk:
            return "home"
        return "home"

    def _no_red_card_for_favorite(self, fx, fav_side: str) -> bool:
        # Best-effort: prova a leggere eventi live; se non disponibili, non bloccare l'alert
        fid = int(fx.get("fixture",{}).get("id"))
        try:
            events = self.api.fixture_events(fid)
        except Exception:
            events = []
        if not events:
            return True
        fav_name = fx.get("teams",{}).get(fav_side,{}).get("name","")
        for ev in events:
            if (ev.get("type") == "Card") and (str(ev.get("detail","")).lower().startswith("red")):
                team_name = (ev.get("team") or {}).get("name","")
                if team_name == fav_name:
                    return False
        return True

    def _is_favorite_losing_early(self, fx: dict) -> bool:
        if self.cfg.ALLOWED_LEAGUES and fx.get("league",{}).get("id") not in self.cfg.ALLOWED_LEAGUES:
            return False
        info = fx.get("fixture",{})
        minute = (info.get("status",{}) or {}).get("elapsed") or 0
        if not minute or minute > 20: return False
        fid = int(info.get("id"))
        fav = self._favorite_side_from_cache(fid) or "home"
        goals = fx.get("goals",{})
        gh, ga = goals.get("home") or 0, goals.get("away") or 0
        losing = (gh < ga) if fav == "home" else (ga < gh)
        if not losing: return False
        # niente rosso alla favorita
        return self._no_red_card_for_favorite(fx, fav)

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

    def _resolve_market(self, market: str, gh: int, ga: int, status_short: str):
        total = (gh or 0) + (ga or 0)
        if market == "Over 0.5":
            return "WON" if total >= 1 else ("PENDING" if status_short not in ("FT","AET","PEN") else "LOST")
        if market == "Home to Score":
            return "WON" if (gh or 0) >= 1 else ("PENDING" if status_short not in ("FT","AET","PEN") else "LOST")
        if market == "Away to Score":
            return "WON" if (ga or 0) >= 1 else ("PENDING" if status_short not in ("FT","AET","PEN") else "LOST")
        if market == "Under 3.5":
            if status_short in ("FT","AET","PEN"): return "WON" if total <= 3 else "LOST"
            return "PENDING"
        if market == "1":
            if status_short in ("FT","AET","PEN"): return "WON" if (gh or 0) > (ga or 0) else "LOST"
            return "PENDING"
        if market == "1X":
            if status_short in ("FT","AET","PEN"): return "WON" if (gh or 0) >= (ga or 0) else "LOST"
            return "PENDING"
        if market == "12":
            if status_short in ("FT","AET","PEN"): return "WON" if (gh or 0) != (ga or 0) else "LOST"
            return "PENDING"
        if market == "X2":
            if status_short in ("FT","AET","PEN"): return "WON" if (ga or 0) >= (gh or 0) else "LOST"
            return "PENDING"
        if market == "DNB Home":
            if status_short in ("FT","AET","PEN"):
                if (gh or 0) > (ga or 0): return "WON"
                if (gh or 0) < (ga or 0): return "LOST"
                return "VOID"
            return "PENDING"
        if market == "DNB Away":
            if status_short in ("FT","AET","PEN"):
                if (ga or 0) > (gh or 0): return "WON"
                if (ga or 0) < (gh or 0): return "LOST"
                return "VOID"
            return "PENDING"
        return "PENDING"

    def update_betslips_progress_and_close(self):
        open_bets = get_open_betslips()
        if not open_bets: return
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
                if not fx: continue
                info = fx.get("fixture",{})
                status_short = (info.get("status",{}) or {}).get("short") or "NS"
                goals = fx.get("goals",{})
                gh = goals.get("home") or 0
                ga = goals.get("away") or 0
                res = self._resolve_market(sel["market"], gh, ga, status_short)
                if res in ("WON","LOST","VOID"):
                    mark_selection_result(sel["id"], res)
                    w, t = update_betslip_progress(bid)
                    if t > 1:  # progress bar solo per multiple
                        self.tg.send_message(render_progress_bar(w, t))
            status = close_betslip_if_done(bid)
            if status:
                code = b["code"]
                if status == "WON":
                    self.tg.send_message(render_celebration(code, float(b["total_odds"])))
                elif status == "LOST_1":
                    missed = None
                    for sel in sels:
                        if sel["result"] == "LOST":
                            missed = f"{sel['home']}–{sel['away']} ({sel['market']})"
                            break
                    self.tg.send_message(render_quasi_vincente(code, missed or "1 leg"))
                else:
                    self.tg.send_message(render_cuori_spezzati(code))
