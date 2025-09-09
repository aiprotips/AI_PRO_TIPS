import os

class Config:
    APIFOOTBALL_KEY = os.getenv("APIFOOTBALL_KEY", "REPLACE_ME")
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "REPLACE_ME")
    CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1000000000000"))
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

    MYSQL_URL = os.getenv("MYSQL_URL", "").strip()
    TZ = os.getenv("TZ", "Europe/Rome")

    # Odds target per leg
    LEG_ODDS_MIN = float(os.getenv("LEG_ODDS_MIN", "1.20"))
    LEG_ODDS_MAX = float(os.getenv("LEG_ODDS_MAX", "1.35"))

    # Frequenze giornaliere
    DAILY_COUNTS = {
        "stat_flash": int(os.getenv("STAT_FLASH_PER_DAY", "2")),
        "banter": int(os.getenv("BANTER_PER_DAY", "2")),
        "value_scan": int(os.getenv("VALUE_SCAN_PER_DAY", "1")),
        "story": int(os.getenv("STORY_PER_DAY", "1")),
        "parlays": [
            {"name": "singola_safe", "legs": 1},
            {"name": "doppia_safe",  "legs": 2},
            {"name": "tripla_safe",  "legs": 3},
            {"name": "quad_safe",    "legs": 4},
            {"name": "sestuple_safe","legs": 6},
        ],
    }

    # Quiet hours & scheduling
    QUIET_HOURS = (0, 9)  # 00:00–08:59
    MIN_GAP_MINUTES = int(os.getenv("MIN_GAP_MINUTES", "18"))
    SLOTS = {
        "morning":  ("09:15", "11:45"),
        "lunch":    ("12:00", "14:00"),
        "afternoon":("15:00", "18:30"),
        "evening":  ("19:30", "23:15"),
    }

    LIVE_POLL_SECONDS = int(os.getenv("LIVE_POLL_SECONDS", "75"))
    AUTOPILOT_TICK_SECONDS = int(os.getenv("AUTOPILOT_TICK_SECONDS", "300"))

    MONITOR_LEAGUES = None  # e.g., [39,140,135,78,61]
