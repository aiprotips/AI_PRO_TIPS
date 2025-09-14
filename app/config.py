import os

class Config:
    def __init__(self):
        self.TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
        self.ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or "0")

        ch = os.getenv("CHANNEL_ID", "0").strip()
        try:
            self.CHANNEL_ID = int(ch) if ch else None
            if self.CHANNEL_ID == 0:
                self.CHANNEL_ID = None
        except Exception:
            self.CHANNEL_ID = None

        self.APIFOOTBALL_KEY = os.getenv("APIFOOTBALL_KEY", "").strip()

        self.TZ = os.getenv("TZ", "Europe/Rome")
        self.PAGE_SIZE = int(os.getenv("PAGE_SIZE", "3500"))
        self.PUBLIC_LINK = os.getenv("PUBLIC_LINK", "https://short-url.org/1eygc")

        self.LIVE_POLL_SECONDS = int(os.getenv("LIVE_POLL_SECONDS", "25"))
        qh = os.getenv("QUIET_HOURS", "0,8").split(",")
        try:
            self.QUIET_HOURS = (int(qh[0]), int(qh[1]))
        except Exception:
            self.QUIET_HOURS = (0, 8)

        self.DATABASE_URL = os.getenv("DATABASE_URL", "").strip() or None
        self.MYSQL_URL = os.getenv("MYSQL_URL", "").strip() or None

        if not self.TELEGRAM_TOKEN:
            raise RuntimeError("TELEGRAM_TOKEN mancante")
        if not self.ADMIN_ID:
            raise RuntimeError("ADMIN_ID mancante o non valido")
        if not self.APIFOOTBALL_KEY:
            raise RuntimeError("APIFOOTBALL_KEY mancante")
