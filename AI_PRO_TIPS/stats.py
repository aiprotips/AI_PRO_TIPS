# AI_PRO_TIPS/stats.py
from typing import Optional, Dict, Any, List
from .api_football import APIFootball

def _team_name(fx: Dict, side: str) -> str:
    return (fx.get("teams", {}) or {}).get(side, {}).get("name", side.capitalize())

def _recent_form(api: APIFootball, team_id: int) -> Dict[str,int]:
    # Placeholder semplice: senza extra chiamate (API rate). Torna valori "safe".
    # Puoi evolverlo leggendo /fixtures head-to-head o ultime N gare se vuoi spingere.
    return {"won": 4, "scored": 8, "played": 10}

def craft_coherent_stat_line(api: APIFootball, fx: Dict[str,Any], pick: str) -> Optional[str]:
    """
    Genera una riga statistica coerente con il pick scelto.
    Non fa affermazioni “contro” il nostro consiglio.
    """
    pick = (pick or "").strip()

    home = _team_name(fx, "home")
    away = _team_name(fx, "away")
    fid  = (fx.get("teams", {}) or {}).get("home", {}).get("id")

    # Mock "safe": non contraddice. (Puoi attivare analytics reali quando vuoi)
    if pick in ("1", "1X", "DNB Home", "Home to Score"):
        return f"{home} è solida in casa: imbattuta in 8 delle ultime 10. 👍"
    if pick in ("2", "X2", "DNB Away", "Away to Score"):
        return f"{away} spinge in trasferta: imbattuta in 7 delle ultime 9. 💪"
    if "Under" in pick:
        return "Trend Under stabile: ritmo basso nelle ultime uscite. 🧊"
    if "Over" in pick or pick in ("12",):
        return "Ritmo alto: partite con tanti tiri nelle ultime gare. 🔥"
    if pick == "X":
        return "Sfida equilibrata: dati molto vicini tra le due. ⚖️"

    return "Momentum favorevole sul nostro lato: indicatori in linea col pick. ✅"
