import os

class Config:
    # --- Credenziali / ambiente ---
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
    CHANNEL_ID     = int(os.getenv("CHANNEL_ID", "0"))
    ADMIN_ID       = int(os.getenv("ADMIN_ID", "0"))
    MYSQL_URL      = os.getenv("MYSQL_URL", "")
    APIFOOTBALL_KEY= os.getenv("APIFOOTBALL_KEY", "")
    TZ             = os.getenv("TZ", "Europe/Rome")

    # --- Quiet hours ---
    QUIET_HOURS = (0, 8)  # (start_hour, end_hour)

    # --- Piano giornaliero ---
    DAILY_PLAN = {
        "value_singles": 2,
        "combos": [
            {"legs": 2,     "leg_lo": 1.30, "leg_hi": 1.50},
            {"legs": 3,     "leg_lo": 1.20, "leg_hi": 1.50},
            {"legs": 5,     "leg_lo": 1.20, "leg_hi": 1.50},
            {"legs": "8-12","leg_lo": 1.10, "leg_hi": 1.36},
        ],
        "random_content": {
            "stat_flash_per_day": 2,
            "story_per_day": 2,
            "banter_per_day": 2
        }
    }

    # --- Whitelist competizioni (country,name) ---
    ALLOWED_COMP_NAMES = {
        ("italy","serie a"), ("italy","serie b"), ("italy","serie c"), ("italy","coppa italia"),
        ("england","premier league"), ("england","championship"), ("england","fa cup"), ("england","efl cup"),
        ("spain","la liga"), ("spain","laliga"), ("spain","laliga 2"), ("spain","segunda division"), ("spain","copa del rey"),
        ("germany","bundesliga"), ("germany","2. bundesliga"), ("germany","dfb pokal"),
        ("france","ligue 1"), ("france","ligue 2"), ("france","coupe de france"),
        ("portugal","primeira liga"), ("portugal","taca de portugal"),
        ("netherlands","eredivisie"), ("netherlands","knvb beker"),
        ("belgium","jupiler pro league"),
        ("austria","bundesliga"),
        ("denmark","superligaen"),
        ("romania","liga i"),
        ("scotland","premiership"),
        ("switzerland","super league"),
        ("turkey","super lig"),
        ("world","uefa champions league"), ("world","uefa europa league"), ("world","uefa europa conference league"),
        ("world","fifa world cup"),
        ("south america","copa libertadores"), ("south america","copa sudamericana"),
        ("brazil","serie a"), ("argentina","liga profesional"), ("usa","mls")
    }

    # --- NUOVI default per i loop (mancavano) ---
    AUTOPILOT_TICK_SECONDS = int(os.getenv("AUTOPILOT_TICK_SECONDS", "30"))  # ogni 30s controlla planner/coda
    LIVE_POLL_SECONDS      = int(os.getenv("LIVE_POLL_SECONDS", "40"))       # ogni 40s loop live
