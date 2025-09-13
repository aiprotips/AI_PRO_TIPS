# Whitelist dei campionati con matching robusto (case-insensitive, substring).
from typing import Tuple

def _norm(s: str) -> str:
    return (s or "").strip().lower()

def allowed_league(country: str, name: str) -> bool:
    c = _norm(country)
    n = _norm(name)

    # ITALIA
    if c == "italy":
        if any(x in n for x in ["serie a","serie-a","seria a","seria-a"]): return True
        if any(x in n for x in ["serie b","serie-b","seria b","seria-b"]): return True
        if "serie c" in n or "serie-c" in n: return True
        if "coppa italia" in n: return True

    # INGHILTERRA
    if c == "england":
        if "premier" in n: return True
        if "championship" in n: return True
        if "fa cup" in n: return True
        if "efl cup" in n or "carabao" in n or "league cup" in n: return True

    # SPAGNA
    if c == "spain":
        if "la liga" in n or "laliga" in n: return True
        if "la liga 2" in n or "laliga2" in n or "segunda" in n: return True
        if "copa del rey" in n or "coppa spagnola" in n: return True

    # GERMANIA
    if c == "germany":
        if "bundesliga 2" in n or "2. bundesliga" in n or "bundesliga2" in n: return True
        if "bundesliga" in n: return True
        if "dfb-pokal" in n or "dfb pokal" in n or "coppa tedesca" in n: return True

    # FRANCIA
    if c == "france":
        if "ligue 1" in n: return True
        if "ligue 2" in n: return True
        if "coupe de france" in n or "coppa" in n: return True

    # PORTOGALLO
    if c == "portugal":
        if "primeira liga" in n or "liga portugal" in n: return True
        if "taca de portugal" in n or "taça de portugal" in n or "coppa" in n: return True

    # OLANDA
    if c in ("netherlands","holland"):
        if "eredivisie" in n: return True
        if "knvb beker" in n or "beker" in n or "coppa" in n: return True

    # BELGIO
    if c == "belgium":
        if "pro league" in n or "jupiler" in n: return True

    # AUSTRIA
    if c == "austria":
        if "bundesliga" in n: return True

    # DANIMARCA
    if c == "denmark":
        if "superliga" in n: return True

    # ROMANIA
    if c == "romania":
        if "liga 1" in n or "liga i" in n or "superliga" in n: return True

    # SCOZIA
    if c == "scotland":
        if "premiership" in n or "premier" in n: return True

    # SVIZZERA
    if c in ("switzerland","swiss"):
        if "super league" in n: return True

    # TURCHIA
    if c == "turkey":
        if "super lig" in n or "süper lig" in n: return True

    # EUROPEE (UEFA)
    if c in ("europe","world","uefa"):
        if any(x in n for x in ["champions league","uefa champions"]): return True
        if any(x in n for x in ["europa league","uefa europa"]): return True
        if any(x in n for x in ["conference league","uefa europa conference"]): return True
        if any(x in n for x in ["uefa super cup","supercoppa uefa"]): return True

    # MONDIALI
    if c in ("world","fifa"):
        if "world cup" in n or "mondiale" in n: return True

    # SUD AMERICA
    if c in ("south america","conmebol","world"):
        if any(x in n for x in ["copa libertadores","libertadores"]): return True
        if any(x in n for x in ["copa sudamericana","sudamericana","coppa sudamerica"]): return True

    return False

def label_league(country: str, name: str) -> str:
    return f"{country} — {name}"
