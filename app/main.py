# app/main.py — disable webhook al boot + thread scheduler 08:00 (fix doppio main)
import threading
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import requests  # <--- per deleteWebhook

from .config import Config
from .telegram_client import TelegramClient
from .api_football import APIFootball
from .commands import CommandsLoop
from .live_alerts import LiveAlerts

from .morning_job import run_morning
from .scheduler import ScheduledPublisher
from .closer import Closer

def main():
    cfg = Config()
    tg  = TelegramClient(cfg.TELEGRAM_TOKEN)
    api = APIFootball(cfg.APIFOOTBALL_KEY, tz=cfg.TZ)

    # disattiva webhook se mai fosse stato impostato
    try:
        requests.get(f"https://api.telegram.org/bot{cfg.TELEGRAM_TOKEN}/deleteWebhook", timeout=5)
    except Exception:
        pass

    print("[BOOT] Odds bot pronto. Comandi: /quote [today|tomorrow], /plan, live alerts ON")

    has_db = bool(getattr(cfg, "DATABASE_URL", None) or getattr(cfg, "MYSQL_URL", None))
    has_channel = bool(getattr(cfg, "CHANNEL_ID", None))

    cmd_loop = CommandsLoop(cfg, tg, api)
    def loop_commands():
        while True:
            try:
                cmd_loop.run_forever()
            except Exception as e:
                print(f"[commands] restart after error: {e}")
                time.sleep(2)

    la = LiveAlerts(cfg, tg, api)
    def loop_live_alerts():
        try:
            la.build_morning_watchlist()
        except Exception as e:
            print(f"[live_alerts] build watchlist on boot failed: {e}")
        while True:
            try:
                la.run_forever()
            except Exception as e:
                print(f"[live_alerts] loop error: {e}; retry in 5s")
                time.sleep(5)

    def loop_daily_watchlist():
        tz = ZoneInfo(cfg.TZ)
        while True:
            try:
                now = datetime.now(tz)
                next_8 = now.replace(hour=8, minute=0, second=0, microsecond=0)
                if next_8 <= now:
                    next_8 = next_8 + timedelta(days=1)
                time.sleep(max(1, (next_8 - now).total_seconds()))
                la.build_morning_watchlist()
            except Exception as e:
                print(f"[live_alerts] daily watchlist error: {e}")
                time.sleep(10)

    def loop_morning_scheduler():
        tz = ZoneInfo(cfg.TZ)
        while True:
            try:
                now = datetime.now(tz)
                next_8 = now.replace(hour=8, minute=0, second=0, microsecond=0)
                if next_8 <= now:
                    next_8 = next_8 + timedelta(days=1)
                time.sleep(max(1, (next_8 - now).total_seconds()))
                run_morning(cfg, tg, api)
            except Exception as e:
                print(f"[morning] error: {e}")
                time.sleep(10)

    pub = ScheduledPublisher(cfg, tg)
    def loop_publisher():
        while True:
            try:
                pub.run_forever()
            except Exception as e:
                print(f"[publisher] restart after error: {e}")
                time.sleep(5)

    closer = Closer(cfg, tg, api)
    def loop_closer():
        while True:
            try:
                closer.run_forever()
            except Exception as e:
                print(f"[closer] restart after error: {e}")
                time.sleep(5)

    # avvio thread base
    threading.Thread(target=loop_commands, daemon=True).start()
    threading.Thread(target=loop_live_alerts, daemon=True).start()
    threading.Thread(target=loop_daily_watchlist, daemon=True).start()

    # avvio condizionato
    if has_db:
        threading.Thread(target=loop_morning_scheduler, daemon=True).start()
        threading.Thread(target=loop_closer, daemon=True).start()
        if has_channel:
            threading.Thread(target=loop_publisher, daemon=True).start()
        else:
            print("[boot] CHANNEL_ID assente: publisher DISABILITATO")
    else:
        print("[boot] DB assente: morning_job/closer/publisher DISABILITATI")

    while True:
        time.sleep(3600)

if __name__ == "__main__":
    main()
