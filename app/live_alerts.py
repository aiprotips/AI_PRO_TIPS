# app/live_alerts.py
# Live Alerts — favorita pre ≤ 1.26 che va sotto entro 20' senza rosso
# Doppio controllo a 60s e invio DM all'ADMIN_ID (per ora non al canale).

from __future__ import annotations
from typing import Dict, Any, Tuple
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

PRE_FAV_MAX = 1.26           # soglia favorita pre-match
EARLY_MINUTE_MAX = 20        # entro il 20'
DOUBLECHECK_SECONDS = 60     # delay per secondo controllo
POLL_SECONDS = 25            # frequenza polling live

def _norm(s: str) -> str:
    return (s or "").strip().lower()

def _parse_match_winner_from_odds(odds_resp: list) -> Dict[str, float]:
    """
    Parser minimale: estrae solo Match Winner full-time (1,2) da odds_resp /odds?fixture=...&bookmaker=8.
    Filtra quote <=1.05 (placeholder).
    """
    out = {}
    try:
        # odds_resp: [ { fixture, bookmakers:[{ name, lastUpdate, bets:[{name,values:[{value,odd}]}] }]} ]
        for entry in odds_resp:
            for bm in entry.get("bookmakers", []) or []:
                name = _norm(bm.get("name",""))
                if name != "bet365":
                    continue
                for bet in bm.get("bets", []) or []:
                    bname = _norm(bet.get("name",""))
                    if bname in ("match winner","winner"):
                        for v in bet.get("values", []) or []:
                            val = _norm(v.get("value",""))
                            odd = v.get("odd")
                            try:
                                x = float(odd)
                            except:
                                continue
                            if x <= 1.05:
                                continue
                            if val.startswith("home") or val == "1":
                                out["1"] = x
                            elif val.startswith("away") or val == "2":
                                out["2"] = x
        return out
    except Exception:
        return out

def _has_red_card_for(team_name: str, events_resp: Dict[str, Any]) -> bool:
    """
    Controlla se il team_name ha ricevuto un rosso negli events del fixture.
    """
    try:
        events = events_resp.get("response", []) or []
        for ev in events:
            if ev.get("type") == "Card" and str(ev.get("detail","")).lower().startswith("red"):
                t = ((ev.get("team") or {}).get("name") or "")
                if t == team_name:
                    return True
    except Exception:
        pass
    return False

