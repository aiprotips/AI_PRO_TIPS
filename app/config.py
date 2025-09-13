import os

class Config:
    def __init__(self):
        # Token & ID
        self.TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
        self.ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or "0")

        # Canale (facoltativo ma consigliato)
        # Se non impostato o =0, alcuni post di canale vengono saltati
        ch = os.getenv("CHANNEL_ID", "0").strip()
        try:
            self.CHANNEL_ID = int(ch) if ch else None
            if self.CHANNEL_ID == 0:
                self.CHANNEL_ID = None
        except Exception:
            self.CHANNEL_ID = None

        # API-Football
        self.APIFOOTBALL_KEY = os.getenv("APIFOOTBALL_KEY", "").strip()

        # Timezone & parametri generali
        self.TZ = os.getenv("TZ", "Europe/Rome")
        self.PAGE_SIZE = int(os.getenv("PAGE_SIZE", "3500"))
        self.PUBLIC_LINK = os.getenv("PUBLIC_LINK", "https://t.me/AIProTips")

        # Live loop / Quiet hours
        self.LIVE_POLL_SECONDS = int(os.getenv("LIVE_POLL_SECONDS", "25"))
        # QUIET_HOURS come "start,end" (es. "0,8")
        qh = os.getenv("QUIET_HOURS", "0,8").split(",")
        try:
            self.QUIET_HOURS = (int(qh[0]), int(qh[1]))
        except Exception:
            self.QUIET_HOURS = (0, 8)

        # === NEW: esponi le URL DB per i check in main.py ===
        self.DATABASE_URL = os.getenv("DATABASE_URL", "").strip() or None
        self.MYSQL_URL = os.getenv("MYSQL_URL", "").strip() or None

        # Sanity checks minimi
        if not self.TELEGRAM_TOKEN:
            raise RuntimeError("TELEGRAM_TOKEN mancante")
        if not self.ADMIN_ID:
            raise RuntimeError("ADMIN_ID mancante o non valido")
        if not self.APIFOOTBALL_KEY:
            raise RuntimeError("APIFOOTBALL_KEY mancante")
