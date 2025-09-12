import os, time, threading, pathlib
from sqlalchemy import text
from .config import Config
from .telegram_client import TelegramClient
from .api_football import APIFootball
from .autopilot import Autopilot
from .live_engine import LiveEngine
from .db import get_session
from .sql_exec import run_sql_file
from .sender import process_due_messages
from .commands import CommandsLoop  # <-- AVVIAMO ANCHE I COMANDI

def ensure_db_and_schema():
    from .db import engine
    with engine.begin() as conn:
        conn.execute(text("SELECT 1"))
    sql_path = pathlib.Path(__file__).parent / "migrazioni" / "001_init.sql"
    if sql_path.exists():
        try:
            run_sql_file(str(sql_path))
            print("[BOOT] Migrazioni applicate/già presenti.")
        except Exception as e:
            print("[BOOT] Errore migrazioni:", e)

def main():
    cfg = Config()
    tg = TelegramClient(cfg.TELEGRAM_TOKEN, cfg.CHANNEL_ID, cfg.ADMIN_ID)
    api = APIFootball(cfg.APIFOOTBALL_KEY, cfg.TZ)

    ensure_db_and_schema()

    auto = Autopilot(cfg, tg, api)
    live = LiveEngine(tg, api, cfg)
    cmd  = CommandsLoop(cfg, tg, auto)

    # assicurati che non ci sia un webhook attivo (usiamo getUpdates)
    try:
        import requests
        requests.get(f"https://api.telegram.org/bot{cfg.TELEGRAM_TOKEN}/deleteWebhook", timeout=5)
    except Exception:
        pass

    def loop_autopilot():
        while True:
            try:
                auto.run_once()
            except Exception as e:
                from .repo import log_error
                log_error("autopilot", str(e))
            time.sleep(cfg.AUTOPILOT_TICK_SECONDS)

    def loop_live():
        while True:
            try:
                live.check_favorite_under_20()
                live.update_betslips_live()
            except Exception as e:
                from .repo import log_error
                log_error("live", str(e))
            time.sleep(cfg.LIVE_POLL_SECONDS)

    def loop_sender():
        while True:
            try:
                process_due_messages(tg, api, cfg)
            except Exception as e:
                from .repo import log_error
                log_error("sender", str(e))
            time.sleep(20)

    def loop_commands():
        try:
            cmd.run_forever()
        except Exception as e:
            from .repo import log_error
            log_error("commands", str(e))

    th1 = threading.Thread(target=loop_autopilot, daemon=True)
    th2 = threading.Thread(target=loop_live, daemon=True)
    th3 = threading.Thread(target=loop_sender, daemon=True)
    th4 = threading.Thread(target=loop_commands, daemon=True)  # <--
    th1.start(); th2.start(); th3.start(); th4.start()

    print("AI Pro Tips running. Ctrl+C per uscire.")
    tg.notify_admin("AI Pro Tips avviato.")

    while True:
        time.sleep(3600)

if __name__ == "__main__":
    main()
