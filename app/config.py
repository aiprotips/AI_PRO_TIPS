import os

class Config:
    def __init__(self):
        self.TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
        self.ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
        self.APIFOOTBALL_KEY = os.getenv("APIFOOTBALL_KEY", "").strip()
        self.TZ = os.getenv("TZ", "Europe/Rome")
        self.PAGE_SIZE = 3500  # soft limit (Telegram 4096 chars)

        if not self.TELEGRAM_TOKEN:
            raise RuntimeError("TELEGRAM_TOKEN mancante")
        if not self.ADMIN_ID:
            raise RuntimeError("ADMIN_ID mancante o non valido")
        if not self.APIFOOTBALL_KEY:
            raise RuntimeError("APIFOOTBALL_KEY mancante")
