import time, threading
from sqlalchemy import text
from .config import Config
from .db import engine
from .telegram_client import TelegramClient
from .api_football import APIFootball
from .autopilot import Autopilot
from .live_engine import LiveEngine
from .commands import CommandsLoop

def main():
    cfg = Config()
    with engine.begin() as conn: conn.execute(text("SELECT 1"))
    tg = TelegramClient(cfg.TELEGRAM_TOKEN, cfg.CHANNEL_ID, cfg.ADMIN_ID)
    api = APIFootball(cfg.APIFOOTBALL_KEY, cfg.TZ)
    auto = Autopilot(cfg, tg, api)
    live = LiveEngine(tg, api, cfg)
    cmd  = CommandsLoop(cfg, tg, auto)

    def loop_autopilot():
        while True:
            try: auto.run_once()
            except Exception as e: tg.notify_admin(f"[autopilot] {e}")
            time.sleep(30)

    def loop_live():
        while True:
            try:
                live.check_favorite_under_20()
                live.update_betslips_live()
            except Exception as e: tg.notify_admin(f"[live] {e}")
            time.sleep(40)

    def loop_commands():
        try: cmd.run_forever()
        except Exception as e: tg.notify_admin(f"[commands] {e}")

    threading.Thread(target=loop_autopilot, daemon=True).start()
    threading.Thread(target=loop_live, daemon=True).start()
    threading.Thread(target=loop_commands, daemon=True).start()
    tg.notify_admin("AI Pro Tips avviato.")
    while True: time.sleep(3600)

if __name__ == "__main__":
    main()
