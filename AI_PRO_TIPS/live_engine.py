from typing import Dict, Tuple
from zoneinfo import ZoneInfo

from .config import Config
from .telegram_client import TelegramClient
from .api_football import APIFootball
from .util import now_tz
from .repo import get_open_betslips, get_selections_for_betslip, mark_selection_result, update_betslip_progress, close_betslip_if_done, log_error
from .templates import render_live_alert, render_live_energy, render_celebration_singola, render_celebration_multipla, render_quasi_vincente, render_cuori_spezzati

class LiveEngine:
    def __init__(self, tg: TelegramClient, api: APIFootball, cfg: Config):
        self.tg=tg; self.api=api; self.cfg=cfg
        self._alert_sent_fixtures=set()
        self._energy_sent_selections=set()
        self._final_message_sent_bets=set()

    def _in_quiet_hours(self) -> bool:
        return now_tz(self.cfg.TZ).hour in range(self.cfg.QUIET_HOURS[0], self.cfg.QUIET_HOURS[1])

    def _favorite_pre_from_bet365(self, fx: Dict) -> Tuple[str, float]:
        fid = int((fx.get("fixture", {}) or {}).get("id") or 0)
        try:
            odds = self.api.odds_by_fixture(fid); mk = self.api.parse_markets_bet365(odds)
            o1 = float(mk.get("1")) if "1" in mk else None
            o2 = float(mk.get("2")) if "2" in mk else None
            if o1 is None and o2 is None: return "home", 99.0
            if o2 is None or (o1 is not None and o1 <= o2): return "home", o1 or 99.0
            return "away", o2 or 99.0
        except Exception:
            return "home", 99.0

    def _no_red_card_for_favorite(self, fx: Dict, fav_side: str) -> bool:
        try:
            fid = int((fx.get("fixture", {}) or {}).get("id") or 0)
            js = self.api._get("/fixtures/events", {"fixture": fid})
            events = js.get("response", []) if js else []
        except Exception:
            events = []
        fav_name = (fx.get("teams", {}) or {}).get(fav_side, {}).get("name", "")
        for ev in events:
            if (ev.get("type") == "Card") and str(ev.get("detail","")).lower().startswith("red"):
                if (ev.get("team") or {}).get("name","") == fav_name:
                    return False
        return True

    def _should_send_fav_under20_alert(self, fx: Dict):
        lg = fx.get("league", {}) or {}; country=(lg.get("country","") or "").lower().strip(); name=(lg.get("name","") or "").lower().strip()
        if (country,name) not in self.cfg.ALLOWED_COMP_NAMES: return (False,"","",0)
        info = fx.get("fixture", {}) or {}; minute=int(((info.get("status", {}) or {}).get("elapsed") or 0))
        if not minute or minute > 20: return (False,"","",0)
        fav_side, preodd = self._favorite_pre_from_bet365(fx)
        if preodd > 1.25: return (False,"","",0)
        goals = fx.get("goals", {}) or {}; gh,ga=int(goals.get("home") or 0), int(goals.get("away") or 0)
        losing = (gh < ga) if fav_side == "home" else (ga < gh)
        if not losing: return (False,"","",0)
        if not self._no_red_card_for_favorite(fx, fav_side): return (False,"","",0)
        teams = fx.get("teams", {}) or {}; home=teams.get("home",{}).get("name","Home"); away=teams.get("away",{}).get("name","Away")
        fav_name = home if fav_side == "home" else away; other_name = away if fav_side == "home" else home
        return (True, fav_name, other_name, minute)

    def _resolve_market(self, market: str, gh: int, ga: int, status_short: str) -> str:
        finished = status_short in ("FT","AET","PEN")
        if market == "Under 3.5": return "WON" if finished and (gh+ga)<=3 else ("PENDING" if not finished else "LOST")
        if market == "Over 0.5": return "WON" if (gh+ga)>=1 else ("PENDING" if not finished else "LOST")
        if market == "1":
            if finished: 
                if gh>ga: return "WON"
                if gh<ga: return "LOST"
                return "VOID"
            return "PENDING"
        if market == "2":
            if finished:
                if ga>gh: return "WON"
                if ga<gh: return "LOST"
                return "VOID"
            return "PENDING"
        if market == "1X": return "WON" if finished and gh>=ga else ("PENDING" if not finished else "LOST")
        if market == "X2": return "WON" if finished and ga>=gh else ("PENDING" if not finished else "LOST")
        if market == "12": return "WON" if finished and gh!=ga else ("PENDING" if not finished else "LOST")
        if market == "Home to Score": return "WON" if gh>=1 else ("PENDING" if not finished else "LOST")
        if market == "Away to Score": return "WON" if ga>=1 else ("PENDING" if not finished else "LOST")
        if market == "DNB Home":
            if finished:
                if gh>ga: return "WON"
                if gh<gh: return "LOST"
                return "VOID"
            return "PENDING"
        if market == "DNB Away":
            if finished:
                if ga>gh: return "WON"
                if ga<gh: return "LOST"
                return "VOID"
            return "PENDING"
        # >>> MODIFICA: rinomina BTTS Yes/No in Gol/No Gol
        if market in ("Gol","No Gol"):
            if finished:
                if market=="Gol":     return "WON" if (gh>=1 and ga>=1) else "LOST"
                else:                 return "WON" if (gh==0 or ga==0) else "LOST"
            return "PENDING"
        return "PENDING"

    def check_favorite_under_20(self):
        if self._in_quiet_hours(): return
        try: lives = self.api.live_fixtures()
        except Exception as e: log_error("live_fav", f"live_fixtures error: {e}"); return
        for fx in (lives or []):
            fid = int((fx.get("fixture", {}) or {}).get("id") or 0)
            if fid in self._alert_sent_fixtures: continue
            ok, fav_name, other_name, minute = self._should_send_fav_under20_alert(fx)
            if ok:
                preodd = f"{self._favorite_pre_from_bet365(fx)[1]:.2f}"
                self.tg.send_message(render_live_alert(fav_name, other_name, minute, preodd, "n/d", "https://t.me/AIProTips"))
                self._alert_sent_fixtures.add(fid)

    def update_betslips_live(self):
        if self._in_quiet_hours(): return
        try:
            lives = self.api.live_fixtures(); live_map = {int((fx.get("fixture", {}) or {}).get("id") or 0): fx for fx in (lives or [])}
        except Exception:
            live_map = {}
        for b in get_open_betslips():
            bid = int(b["id"]); legs_count=int(b.get("legs_count",0)); short_id=str(b.get("short_id","-----"))
            sels = get_selections_for_betslip(bid)
            already_lost = any((s.get("result") == "LOST") for s in sels)
            if already_lost:
                update_betslip_progress(bid); status=close_betslip_if_done(bid)
                if status and bid not in self._final_message_sent_bets:
                    self._final_message_sent_bets.add(bid)
                    if status == "LOST":
                        lost_legs = [s for s in sels if s.get("result") == "LOST"]
                        if len(lost_legs) == 1:
                            missed = lost_legs[0]
                            self.tg.send_message(render_quasi_vincente(f"{missed['home']}–{missed['away']} ({missed['market']})"))
                        else:
                            self.tg.send_message(render_cuori_spezzati())
                continue
            for sel in sels:
                fid = int(sel["fixture_id"]); fx = live_map.get(fid) or self.api.fixture_by_id(fid)
                if not fx: continue
                info = fx.get("fixture", {}) or {}; status_short = (info.get("status", {}) or {}).get("short") or "NS"
                minute = int(((info.get("status", {}) or {}).get("elapsed") or 0))
                goals = fx.get("goals", {}) or {}; gh,ga=int(goals.get("home") or 0), int(goals.get("away") or 0)
                new_res = self._resolve_market(sel["market"], gh, ga, status_short)
                if new_res == "WON" and sel["result"] == "PENDING" and sel["id"] not in self._energy_sent_selections:
                    line=""; m=sel["market"]
                    if m=="Over 0.5" and (gh+ga)>=1: line="Over 0.5 preso. ✅"
                    elif m=="Home to Score" and gh>=1: line="Segna Casa preso. ✅"
                    elif m=="Away to Score" and ga>=1: line="Segna Trasferta preso. ✅"
                    elif m=="1" and gh>ga: line="Vantaggio casa: siamo sulla traccia. ✅"
                    elif m=="2" and ga>gh: line="Vantaggio ospiti: siamo sulla traccia. ✅"
                    elif m=="1X" and gh>=ga: line="Linea 1X in controllo. ✅"
                    elif m=="X2" and ga>=gh: line="Linea X2 in controllo. ✅"
                    elif m=="Under 3.5" and (gh+ga)<=3 and status_short in ("HT","2H"): line="Under 3.5 in controllo. ✅"
                    elif m in ("Gol","No Gol"): line=f"{m} in traiettoria. ✅"  # <--- MODIFICA QUI
                    if line:
                        self.tg.send_message(render_live_energy(sel["home"], sel["away"], minute, line, short_id))
                        self._energy_sent_selections.add(sel["id"])
                if new_res in ("WON","LOST","VOID") and sel["result"] != new_res:
                    mark_selection_result(sel["id"], new_res)
            won,total = update_betslip_progress(bid); status=close_betslip_if_done(bid)
            if status and bid not in self._final_message_sent_bets:
                self._final_message_sent_bets.add(bid)
                if status=="WON":
                    if legs_count<=1:
                        sel = sels[0] if sels else None
                        if sel:
                            try:
                                fx=self.api.fixture_by_id(int(sel["fixture_id"])); g=fx.get("goals",{}) or {}; score=f"{int(g.get('home') or 0)}–{int(g.get('away') or 0)}"
                            except Exception: score=""
                            self.tg.send_message(render_celebration_singola(sel["home"], sel["away"], score, sel["market"], float(sel["odds"]), "https://t.me/AIProTips"))
                    else:
                        summary=[]
                        for s in sels:
                            try: fx2=self.api.fixture_by_id(int(s["fixture_id"])); g2=fx2.get("goals",{}) or {}; sc=f"{int(g2.get('home') or 0)}–{int(g2.get('away') or 0)}"
                            except Exception: sc=""
                            summary.append({"home":s["home"],"away":s["away"],"pick":s["market"],"score":sc})
                        self.tg.send_message(render_celebration_multipla(summary, float(b["total_odds"]), "https://t.me/AIProTips"))
                elif status=="LOST":
                    lost=[s for s in sels if s.get("result")=="LOST"]
                    if len(lost)==1:
                        missed=lost[0]; self.tg.send_message(render_quasi_vincente(f"{missed['home']}–{missed['away']} ({missed['market']})"))
                    else:
                        self.tg.send_message(render_cuori_spezzati())
