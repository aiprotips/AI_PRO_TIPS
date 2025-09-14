# app/live_alerts.py
from __future__ import annotations
from typing import Dict, Any, Tuple
import time
from datetime import datetime
from zoneinfo import ZoneInfo

PRE_FAV_MAX = 1.26
EARLY_MINUTE_MAX = 20
DOUBLECHECK_SECONDS = 60
POLL_SECONDS = 25  # default

def _norm(s: str) -> str:
    return (s or "").strip().lower()

def _parse_match_winner_from_odds(odds_resp: list) -> Dict[str, float]:
    out = {}
    try:
        for entry in odds_resp:
            for bm in entry.get("bookmakers", []) or []:
                name = _norm(bm.get("name",""))
                if name != "bet365":
                    continue
                for bet in bm.get("bets", []) or []:
                    bname = _norm(bet.get("name",""))
                    if bname in ("match winner","winner"):
                        for v in bet.get("values", []) or []:
                            val = _norm(v.get("value","")); odd = v.get("odd")
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

def _safe_send(tg, chat_id: int, text: str):
    try:
        return tg.send_message(chat_id, text)
    except TypeError:
        return tg.send_message(text, chat_id=chat_id)
    except Exception:
        try:
            return tg.send_message(chat_id, text)
        except Exception:
            pass

class LiveAlerts:
    def __init__(self, cfg, tg, api):
        self.cfg = cfg
        self.tg  = tg
        self.api = api
        self.tz  = ZoneInfo(getattr(cfg, "TZ", "Europe/Rome"))
        self.watch: Dict[int, Dict[str, Any]] = {}
        self.pending_check: Dict[int, float] = {}
        self.alerted: set[int] = set()
        self.poll_seconds = int(getattr(cfg, "LIVE_POLL_SECONDS", POLL_SECONDS))

    def _now_local(self) -> datetime:
        return datetime.now(self.tz)

    def build_morning_watchlist(self):
        today = self._now_local().strftime("%Y-%m-%d")
        try:
            fixtures = self.api.fixtures_by_date(today)
        except Exception:
            fixtures = []

        # CHANGED: nessun filtro per lega — live alerts su tutte le competizioni
        def league_ok(_lg):  # prima: allowed_league(...)
            return True

        count = 0
        for fx in fixtures:
            lg = fx.get("league", {}) or {}
            if not league_ok(lg):
                continue
            fid = int((fx.get("fixture", {}) or {}).get("id") or 0)
            if not fid:
                continue
            try:
                odds_resp = self.api.odds_by_fixture_bet365(fid)
                mw = _parse_match_winner_from_odds(odds_resp)
            except Exception:
                mw = {}
            if not mw:
                continue

            odd1 = mw.get("1"); odd2 = mw.get("2")
            fav_side = None; fav_pre = None
            if odd1 and (not odd2 or odd1 <= odd2):
                fav_side, fav_pre = "home", odd1
            elif odd2:
                fav_side, fav_pre = "away", odd2
            if (fav_pre is None) or (float(fav_pre) > PRE_FAV_MAX):
                continue

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

        _safe_send(self.tg, int(self.cfg.ADMIN_ID), f"🔎 LiveAlerts: watchlist caricata ({count} favorite ≤ {PRE_FAV_MAX}).")

    def _fixture_losing_info(self, fx: Dict[str, Any], fav_side: str) -> Tuple[bool, int]:
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
            return True

    def _current_live_price_for_fav(self, fid: int, fav_side: str) -> float | None:
        try:
            odds_resp = self.api.odds_by_fixture_bet365(fid)
            mw = _parse_match_winner_from_odds(odds_resp)
            key = "1" if fav_side == "home" else "2"
            return float(mw[key]) if key in mw else None
        except Exception:
            return None

    def _send_alert(self, rec: Dict[str, Any], fid: int, minute: int, live_price: float | None):
        fav = rec["fav_name"]; other = rec["other_name"]
        pre = rec["pre_odd"]; league = rec["league"]
        lp_str = f"{live_price:.2f}" if isinstance(live_price, (int,float)) else "n/d"
        msg = (
            f"⚡ <b>LIVE ALERT</b>\n\n"
            f"[{league}]\n"
            f"⏱️ {minute}' — la favorita <b>{fav}</b> è sotto contro {other}\n"
            f"Pre-match: <b>{pre:.2f}</b>  |  Live ML: <b>{lp_str}</b>\n\n"
            f"🎯 Idea ingresso: vittoria <b>{fav}</b> (spot live)\n"
            f"(doppio check eseguito)"
        )
        _safe_send(self.tg, int(self.cfg.ADMIN_ID), msg)
        channel_id = getattr(self.cfg, "CHANNEL_ID", None)
        if channel_id:
            _safe_send(self.tg, int(channel_id), msg)

    def _handle_live_fixture(self, fx: Dict[str, Any]):
        fid = int((fx.get("fixture", {}) or {}).get("id") or 0)
        if fid not in self.watch or fid in self.alerted:
            return
        rec = self.watch[fid]
        fav_side = rec["fav_side"]; fav_name = rec["fav_name"]

        losing, minute = self._fixture_losing_info(fx, fav_side)
        if not losing or minute <= 0 or minute > EARLY_MINUTE_MAX:
            return
        if not self._no_red_for_fav(fid, fav_name):
            return

        now = time.time()
        if fid not in self.pending_check:
            self.pending_check[fid] = now
            return

        if now - self.pending_check[fid] >= DOUBLECHECK_SECONDS:
            try:
                fx2 = self.api.fixture_by_id(fid) or {}
            except Exception:
                fx2 = {}
            losing2, minute2 = self._fixture_losing_info(fx2, fav_side)
            if losing2 and minute2 <= EARLY_MINUTE_MAX and self._no_red_for_fav(fid, fav_name):
                live_price = self._current_live_price_for_fav(fid, fav_side)
                self._send_alert(rec, fid, minute2, live_price)
                self.alerted.add(fid)
            self.pending_check.pop(fid, None)

    def tick(self):
        try:
            lives = self.api.live_fixtures()
        except Exception:
            lives = []
        for fx in (lives or []):
            self._handle_live_fixture(fx)

    def run_forever(self):
        while True:
            self.tick()
            time.sleep(self.poll_seconds)
