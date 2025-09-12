from typing import Dict, Any, List
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dateutil import parser as duparser

from .config import Config
from .telegram_client import TelegramClient
from .api_football import APIFootball
from .leagues import allowed_league, label_league

def _to_local_hhmm(iso: str, tz: str) -> str:
    try:
        dt = duparser.isoparse(iso)
        return dt.astimezone(ZoneInfo(tz)).strftime("%H:%M")
    except Exception:
        return "n/d"

def _group_by_league(rows: List[Dict]) -> Dict[str, List[Dict]]:
    out = {}
    for r in rows:
        key = label_league(r["league_country"], r["league_name"])
        out.setdefault(key, []).append(r)
    for k in out:
        out[k].sort(key=lambda x: x["kickoff_iso"])
    return out

def _format_markets(mk: Dict[str, float]) -> List[str]:
    lines = []
    r1 = [f"{k}: {mk[k]}" for k in ("1","X","2") if k in mk]
    if r1: lines.append(" | ".join(r1))

    r2 = [f"{k}: {mk[k]}" for k in ("1X","12","X2") if k in mk]
    if r2: lines.append(" | ".join(r2))

    r3 = [f"{k.replace(' ', '')}: {mk[k]}" for k in ("Over 0.5","Over 1.5","Over 2.5") if k in mk]
    if r3: lines.append(" | ".join(r3))

    r4 = [f"{k.replace(' ', '')}: {mk[k]}" for k in ("Under 2.5","Under 3.5") if k in mk]
    if r4: lines.append(" | ".join(r4))

    r5 = [f"{k}: {mk[k]}" for k in ("Gol","No Gol") if k in mk]
    if r5: lines.append(" | ".join(r5))

    return lines

def _render_day(api: APIFootball, cfg: Config, date_str: str) -> List[str]:
    entries = api.odds_by_date_bet365(date_str)
    parsed = api.parse_odds_entries(entries)
    parsed = [p for p in parsed if allowed_league(p["league_country"], p["league_name"])]
    if not parsed:
        return [f"<b>{date_str}</b> — Nessuna quota Bet365 disponibile per i campionati whitelisted."]

    grouped = _group_by_league(parsed)
    messages = []
    for league, rows in grouped.items():
        parts = [f"<b>[{league}]</b>"]
        for r in rows:
            hhmm = _to_local_hhmm(r["kickoff_iso"], cfg.TZ)
            parts.append(f"{hhmm} — {r['home']} vs {r['away']} (fixture {r['fixture_id']})")
            for mline in _format_markets(r["markets"]):
                parts.append(mline)
            if r.get("last_update"):
                parts.append(f"(upd {r['last_update']} UTC)")
            parts.append("")
        messages.append("\n".join(parts).strip())
    return messages

class CommandsLoop:
    def __init__(self, cfg: Config, tg: TelegramClient, api: APIFootball):
        self.cfg = cfg
        self.tg = tg
        self.api = api
        self._offset = 0

    def _is_admin(self, user_id: int) -> bool:
        return int(user_id) == int(self.cfg.ADMIN_ID)

    def _send_paginated(self, chat_id: int, blocks: List[str]):
        page = []
        page_len = 0
        for b in blocks:
            if page_len + len(b) + 2 > self.cfg.PAGE_SIZE:
                if page:
                    self.tg.send_message(chat_id, "\n\n".join(page))
                page = [b]; page_len = len(b) + 2
            else:
                page.append(b); page_len += len(b) + 2
        if page:
            self.tg.send_message(chat_id, "\n\n".join(page))

    def _handle_quote(self, chat_id: int, mode: str):
        now = datetime.now(ZoneInfo(self.cfg.TZ)).date()
        today = now.strftime("%Y-%m-%d")
        tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        if mode == "today":
            blocks = _render_day(self.api, self.cfg, today)
            self._send_paginated(chat_id, [f"<b>OGGI {today}</b>"] + blocks)
        elif mode == "tomorrow":
            blocks = _render_day(self.api, self.cfg, tomorrow)
            self._send_paginated(chat_id, [f"<b>DOMANI {tomorrow}</b>"] + blocks)
        else:
            blocks_today = _render_day(self.api, self.cfg, today)
            blocks_tom = _render_day(self.api, self.cfg, tomorrow)
            self._send_paginated(chat_id, [f"<b>OGGI {today}</b>"] + blocks_today + [f"<b>DOMANI {tomorrow}</b>"] + blocks_tom)

    def handle_update(self, upd: Dict[str, Any]):
        msg = upd.get("message") or upd.get("edited_message")
        if not msg:
            return
        chat = msg.get("chat", {}) or {}
        chat_id = chat.get("id")
        user = msg.get("from", {}) or {}
        user_id = user.get("id")
        text = (msg.get("text") or "").strip()
        if not text or not chat_id:
            return

        if not self._is_admin(user_id):
            self.tg.send_message(chat_id, "❌ Non autorizzato.")
            return

        low = text.lower()
        if low.startswith("/start"):
            self.tg.send_message(chat_id, "Benvenuto! Usa /quote per le quote Bet365 (oggi+domani)."); return
        if low.startswith("/help"):
            self.tg.send_message(chat_id, "Comandi: /quote [today|tomorrow]"); return
        if low.startswith("/ping"):
            self.tg.send_message(chat_id, "pong ✅"); return
        if low.startswith("/quote"):
            parts = text.split()
            mode = parts[1].lower() if len(parts)>=2 else "all"
            if mode not in ("today","tomorrow","all"):
                mode = "all"
            self._handle_quote(chat_id, mode); return

        self.tg.send_message(chat_id, "Comando non riconosciuto. Usa /help")

    def run_forever(self):
        off = self._offset
        while True:
            try:
                updates = self.tg.get_updates(offset=off+1, timeout=25)
                for u in updates:
                    upid = u.get("update_id", 0)
                    if upid > off:
                        off = upid; self._offset = off
                    self.handle_update(u)
            except Exception:
                import time; time.sleep(2)
