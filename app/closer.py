# app/closer.py
from __future__ import annotations
import time
from typing import Dict, Any, List, Tuple
from zoneinfo import ZoneInfo
from datetime import datetime

from .api_football import APIFootball
from .telegram_client import TelegramClient
from .repo_bets import (
    get_open_betslips, get_selections, update_selection_result, recalc_betslip_status
)
from .templates_schedine import render_live_energy, render_celebration_singola, render_celebration_multipla, render_quasi_vincente, render_cuori_spezzati

# ------- helper invio a prova di firma -------
def _send(tg: TelegramClient, chat_id: int, text: str):
    try:
        return tg.send_message(chat_id, text)  # firma corretta
    except TypeError:
        return tg.send_message(text, chat_id=chat_id)  # fallback
    except Exception:
        try:
            return tg.send_message(chat_id, text)
        except Exception:
            pass

def _channel_id(cfg) -> int | None:
    try:
        return int(getattr(cfg, "CHANNEL_ID", None)) if getattr(cfg, "CHANNEL_ID", None) is not None else None
    except Exception:
        return None

# ------- risoluzione mercato -------
def _resolve_market(market: str, gh: int, ga: int, finished: bool) -> str:
    tot = gh + ga
    if market == "Under 3.5":
        return "WON" if finished and tot <= 3 else ("PENDING" if not finished else "LOST")
    if market == "Under 2.5":
        return "WON" if finished and tot <= 2 else ("PENDING" if not finished else "LOST")
    if market == "Over 0.5":
        return "WON" if tot >= 1 else ("PENDING" if not finished else "LOST")
    if market == "Over 1.5":
        return "WON" if tot >= 2 else ("PENDING" if not finished else "LOST")
    if market == "Over 2.5":
        return "WON" if tot >= 3 else ("PENDING" if not finished else "LOST")
    if market == "1":
        if not finished: return "PENDING"
        return "WON" if gh > ga else ("LOST" if gh < ga else "VOID")
    if market == "2":
        if not finished: return "PENDING"
        return "WON" if ga > gh else ("LOST" if ga < gh else "VOID")
    if market == "1X":
        return "WON" if finished and gh >= ga else ("PENDING" if not finished else "LOST")
    if market == "X2":
        return "WON" if finished and ga >= gh else ("PENDING" if not finished else "LOST")
    if market == "12":
        return "WON" if finished and gh != ga else ("PENDING" if not finished else "LOST")
    if market == "Gol":
        return "WON" if finished and gh >= 1 and ga >= 1 else ("PENDING" if not finished else "LOST")
    if market == "No Gol":
        return "WON" if finished and (gh == 0 or ga == 0) else ("PENDING" if not finished else "LOST")
    return "PENDING"

def _fixture_state(api: APIFootball, fid: int) -> Tuple[int,int,bool]:
    fx = api.fixture_by_id(int(fid)) or {}
    info = (fx.get("fixture") or {})
    status = (info.get("status") or {}).get("short") or "NS"
    finished = status in ("FT","AET","PEN")
    goals = fx.get("goals") or {}
    gh = int(goals.get("home") or 0); ga = int(goals.get("away") or 0)
    return gh, ga, finished

