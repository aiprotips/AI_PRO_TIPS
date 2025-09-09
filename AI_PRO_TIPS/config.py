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

    # Leghe consentite
    ALLOWED_LEAGUES = [
        # Italia
        135,   # Serie A
        136,   # Serie B
        137,   # Serie C
        318,   # Coppa Italia

        # Inghilterra
        39,    # Premier League
        40,    # Championship
        45,    # FA Cup
        46,    # EFL Cup

        # Spagna
        140,   # La Liga
        141,   # La Liga 2
        143,   # Copa del Rey

        # Germania
        78,    # Bundesliga
        79,    # 2. Bundesliga
        81,    # DFB Pokal

        # Francia
        61,    # Ligue 1
        62,    # Ligue 2
        66,    # Coupe de France

        # Portogallo
        94,    # Primeira Liga
        96,    # Taça de Portugal

        # Olanda
        88,    # Eredivisie
        90,    # KNVB Beker

        # Belgio
        144,   # Jupiler Pro League

        # Austria
        218,   # Bundesliga

        # Danimarca
        103,   # Superligaen

        # Romania
        283,   # Liga I

        # Scozia
        179,   # Premiership

        # Svizzera
        207,   # Super League

        # Turchia
        203,   # Super Lig

        # Competizioni internazionali
        2,     # UEFA Champions League
        3,     # UEFA Europa League
        848,   # Conference League
        4,     # World Cup
        10,    # Copa Libertadores
        11,    # Copa Sudamericana

        # Extra consigliati
        71,    # Brasile Serie A
        128,   # Argentina Primera Division
        253,   # MLS (USA)
    ]