class LiveAlerts:
    """
    Usage:
      la = LiveAlerts(cfg, tg, api)
      la.build_morning_watchlist()       # chiamalo alle 08:00 locali
      la.run_forever()                   # in un thread dedicato

    Per ora invia SOLO all'ADMIN_ID (DM). In futuro potrai usare CHANNEL_ID.
    """

    def __init__(self, cfg, tg, api):
        self.cfg = cfg
        self.tg  = tg
        self.api = api
        self.tz  = ZoneInfo(getattr(cfg, "TZ", "Europe/Rome"))
        self.watch: Dict[int, Dict[str, Any]] = {}        # fixture_id -> info favorita
        self.pending_check: Dict[int, float] = {}         # fixture_id -> epoch_time del primo trigger
        self.alerted: set[int] = set()                    # fixture già alertate (no duplicati)

    def _now_local(self) -> datetime:
        return datetime.now(self.tz)

    def build_morning_watchlist(self):
        """
        Costruisce la watchlist dai fixtures di OGGI: favorite pre ≤ 1.26
        Solo leghe whitelisted.
        """
        today = self._now_local().strftime("%Y-%m-%d")
        try:
            fixtures = self.api.fixtures_by_date(today)
        except Exception:
            fixtures = []

        # filtro leghe whitelisted
        try:
            from .leagues import allowed_league
            def league_ok(lg): 
                return allowed_league(lg.get("country",""), lg.get("name",""))
        except Exception:
            def league_ok(lg): 
                return True

        count = 0
        for fx in fixtures:
            lg = fx.get("league", {}) or {}
            if not league_ok(lg):
                continue
            fid = int((fx.get("fixture", {}) or {}).get("id") or 0)
            if not fid:
                continue

            # quote pre-match Bet365 per match winner (1,2)
            try:
                odds_resp = self.api.odds_by_fixture_bet365(fid)
                mw = _parse_match_winner_from_odds(odds_resp)
            except Exception:
                mw = {}

            if not mw:
                continue

            # trova favorita e controlla soglia
            odd1 = mw.get("1"); odd2 = mw.get("2")
            fav_side = None; fav_pre = None
            if odd1 and (not odd2 or odd1 <= odd2):
                fav_side, fav_pre = "home", odd1
            elif odd2:
                fav_side, fav_pre = "away", odd2

            if (fav_pre is None) or (float(fav_pre) > PRE_FAV_MAX):
                continue

            # salva info
            tms = fx.get("teams", {}) or {}
            fav_name = (tms.get(fav_side, {}) or {}).get("name") or (fx.get("fixture", {}).get("teams", {}) or {}).get(fav_side, {}).get("name") or fav_side
            other_side = "away" if fav_side == "home" else "home"
            other_name = (tms.get(other_side, {}) or {}).get("name") or (fx.get("fixture", {}).get("teams", {}) or {}).get(other_side, {}).get("name") or other_side

            self.watch[fid] = {
                "fav_side": fav_side,
                "fav_name": fav_name,
                "other_name": other_name,
                "pre_odd": float(fav_pre),
                "league": f"{lg.get('country','')} — {lg.get('name','')}"
            }
            count += 1

        # feedback all'admin
        try:
            self.tg.send_message(self.cfg.ADMIN_ID, f"🔎 LiveAlerts: watchlist caricata ({count} favorite ≤ {PRE_FAV_MAX}).")
        except Exception:
            pass

    def _fixture_losing_info(self, fx: Dict[str, Any], fav_side: str) -> Tuple[bool, int]:
        """
        Ritorna (is_losing, minute) per la favorita nel fixture fx.
        """
        try:
            info = fx.get("fixture", {}) or {}
            minute = int(((info.get("status", {}) or {}).get("elapsed") or 0))
            goals = fx.get("goals", {}) or {}
            gh, ga = int(goals.get("home") or 0), int(goals.get("away") or 0)
            losing = (gh < ga) if fav_side == "home" else (ga < gh)
            return losing, minute
        except Exception:
            return False, 0

    def _no_red_for_fav(self, fid: int, fav_name: str) -> bool:
        try:
            ev = self.api._get("/fixtures/events", {"fixture": fid})
            return not _has_red_card_for(fav_name, ev)
        except Exception:
            return True  # se non riusciamo a leggere eventi, non bloccare

    def _current_live_price_for_fav(self, fid: int, fav_side: str) -> float | None:
        """
        Prova a leggere la quota live (Bet365) per la vittoria della favorita.
        (Non sempre disponibile in modo affidabile; se non c'è, restituisce None)
        """
        try:
            odds_resp = self.api.odds_by_fixture_bet365(fid)
            mw = _parse_match_winner_from_odds(odds_resp)
            key = "1" if fav_side == "home" else "2"
            return float(mw[key]) if key in mw else None
        except Exception:
            return None

    def _send_admin_alert(self, rec: Dict[str, Any], fid: int, minute: int, live_price: float | None):
        fav = rec["fav_name"]; other = rec["other_name"]
        pre = rec["pre_odd"]
        league = rec["league"]
        lp_str = f"{live_price:.2f}" if isinstance(live_price, (int,float)) else "n/d"
        msg = (
            f"⚡ <b>LIVE ALERT</b> — favorita sotto\n\n"
            f"[{league}]\n"
            f"⏱️ {minute}' — {fav} sotto contro {other}\n"
            f"Pre-match: <b>{pre:.2f}</b>  |  Live ML: <b>{lp_str}</b>\n\n"
            f"👉 Consiglio live: vittoria <b>{fav}</b> (entry spot)\n"
            f"(verifica doppia effettuata)"
        )
        try:
            self.tg.send_message(self.cfg.ADMIN_ID, msg)
        except Exception:
            pass

    def _handle_live_fixture(self, fx: Dict[str, Any]):
        fid = int((fx.get("fixture", {}) or {}).get("id") or 0)
        if fid not in self.watch or fid in self.alerted:
            return
        rec = self.watch[fid]
        fav_side = rec["fav_side"]
        fav_name = rec["fav_name"]

        losing, minute = self._fixture_losing_info(fx, fav_side)
        if not losing or minute <= 0 or minute > EARLY_MINUTE_MAX:
            return
        if not self._no_red_for_fav(fid, fav_name):
            return

        now = time.time()
        if fid not in self.pending_check:
            # primo trigger → salva timestamp e aspetta il secondo controllo
            self.pending_check[fid] = now
            return

        # se sono passati >= DOUBLECHECK_SECONDS dal primo trigger, ricontrolla
        if now - self.pending_check[fid] >= DOUBLECHECK_SECONDS:
            try:
                fx2 = self.api.fixture_by_id(fid) or {}
            except Exception:
                fx2 = {}
            losing2, minute2 = self._fixture_losing_info(fx2, fav_side)
            if losing2 and minute2 <= EARLY_MINUTE_MAX and self._no_red_for_fav(fid, fav_name):
                live_price = self._current_live_price_for_fav(fid, fav_side)
                self._send_admin_alert(rec, fid, minute2, live_price)
                self.alerted.add(fid)
            # cleanup pending (sia che alerti, sia che no; se continua losing, rifarà pending al prossimo giro)
            self.pending_check.pop(fid, None)

    def tick(self):
        """
        Un giro di controllo live; da richiamare periodicamente (es. ogni 25s).
        """
        try:
            lives = self.api.live_fixtures()
        except Exception:
            lives = []
        for fx in (lives or []):
            self._handle_live_fixture(fx)

    def run_forever(self):
        while True:
            self.tick()
            time.sleep(POLL_SECONDS)
