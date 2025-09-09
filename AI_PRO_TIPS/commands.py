from typing import Optional, Dict, Any
from config import Config
from telegram_client import TelegramClient
from repo import kv_get, kv_set
from autopilot import Autopilot
from datetime import datetime

HELP_TEXT = (
    "🤖 <b>AI Pro Tips — Comandi</b>\n"
    "/start — info\n"
    "/help — questo menu\n"
    "/ping — test rapido\n"
    "/id — mostra il tuo chat id\n"
    "\n<b>Admin</b>:\n"
    "/banter, /stat, /value, /story\n"
    "/parlay N  (N=1,2,3,4,6)\n"
    "/status — stato rapido"
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

        # Comandi base
        if text.lower().startswith("/start"):
            self._reply(chat_id, "Benvenuto! Questo è il bot AI Pro Tips. Per il pubblico è un canale one-way; qui puoi testare i comandi.")
            return
        if text.lower().startswith("/help"):
            self._reply(chat_id, HELP_TEXT)
            return
        if text.lower().startswith("/ping"):
            self._reply(chat_id, "pong ✅")
            return
        if text.lower().startswith("/id"):
            self._reply(chat_id, f"Tuo chat id: <code>{chat_id}</code>")
            return

        # Da qui in giù: admin only
        if not self._is_admin(user_id):
            self._reply(chat_id, "Comando non disponibile per l’utente.")
            return

        low = text.lower()
        if low.startswith("/banter"):
            self.auto.post_banter()
            self._reply(chat_id, "OK: banter inviato.")
            return
        if low.startswith("/stat"):
            self.auto.post_stat_flash()
            self._reply(chat_id, "OK: statistica lampo inviata.")
            return
        if low.startswith("/value"):
            self.auto.post_value_scan()
            self._reply(chat_id, "OK: value scanner lanciato.")
            return
        if low.startswith("/story"):
            self.auto.post_story()
            self._reply(chat_id, "OK: story inviata.")
            return
        if low.startswith("/parlay"):
            # /parlay 3
            parts = text.split()
            legs = 3
            if len(parts) >= 2:
                try:
                    legs = int(parts[1])
                except:
                    pass
            legs = legs if legs in (1,2,3,4,6) else 3
            ok = self.auto.post_parlay(legs)
            self._reply(chat_id, f"Parlay x{legs} {'OK' if ok else 'fallita (nessuna combo trovata)'}")
            return
        if low.startswith("/status"):
            self._reply(chat_id, "Bot attivo. Loop autopilot/live in esecuzione. ✅")
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
                # loggalo se vuoi
                # from repo import log_error
                # log_error("commands", str(e))
                import time
                time.sleep(2)   # <-- evita loop serrato
