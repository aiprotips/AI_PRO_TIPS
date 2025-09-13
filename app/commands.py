# app/commands.py
from typing import Dict, Any, List
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dateutil import parser as duparser

from .config import Config
from .telegram_client import TelegramClient
from .api_football import APIFootball
from .leagues import allowed_league, label_league

# nuovi import per il planner
from .value_builder import plan_day, render_plan_blocks

# --- PATCH: repo scheduler & planner/watchlist ---
from .repo_sched import list_today, cancel_by_short_id, cancel_all_today  # patch
# from .planner import DailyPlanner                                         # patch  (rimosso: unificato su value_builder)
from .live_alerts import LiveAlerts                                       # patch
from .morning_job import run_morning                                      # NEW: per /regen

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
    entries = api.entries_by_date_bet365(date_str)  # usa paginazione + fallback
    parsed = [p for p in entries if allowed_league(p["league_country"], p["league_name"])]
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

    # ---------- PATCH: invio compatibile con entrambe le firme ----------
    def _send(self, chat_id: int, text: str):
        try:
            # firma corretta: (chat_id, text)
            return self.tg.send_message(chat_id, text)
        except TypeError:
            # fallback: (text, chat_id=...)
            return self.tg.send_message(text, chat_id=chat_id)
        except Exception:
            # ultima difesa
            try:
                return self.tg.send_message(chat_id, text)
            except Exception:
                pass
    # --------------------------------------------------------------------

    def _is_admin(self, user_id: int) -> bool:
        return int(user_id) == int(self.cfg.ADMIN_ID)

    def _send_paginated(self, chat_id: int, blocks: List[str]):
        page = []; total_len = 0
        page_size = getattr(self.cfg, "PAGE_SIZE", 3500)
        for b in blocks:
            if total_len + len(b) + 2 > page_size:
                if page:
                    self._send(chat_id, "\n\n".join(page))
                page = [b]; total_len = len(b) + 2
            else:
                page.append(b); total_len += len(b) + 2
        if page:
            self._send(chat_id, "\n\n".join(page))

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

    def _handle_plan(self, chat_id: int, publish: bool = False, when: str = "today"):
        now = datetime.now(ZoneInfo(self.cfg.TZ)).date()
        date_str = (now if when == "today" else (now + timedelta(days=1))).strftime("%Y-%m-%d")

        try:
            plan = plan_day(self.api, self.cfg, date_str, want_long_legs=10)
        except Exception as e:
            self._send(chat_id, f"❌ Errore planner: {e}")
            return

        blocks = render_plan_blocks(self.api, self.cfg, plan)
        if not blocks:
            self._send(chat_id, f"Nessuna giocata valida per {date_str}.")
            return

        # preview in DM
        self._send_paginated(chat_id, [f"<b>PLAN {date_str}</b>"] + blocks)

        # publish se richiesto
        if publish:
            channel_id = getattr(self.cfg, "CHANNEL_ID", None)
            if not channel_id:
                self._send(chat_id, "⚠️ CHANNEL_ID non configurato: salto pubblicazione.")
                return
            for b in blocks:
                try:
                    self._send(channel_id, b)
                except Exception:
                    pass

    def handle_update(self, upd: Dict[str, Any]):
        msg = upd.get("message") or upd.get("edited_message")
        if not msg:
            return
        chat_id = (msg.get("chat") or {}).get("id")
        user_id = (msg.get("from") or {}).get("id")
        text = (msg.get("text") or "").strip()
        if not text or not chat_id:
            return

        if not self._is_admin(user_id):
            self._send(chat_id, "❌ Non autorizzato."); return

        low = text.lower()
        if low.startswith("/start"):
            self._send(chat_id, "Benvenuto! /quote per quote Bet365, /plan per anteprima giocate."); return
        if low.startswith("/help"):
            self._send(chat_id, "Comandi: /quote [today|tomorrow|all], /plan [today|tomorrow], /plan_publish [today|tomorrow], /preview_today, /cancel ID, /cancel_all, /regen, /rebuild_watchlist, /watchlist"); return
        if low.startswith("/ping"):
            self._send(chat_id, "pong ✅"); return

        if low.startswith("/quote"):
            parts = text.split()
            mode = parts[1].lower() if len(parts)>=2 else "all"
            if mode not in ("today","tomorrow","all"):
                mode = "all"
            self._handle_quote(chat_id, mode); return

        if low.startswith("/plan_publish"):
            parts = text.split()
            when = parts[1].lower() if len(parts)>=2 else "today"
            if when not in ("today","tomorrow"):
                when = "today"
            self._handle_plan(chat_id, publish=True, when=when); return

        if low.startswith("/plan"):
            parts = text.split()
            when = parts[1].lower() if len(parts)>=2 else "today"
            if when not in ("today","tomorrow"):
                when = "today"
            self._handle_plan(chat_id, publish=False, when=when); return

        # -----------------------
        # PATCH: nuovi comandi admin
        # -----------------------
        if low.startswith("/preview_today"):
            rows = list_today()
            if not rows:
                self._send(chat_id, "Nessuna schedina pianificata oggi."); return
            tz = ZoneInfo(self.cfg.TZ)
            out = []
            for r in rows:
                when = r.get("send_at_utc")
                try:
                    if isinstance(when, datetime):
                        when_local = when.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz).strftime("%H:%M")
                    else:
                        when_local = datetime.fromisoformat(str(when)).replace(tzinfo=ZoneInfo("UTC")).astimezone(tz).strftime("%H:%M")
                except Exception:
                    when_local = "n/d"
                out.append(f"ID <b>{r['short_id']}</b> — {r['kind']} — invio: <b>{when_local}</b>\n\n{r['payload']}")
            self._send_paginated(chat_id, out); return

        if low.startswith("/cancel_all"):
            n = cancel_all_today()
            self._send(chat_id, f"🛑 Cancellate <b>{n}</b> schedine in coda oggi."); return

        if low.startswith("/cancel"):
            parts = text.split()
            if len(parts) < 2:
                self._send(chat_id, "Uso: /cancel ID"); return
            sid = parts[1].strip()
            n = cancel_by_short_id(sid)
            self._send(chat_id, "✅ Annullata." if n > 0 else "❌ ID non trovato o già inviata."); return

        if low.startswith("/regen"):
            # Rigenera la pianificazione del giorno usando la stessa pipeline del job delle 08:00
            try:
                # Usa il job ufficiale (identico a quello schedulato), con DM report automatico
                run_morning(self.cfg, self.tg, self.api)
                self._send(chat_id, "🔧 Pianificazione del giorno rigenerata (value_builder) e accodata.")
            except Exception as e:
                self._send(chat_id, f"Errore rigenerazione: {e}")
            return

        if low.startswith("/rebuild_watchlist"):
            try:
                la = LiveAlerts(self.cfg, self.tg, self.api)
            except Exception:
                la = None
            if la:
                try:
                    la.build_morning_watchlist()
                    self._send(chat_id, "✅ Watchlist ricostruita.")
                except Exception as e:
                    self._send(chat_id, f"Errore watchlist: {e}")
            else:
                self._send(chat_id, "Errore: modulo live alerts non disponibile.")
            return

        if low.startswith("/watchlist"):
            try:
                la = LiveAlerts(self.cfg, self.tg, self.api)
                la.build_morning_watchlist()
                rows = getattr(la, "watch", {})
                if not rows:
                    self._send(chat_id, "Nessuna favorita da monitorare."); return
                out = []
                for fid, rec in rows.items():
                    out.append(f"• {rec['league']} — {rec['fav_name']} vs {rec['other_name']} (pre {rec['pre_odd']:.2f})")
                self._send(chat_id, "<b>Favorite monitorate (≤1.26)</b>\n" + "\n".join(out))
            except Exception as e:
                self._send(chat_id, f"Errore watchlist: {e}")
            return
        # -----------------------

        self._send(chat_id, "Comando non riconosciuto. Usa /help")

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
