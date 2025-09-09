import os, time, threading
from config import Config
from telegram_client import TelegramClient
from api_football import APIFootball
from autopilot import Autopilot
from live_engine import LiveEngine
from db import get_session
from sqlalchemy import text

def ensure_db_ready():
    # sanity check
    from db import engine
    try:
        with engine.begin() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        print("[DB] Connection error:", e)
        raise

def main():
    cfg = Config()
    tg = TelegramClient(cfg.TELEGRAM_TOKEN, cfg.CHANNEL_ID, cfg.ADMIN_ID)
    api = APIFootball(cfg.APIFOOTBALL_KEY, cfg.TZ)

    ensure_db_ready()

    auto = Autopilot(cfg, tg, api)
    live = LiveEngine(cfg, tg, api)

    def loop_autopilot():
        while True:
            try:
                auto.run_once()
            except Exception as e:
                from repo import log_error
                log_error("autopilot", str(e))
            time.sleep(cfg.AUTOPILOT_TICK_SECONDS)

    def loop_live():
        while True:
            try:
                live.check_favorite_under_20()
                live.update_betslips_progress_and_close()
            except Exception as e:
                from repo import log_error
                log_error("live", str(e))
            time.sleep(cfg.LIVE_POLL_SECONDS)

    th1 = threading.Thread(target=loop_autopilot, daemon=True)
    th2 = threading.Thread(target=loop_live, daemon=True)
    th1.start(); th2.start()

    print("AI Pro Tips running. Press Ctrl+C to stop.")
    tg.notify_admin("AI Pro Tips avviato.")

    while True:
        time.sleep(3600)

if __name__ == "__main__":
    main()
