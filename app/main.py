# app/main.py — aggiunta disable webhook al boot + thread scheduler 08:00
import threading
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import requests  # <--- per deleteWebhook

from .config import Config
from .telegram_client import TelegramClient
from .api_football import APIFootball
from .commands import CommandsLoop
from .live_alerts import LiveAlerts  # nuovo modulo per gli alert

# NEW: import per il job mattutino + publisher + closer
from .morning_job import run_morning
from .scheduler import ScheduledPublisher
from .closer import Closer

def main():
    cfg = Config()
    tg  = TelegramClient(cfg.TELEGRAM_TOKEN)
    api = APIFootball(cfg.APIFOOTBALL_KEY, tz=cfg.TZ)

    # PATCH: disattiva webhook se mai fosse stato impostato
    try:
        requests.get(f"https://api.telegram.org/bot{cfg.TELEGRAM_TOKEN}/deleteWebhook", timeout=5)
    except Exception:
        pass

    print("[BOOT] Odds bot pronto. Comandi: /quote [today|tomorrow], /plan, live alerts ON")

    # --- Guardie runtime per avvio thread dipendenti da DB/CHANNEL ---
    has_db = bool(getattr(cfg, "DATABASE_URL", None) or getattr(cfg, "MYSQL_URL", None))
    has_channel = bool(getattr(cfg, "CHANNEL_ID", None))

    # --- Loop comandi (DM admin) ---
    cmd_loop = CommandsLoop(cfg, tg, api)

    def loop_commands():
        while True:
            try:
                cmd_loop.run_forever()
            except Exception as e:
                # piccolo backoff se mai crasha
                print(f"[commands] restart after error: {e}")
                time.sleep(2)

    # --- Live Alerts (favorite ≤1.26 che vanno sotto entro 20' senza rosso) ---
    la = LiveAlerts(cfg, tg, api)

    def loop_live_alerts():
        # carica la watchlist appena parte
        try:
            la.build_morning_watchlist()
        except Exception as e:
            print(f"[live_alerts] build watchlist on boot failed: {e}")
        # e poi gira per sempre
        while True:
            try:
                la.run_forever()  # include sleep interno
            except Exception as e:
                print(f"[live_alerts] loop error: {e}; retry in 5s")
                time.sleep(5)

    # Ricarica la watchlist OGNI GIORNO alle 08:00 locali
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

    # NEW: Job alle 08:00 per pianificare e accodare le schedine del giorno
    def loop_morning_scheduler():
        tz = ZoneInfo(cfg.TZ)
        while True:
            try:
                now = datetime.now(tz)
                next_8 = now.replace(hour=8, minute=0, second=0, microsecond=0)
                if next_8 <= now:
                    next_8 = next_8 + timedelta(days=1)
                time.sleep(max(1, (next_8 - now).total_seconds()))
                run_morning(cfg, tg, api)  # genera/accoda/manda DM report admin
            except Exception as e:
                print(f"[morning] error: {e}")
                time.sleep(10)

    # NEW: Publisher che posta sul canale i record in coda (send_at raggiunto)
    pub = ScheduledPublisher(cfg, tg)
    def loop_publisher():
        while True:
            try:
                pub.run_forever()
            except Exception as e:
                print(f"[publisher] restart after error: {e}")
                time.sleep(5)

    # NEW: Closer che monitora esiti / live energy / finali schedine
    closer = Closer(cfg, tg, api)
    def loop_closer():
        while True:
            try:
                closer.run_forever()
            except Exception as e:
                print(f"[closer] restart after error: {e}")
                time.sleep(5)

    # --- Avvio thread ---
    threading.Thread(target=loop_commands, daemon=True).start()
    threading.Thread(target=loop_live_alerts, daemon=True).start()
    threading.Thread(target=loop_daily_watchlist, daemon=True).start()

    # Avvio condizionato: questi richiedono DB/CHANNEL
    if has_db:
        threading.Thread(target=loop_morning_scheduler, daemon=True).start()  # NEW
        threading.Thread(target=loop_closer, daemon=True).start()             # NEW
        if has_channel:
            threading.Thread(target=loop_publisher, daemon=True).start()      # NEW
        else:
            print("[boot] CHANNEL_ID assente: publisher DISABILITATO")
    else:
        print("[boot] DB assente: morning_job/closer/publisher DISABILITATI")

    # keep alive (il processo Railway deve restare vivo)
    while True:
        time.sleep(3600)

if __name__ == "__main__":
    main()
