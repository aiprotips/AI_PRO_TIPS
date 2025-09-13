import os

class Config:
    def __init__(self):
        self.TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
        self.ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
        self.APIFOOTBALL_KEY = os.getenv("APIFOOTBALL_KEY", "").strip()
        self.TZ = os.getenv("TZ", "Europe/Rome")
        self.PAGE_SIZE = 3500  # soft limit (Telegram 4096 chars)
        self.CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0")) or None
# opzionale, comodo nelle CTA:
self.PUBLIC_LINK = os.getenv("PUBLIC_LINK", "https://t.me/AIProTips")

        if not self.TELEGRAM_TOKEN:
            raise RuntimeError("TELEGRAM_TOKEN mancante")
        if not self.ADMIN_ID:
            raise RuntimeError("ADMIN_ID mancante o non valido")
        if not self.APIFOOTBALL_KEY:
            raise RuntimeError("APIFOOTBALL_KEY mancante")
