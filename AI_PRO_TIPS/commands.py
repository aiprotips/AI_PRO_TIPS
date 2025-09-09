from typing import Dict, Any
from config import Config
from telegram_client import TelegramClient
from repo import kv_get, kv_set, mark_betslip_cancelled_by_code, emit_count  # <-- aggiunti helper
from autopilot import Autopilot
from util import now_tz  # <-- per /preview e /check_today
import time
import json  # <-- per leggere pool da KV

HELP_TEXT = (
    "🤖 <b>AI Pro Tips — Comandi</b>\n"
    "/start — info\n"
    "/help — questo menu\n"
    "/ping — test rapido\n"
    "/id — mostra il tuo chat id\n"
    "\n<b>Admin</b>:\n"
    "/banter, /stat, /value, /story\n"
    "/parlay N  (N=1,2,3,4,6,8,10,12)\n"
    "/status — stato rapido\n"
    "/preview — finestra invio & conteggio rimanenti\n"
    "/cancel_next value|combo — salta prossima emissione\n"
    "/cancel_sent CODE — annulla schedina inviata\n"
    "/check_picks — verifica pick del giorno & quote\n"
    "/check_today — match whitelisted di oggi & quote"
)

class CommandsLoop:
    def __init__(self, cfg: Config, tg: TelegramClient, auto: Autopilot):
        self.cfg = cfg
        self.tg = tg
        self.auto = auto

    def _get_offset(self) -> int:
        v = kv_get("tg_update_offset")
        try:
            return int(v)
        except:
            return 0

    def _set_offset(self, off: int):
        kv_set("tg_update_offset", str(off))

    def _is_admin(self, user_id: int) -> bool:
        return user_id == self.cfg.ADMIN_ID

    def _reply(self, chat_id: int, text: str):
        self.tg.send_message(text, chat_id=chat_id, disable_web_page_preview=True)

    def handle_update(self, upd: Dict[str, Any]):
        msg = upd.get("message") or upd.get("edited_message")
        if not msg: 
            return
        chat = msg.get("chat", {})
        chat_id = chat.get("id")
        user = msg.get("from", {}) or {}
        user_id = user.get("id")
        text = (msg.get("text") or "").strip()

        if not text or not chat_id:
            return

        low = text.lower()

        # Comandi base
        if low.startswith("/start"):
            self._reply(chat_id, "Benvenuto! Questo è il bot AI Pro Tips. In canale è one-way; qui puoi testare i comandi.")
            return
        if low.startswith("/help"):
            self._reply(chat_id, HELP_TEXT); return
        if low.startswith("/ping"):
            self._reply(chat_id, "pong ✅"); return
        if low.startswith("/id"):
            self._reply(chat_id, f"Tuo chat id: <code>{chat_id}</code>"); return

        # Admin only
        if not self._is_admin(user_id):
            self._reply(chat_id, "❌ Non autorizzato.")
            return

        if low.startswith("/banter"):
            self.auto.post_banter(); self._reply(chat_id, "OK: banter inviato."); return
        if low.startswith("/stat"):
            self.auto.post_stat_flash(); self._reply(chat_id, "OK: statistica lampo inviata."); return
        if low.startswith("/value"):
            ok = self.auto.post_value_single()
            self._reply(chat_id, f"Value single {'OK' if ok else 'fallita (nessuna in range)'}"); return
        if low.startswith("/story"):
            self.auto.post_story(); self._reply(chat_id, "OK: story inviata."); return
        if low.startswith("/parlay"):
            parts = text.split()
            legs = 3
            if len(parts) >= 2:
                try: legs = int(parts[1])
                except: pass
            if legs not in (1,2,3,4,5,6,8,9,10,11,12):
                legs = 3
            # range default per admin quick
            lo, hi = (1.20, 1.50)
            if legs == 2: lo, hi = (1.30, 1.50)
            if legs >= 8: lo, hi = (1.10, 1.36)
            label = {2:"🧩 Doppia Safe",3:"🚀 Tripla Safe",4:"🚀 Quintupla Safe",5:"🚀 Quintupla Safe"}.get(legs, f"🚀 Multipla x{legs} Safe")
            ok = self.auto.post_combo_range(legs, lo, hi, label)
            self._reply(chat_id, f"Parlay x{legs} {'OK' if ok else 'fallita (nessuna combo trovata)'}"); return
        if low.startswith("/status"):
            self._reply(chat_id, "Bot attivo. Loop autopilot/live/commands in esecuzione. ✅"); return

        # ---- NUOVI COMANDI ----

        # /preview -> finestra invio (T-3h) + rimanenti oggi
        if low.startswith("/preview"):
            win = self.auto.preview_window()
            if not win.get("has_fixtures"):
                self._reply(chat_id, "🗓️ Oggi nessun match whitelisted. Niente giocate programmate.")
                return
            fk = win["first_kickoff"].strftime("%H:%M")
            send_from = win["send_from"].strftime("%H:%M")
            today = now_tz(self.cfg.TZ).date()
            remaining_values = max(0, self.cfg.DAILY_PLAN["value_singles"] - emit_count("value_single", today))
            remaining_combos  = max(0, len(self.cfg.DAILY_PLAN["combos"]) - emit_count("combo", today))
            self._reply(chat_id,
                f"🗓️ <b>Preview giocate di oggi</b>\n"
                f"Primo kickoff: <b>{fk}</b>\n"
                f"Finestra invio da: <b>{send_from}</b>\n\n"
                f"Da inviare oggi:\n"
                f"• Value singole rimanenti: <b>{remaining_values}</b>\n"
                f"• Multiple rimanenti: <b>{remaining_combos}</b>")
            return

        # /cancel_next value|combo -> salta la prossima emissione
        if low.startswith("/cancel_next"):
            parts = text.split()
            if len(parts) < 2 or parts[1] not in ("value","combo"):
                self._reply(chat_id, "Uso: /cancel_next value | /cancel_next combo")
                return
            self.auto.set_skip_next(parts[1])
            self._reply(chat_id, f"✅ Prossima emissione <b>{parts[1]}</b> annullata.")
            return

        # /cancel_sent CODE -> annulla schedina già inviata
        if low.startswith("/cancel_sent"):
            parts = text.split()
            if len(parts) < 2:
                self._reply(chat_id, "Uso: /cancel_sent CODE (es: 091245-123)")
                return
            code = parts[1].strip()
            ok = mark_betslip_cancelled_by_code(code)
            self._reply(chat_id, "✅ Annullata." if ok else "❌ Codice non trovato o già chiusa.")
            return

        # /check_picks -> mostra pick del giorno + quota attuale per quel mercato
        if low.startswith("/check_picks"):
            try:
                arr = json.loads(kv_get(self.auto._picks_key()) or "[]")
            except Exception:
                arr = []
            if not arr:
                self._reply(chat_id, "Nessun pick nel pool di oggi.")
                return
            lines = []
            for rec in arr[:12]:  # limit output
                fx = self.auto.api.fixture_by_id(rec.get("fixture_id", 0))
                if not fx:
                    lines.append(f"• {rec.get('home','?')}–{rec.get('away','?')} | {rec.get('pick','?')} | fixture {rec.get('fixture_id','?')} n/d")
                    continue
                try:
                    odds = self.auto.api.odds_by_fixture(rec["fixture_id"])
                    mk = self.auto.api.parse_markets(odds)
                    val = mk.get(rec["pick"]) or "n/d"
                except Exception:
                    val = "n/d"
                lines.append(f"• {rec.get('home','?')}–{rec.get('away','?')} | {rec.get('pick','?')} → <b>{val}</b>")
            self._reply(chat_id, "<b>Controllo pick & quote</b>\n" + "\n".join(lines))
            return

        # /check_today -> primi match whitelisted + snapshot quote principali
        if low.startswith("/check_today"):
            today_str = now_tz(self.cfg.TZ).strftime("%Y-%m-%d")
            try:
                from builders import fixtures_allowed_today
                fixtures = fixtures_allowed_today(self.auto.api, today_str, self.cfg)
            except Exception:
                fixtures = []
            if not fixtures:
                self._reply(chat_id, "Oggi non ci sono match whitelisted.")
                return
            out = []
            for fx in fixtures[:10]:  # limit a 10 righe
                fid = fx.get("fixture",{}).get("id")
                home = fx.get("teams",{}).get("home",{}).get("name","Home")
                away = fx.get("teams",{}).get("away",{}).get("name","Away")
                try:
                    odds = self.auto.api.odds_by_fixture(fid)
                    mk = self.auto.api.parse_markets(odds)
                    snap_keys = ("1X","1","12","Under 3.5","Over 0.5","DNB Home","Home to Score","Away to Score")
                    snap = [f"{k}:{mk[k]}" for k in snap_keys if k in mk]
                    out.append(f"• {home}–{away} ({fid})\n   " + "  |  ".join(snap))
                except Exception:
                    out.append(f"• {home}–{away} ({fid})\n   quote n/d")
            self._reply(chat_id, "<b>Match & quote (snap)</b>\n" + "\n".join(out))
            return

        # fallback
        self._reply(chat_id, "Comando non riconosciuto. Usa /help")

    def run_forever(self):
        offset = self._get_offset()
        while True:
            try:
                updates = self.tg.get_updates(offset=offset+1, timeout=20)
                for upd in updates:
                    upd_id = upd.get("update_id", 0)
                    if upd_id > offset:
                        offset = upd_id
                        self._set_offset(offset)
                    self.handle_update(upd)
            except Exception as e:
                time.sleep(2)  # evita loop serrato
