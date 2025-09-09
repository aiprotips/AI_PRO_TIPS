import os

class Config:
    APIFOOTBALL_KEY = os.getenv("APIFOOTBALL_KEY", "REPLACE_ME")
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "REPLACE_ME")
    CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1000000000000"))
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

    MYSQL_URL = os.getenv("MYSQL_URL", "").strip()
    TZ = os.getenv("TZ", "Europe/Rome")

    # Odds target generali (usati solo come fallback)
    LEG_ODDS_MIN = float(os.getenv("LEG_ODDS_MIN", "1.20"))
    LEG_ODDS_MAX = float(os.getenv("LEG_ODDS_MAX", "1.35"))

    # Quiet hours: 00:00–07:59
    QUIET_HOURS = (0, 8)
    MIN_GAP_MINUTES = int(os.getenv("MIN_GAP_MINUTES", "18"))
    SLOTS = {
        "morning":  ("08:00", "11:45"),
        "lunch":    ("12:00", "14:00"),
        "afternoon":("15:00", "18:30"),
        "evening":  ("19:30", "23:59"),
    }

    LIVE_POLL_SECONDS = int(os.getenv("LIVE_POLL_SECONDS", "75"))
    AUTOPILOT_TICK_SECONDS = int(os.getenv("AUTOPILOT_TICK_SECONDS", "300"))

    # Leghe consentite (solo queste verranno usate)
    ALLOWED_LEAGUES = [
        # Italia
        135, 136, 137, 318,
        # Inghilterra
        39, 40, 45, 46,
        # Spagna
        140, 141, 143,
        # Germania
        78, 79, 81,
        # Francia
        61, 62, 66,
        # Portogallo
        94, 96,
        # Olanda
        88, 90,
        # Belgio
        144,
        # Austria / Danimarca / Romania / Scozia / Svizzera / Turchia
        218, 103, 283, 179, 207, 203,
        # Coppe europee + Mondiali
        2, 3, 848, 4,
        # Sudamerica
        10, 11,
        # Extra consigliati
        71, 128, 253,
    ]

    # Piano giornaliero
    DAILY_PLAN = {
        "value_singles": 2,   # 2 singole (1.50–1.80)
        "combos": [
            {"name": "doppia",    "legs": 2,    "leg_lo": 1.30, "leg_hi": 1.50},
            {"name": "tripla",    "legs": 3,    "leg_lo": 1.20, "leg_hi": 1.50},
            {"name": "quintupla", "legs": 5,    "leg_lo": 1.20, "leg_hi": 1.50},
            {"name": "lunga",     "legs": "8-12","leg_lo": 1.10, "leg_hi": 1.36},
        ],
        "random_content": {
            "stat_flash_per_day": 2,
            "banter_per_day": 2,
            "story_per_day": 1
        }
    }
