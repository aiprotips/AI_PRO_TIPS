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
    # Il bot non invia contenuti tra 00:00 e 07:59 locali
    QUIET_HOURS = (0, 8)  # (start_hour, end_hour)

    # --- Piano giornaliero (minimo garantito, il resto degrada in automatico) ---
    DAILY_PLAN = {
        "value_singles": 2,  # due singole value (1.50–1.80)
        "combos": [
            {"legs": 2,    "leg_lo": 1.30, "leg_hi": 1.50},  # doppia
            {"legs": 3,    "leg_lo": 1.20, "leg_hi": 1.50},  # tripla
            {"legs": 5,    "leg_lo": 1.20, "leg_hi": 1.50},  # quintupla
            {"legs": "8-12","leg_lo": 1.10, "leg_hi": 1.36},  # super combo lunga
        ],
        "random_content": {
            "stat_flash_per_day": 2,  # statistiche lampo discorsive (coerenti col pick)
            "story_per_day": 2,       # storytelling lunghi (3–4 frasi) legati a match in schedina
            "banter_per_day": 2       # one-liner positivi
        }
    }

    # --- Whitelist competizioni (per nome/country normalizzati) ---
    # Nota: lavoriamo per (country,name) per evitare ID ballerini. Se vuoi passare a ID fissi API-Football, lo faremo più avanti.
    ALLOWED_COMP_NAMES = {
        # Italia
        ("italy","serie a"), ("italy","serie b"), ("italy","serie c"), ("italy","coppa italia"),
        # Inghilterra
        ("england","premier league"), ("england","championship"), ("england","fa cup"), ("england","efl cup"),
        # Spagna
        ("spain","la liga"), ("spain","laliga"), ("spain","laliga 2"), ("spain","segunda division"), ("spain","copa del rey"),
        # Germania
        ("germany","bundesliga"), ("germany","2. bundesliga"), ("germany","dfb pokal"),
        # Francia
        ("france","ligue 1"), ("france","ligue 2"), ("france","coupe de france"),
        # Portogallo
        ("portugal","primeira liga"), ("portugal","taca de portugal"),
        # Olanda
        ("netherlands","eredivisie"), ("netherlands","knvb beker"),
        # Belgio
        ("belgium","jupiler pro league"), ("belgium","pro league"), ("belgium","croky cup"),
        # Austria
        ("austria","bundesliga"), ("austria","ofb-cup"),
        # Danimarca
        ("denmark","superligaen"), ("denmark","dbu pokalen"),
        # Romania
        ("romania","liga i"), ("romania","cup"),
        # Scozia
        ("scotland","premiership"), ("scotland","scottish cup"), ("scotland","league cup"),
        # Svizzera
        ("switzerland","super league"), ("switzerland","schweizer cup"),
        # Turchia
        ("turkey","super lig"), ("turkey","turkiye kupasi"),
        # Coppe europee
        ("world","uefa champions league"), ("world","uefa europa league"), ("world","uefa europa conference league"),
        # Mondiali
        ("world","fifa world cup"),
        # Sudamerica
        ("south america","copa libertadores"), ("south america","copa sudamericana"),
        # Extra consigliati
        ("brazil","serie a"), ("brazil","copa do brasil"),
        ("argentina","liga profesional"), ("argentina","copa argentina"),
        ("usa","mls")
    }
