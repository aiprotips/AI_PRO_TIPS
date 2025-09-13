def _norm(s: str) -> str:
    return (s or "").strip().lower()

# alias comuni → nome canonico
_ALIAS = {
    # Italy
    "serie a": "serie a",
    "serie b": "serie b",
    "serie c": "serie c",
    "coppa italia": "coppa italia",

    # England
    "premier league": "premier league",
    "championship": "championship",
    "fa cup": "fa cup",
    "efl cup": "efl cup",
    "carabao cup": "efl cup",

    # Spain
    "la liga": "la liga",
    "laliga": "la liga",
    "la liga 2": "la liga 2",
    "laliga2": "la liga 2",
    "segunda division": "la liga 2",
    "copa del rey": "copa del rey",

    # Germany
    "bundesliga": "bundesliga",
    "2. bundesliga": "2. bundesliga",
    "2 bundesliga": "2. bundesliga",
    "dfb pokal": "dfb pokal",

    # France
    "ligue 1": "ligue 1",
    "ligue1": "ligue 1",
    "ligue 2": "ligue 2",
    "ligue2": "ligue 2",
    "coupe de france": "coupe de france",

    # Portugal
    "primeira liga": "primeira liga",
    "liga portugal": "primeira liga",
    "taca de portugal": "taca de portugal",
    "taça de portugal": "taca de portugal",

    # Netherlands
    "eredivisie": "eredivisie",
    "knvb beker": "knvb beker",

    # Belgium
    "jupiler pro league": "jupiler pro league",
    "pro league": "jupiler pro league",

    # Austria
    "austria bundesliga": "austria bundesliga",
    "bundesliga": "bundesliga",  # disambiguato via country

    # Denmark
    "superliga": "superliga",
    "superligaen": "superliga",

    # Romania
    "liga 1": "liga 1",
    "liga i": "liga 1",

    # Scotland
    "premiership": "premiership",
    "scottish premiership": "premiership",

    # Switzerland
    "super league": "super league",

    # Turkey
    "super lig": "super lig",
    "süper lig": "super lig",

    # UEFA / International
    "uefa champions league": "uefa champions league",
    "champions league": "uefa champions league",
    "uefa europa league": "uefa europa league",
    "europa league": "uefa europa league",
    "uefa europa conference league": "uefa europa conference league",
    "europa conference league": "uefa europa conference league",

    # World / International
    "fifa world cup": "fifa world cup",
    "world cup": "fifa world cup",

    # South America
    "copa libertadores": "copa libertadores",
    "copa sudamericana": "copa sudamericana",
}

_ALLOWED = set([
    # Italy
    ("italy", "serie a"),
    ("italy", "serie b"),
    ("italy", "serie c"),
    ("italy", "coppa italia"),

    # England
    ("england", "premier league"),
    ("england", "championship"),
    ("england", "fa cup"),
    ("england", "efl cup"),

    # Spain
    ("spain", "la liga"),
    ("spain", "la liga 2"),
    ("spain", "copa del rey"),

    # Germany
    ("germany", "bundesliga"),
    ("germany", "2. bundesliga"),
    ("germany", "dfb pokal"),

    # France
    ("france", "ligue 1"),
    ("france", "ligue 2"),
    ("france", "coupe de france"),

    # Portugal
    ("portugal", "primeira liga"),
    ("portugal", "taca de portugal"),

    # Netherlands
    ("netherlands", "eredivisie"),
    ("netherlands", "knvb beker"),

    # Belgium
    ("belgium", "jupiler pro league"),

    # Austria
    ("austria", "austria bundesliga"),

    # Denmark
    ("denmark", "superliga"),

    # Romania
    ("romania", "liga 1"),

    # Scotland
    ("scotland", "premiership"),

    # Switzerland
    ("switzerland", "super league"),

    # Turkey
    ("turkey", "super lig"),

    # UEFA / International / World / CONMEBOL (spesso country='World' in API-Football)
    (None, "uefa champions league"),
    (None, "uefa europa league"),
    (None, "uefa europa conference league"),
    (None, "fifa world cup"),
    (None, "copa libertadores"),
    (None, "copa sudamericana"),
])

def _canon(name: str) -> str:
    n = _norm(name)
    return _ALIAS.get(n, n)

def allowed_league(country: str, name: str) -> bool:
    c = _norm(country)
    n = _canon(name)
    if (c, n) in _ALLOWED:
        return True
    if (None, n) in _ALLOWED and c in ("world", "international", "europe", "uefa", "south america", "conmebol"):
        return True
    # disambiguazione 'bundesliga' austriaca
    if n == "bundesliga" and c == "austria":
        n = "austria bundesliga"
        return (c, n) in _ALLOWED
    return False

def label_league(country: str, name: str) -> str:
    c = (country or "Unknown").strip()
    n = _canon(name or "Unknown")
    return f"{c} — {n}"