class Closer:
    """Monitora le schedine e gestisce Live Energy + messaggi finali."""
    def __init__(self, cfg, tg: TelegramClient, api: APIFootball):
        self.cfg = cfg
        self.tg = tg
        self.api = api
        self.tz = ZoneInfo(getattr(cfg, "TZ","Europe/Rome"))
        self.energy_sent: set[int] = set()   # selection_id già annunciati
        self.final_sent: set[int]  = set()   # betslip_id già chiusi e annunciati

    def _live_ok(self) -> bool:
        h = datetime.now(self.tz).hour
        qs, qe = getattr(self.cfg, "QUIET_HOURS", (0,8))
        return not (qs <= h < qe)

    def _send_energy_if_needed(self, b: Dict[str,Any], s: Dict[str,Any], new_res: str, minute: int):
        if new_res != "WON": 
            return
        if s["id"] in self.energy_sent:
            return
        # manda solo se la schedina non è persa (lo assicuriamo valutando betslip dopo gli update)
        line = None
        m = s["market"]
        home = s["home"]; away = s["away"]
        if m == "Over 0.5": line = "Over 0.5 preso. ✅"
        elif m == "Over 1.5" and minute >= 0: line = "Over 1.5 in carreggiata. ✅"
        elif m == "Under 3.5" and minute in range(1, 90): line = "Under 3.5 in controllo. ✅"
        elif m == "1" and minute >= 0: line = "Casa in vantaggio, traccia rispettata. ✅"
        elif m == "2" and minute >= 0: line = "Ospiti in vantaggio, traccia rispettata. ✅"
        elif m == "1X": line = "Linea 1X solida. ✅"
        elif m == "X2": line = "Linea X2 solida. ✅"
        elif m == "No Gol": line = "No Gol sulla linea. ✅"
        elif m == "Gol": line = "Gol in traiettoria. ✅"
        if line:
            ch = _channel_id(self.cfg)
            if ch is not None:
                msg = render_live_energy(home, away, minute, line, str(b["id"]))
                _send(self.tg, ch, msg)
                self.energy_sent.add(s["id"])

    def tick(self):
        if not self._live_ok():
            time.sleep(5); return

        for b in get_open_betslips():
            bid = int(b["id"])
            if bid in self.final_sent:
                continue
            sels = get_selections(bid)
            any_change = False
            for s in sels:
                if s["result"] != "PENDING":
                    continue
                fid = int(s["fixture_id"])
                gh, ga, finished = _fixture_state(self.api, fid)
                # minuto bruto (se possibile)
                minute = 0
                try:
                    fx = self.api.fixture_by_id(fid) or {}
                    minute = int(((fx.get("fixture",{}) or {}).get("status",{}) or {}).get("elapsed") or 0)
                except Exception:
                    pass
                new_res = _resolve_market(s["market"], gh, ga, finished)
                if new_res != "PENDING":
                    update_selection_result(int(s["id"]), new_res, gh if finished else None, ga if finished else None)
                    any_change = True
                    # live energy: annuncia singola leg vinta se la schedina non è già persa
                    if new_res == "WON" and b["status"] != "LOST":
                        self._send_energy_if_needed(b, s, new_res, minute)

            if any_change:
                status = recalc_betslip_status(bid)
                if status in ("WON","LOST"):
                    # invia finale una sola volta
                    if bid in self.final_sent:
                        continue
                    self.final_sent.add(bid)
                    ch = _channel_id(self.cfg)
                    if ch is None:
                        continue
                    if status == "WON":
                        if int(b.get("legs_count", 0)) <= 1:
                            # singola
                            s0 = get_selections(bid)[0]
                            try:
                                fx = self.api.fixture_by_id(int(s0["fixture_id"])) or {}
                                g = fx.get("goals") or {}
                                score = f"{int(g.get('home') or 0)}–{int(g.get('away') or 0)}"
                            except Exception:
                                score = ""
                            msg = render_celebration_singola(s0["home"], s0["away"], score, s0["market"], float(s0["odd"]), getattr(self.cfg, "PUBLIC_LINK", "https://t.me/AIProTips"))
                            _send(self.tg, ch, msg)
                        else:
                            # multipla
                            summary = []
                            for s in get_selections(bid):
                                try:
                                    fx = self.api.fixture_by_id(int(s["fixture_id"])) or {}
                                    g = fx.get("goals") or {}
                                    score = f"{int(g.get('home') or 0)}–{int(g.get('away') or 0)}"
                                except Exception:
                                    score = ""
                                summary.append({"home": s["home"], "away": s["away"], "pick": s["market"], "score": score})
                            msg = render_celebration_multipla(summary, float(b["total_odds"]), getattr(self.cfg, "PUBLIC_LINK", "https://t.me/AIProTips"))
                            _send(self.tg, ch, msg)
                    else:
                        # persa: 1 sola leg → "quasi", altrimenti "cuori"
                        sels2 = get_selections(bid)
                        lost = [s for s in sels2 if s["result"] == "LOST"]
                        if len(lost) == 1:
                            missed = lost[0]
                            line = f"{missed['home']}–{missed['away']} ({missed['market']})"
                            _send(self.tg, ch, render_quasi_vincente(line))
                        else:
                            _send(self.tg, ch, render_cuori_spezzati())

    def run_forever(self):
        while True:
            try:
                self.tick()
            except Exception:
                time.sleep(5)
            time.sleep(20)
