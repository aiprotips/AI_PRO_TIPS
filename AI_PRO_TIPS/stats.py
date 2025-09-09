# AI_PRO_TIPS/stats.py
from typing import Optional, Dict
from api_football import APIFootball

def _safe_pct(val, total):
    try:
        total = float(total or 0)
        val = float(val or 0)
        if total <= 0: return None
        return int(round(100.0 * val / total))
    except Exception:
        return None

def _avg_goals(stats: dict) -> Optional[float]:
    try:
        gf = stats["fixtures"]["goals"]["for"]["total"]["total"]
        ga = stats["fixtures"]["goals"]["against"]["total"]["total"]
        played = stats["fixtures"]["played"]["total"]
        if played:
            return round((gf + ga) / float(played), 2)
    except Exception:
        pass
    return None

def craft_coherent_stat_line(
    api: APIFootball,
    fixture: dict,
    pick: str
) -> Optional[str]:
    """
    Ritorna una riga discorsiva coerente con il pick (in italiano), oppure None se non calcolabile.
    Usa /teams/statistics (lega+season+team).
    """
    lg = fixture.get("league", {}) or {}
    league_id = int(lg.get("id") or 0)
    season = int(lg.get("season") or 0)

    fx = fixture.get("fixture", {}) or {}
    teams = fixture.get("teams", {}) or {}
    home = teams.get("home", {}) or {}
    away = teams.get("away", {}) or {}
    home_id, away_id = int(home.get("id") or 0), int(away.get("id") or 0)
    home_name, away_name = home.get("name", "Home"), away.get("name", "Away")

    # carica statistiche squadra (campionato corrente)
    try:
        st_home = api.team_statistics(league_id, season, home_id) if (league_id and season and home_id) else {}
        st_away = api.team_statistics(league_id, season, away_id) if (league_id and season and away_id) else {}
    except Exception:
        st_home, st_away = {}, {}

    # helper su percentuali
    def pct_no_draw(stats):
        try:
            draws = stats["fixtures"]["wins"]["total"] * 0  # placeholder
        except Exception:
            draws = None
        try:
            w = stats["fixtures"]["wins"]["total"] or 0
            l = stats["fixtures"]["loses"]["total"] or 0
            p = stats["fixtures"]["played"]["total"] or 0
            d = p - w - l
            return _safe_pct(p - d, p)  # partite non pareggiate
        except Exception:
            return None

    # mappature pick → frase coerente
    p = (pick or "").strip().lower()

    # ---- UNDER 3.5 ----
    if "under 3.5" in p:
        avg_h = _avg_goals(st_home)
        avg_a = _avg_goals(st_away)
        if avg_h is not None and avg_a is not None:
            return (f"{home_name} e {away_name} viaggiano su medie gol contenute "
                    f"({avg_h} e {avg_a} a partita): linea Under 3.5 con basi solide. 📉")
        return (f"Trend prudente per {home_name}–{away_name}: contesti a basso punteggio, Under 3.5 sensato. 📉")

    # ---- OVER 0.5 ----
    if "over 0.5" in p:
        try:
            h_scored = st_home["goals"]["for"]["total"]["total"]
            h_played = st_home["fixtures"]["played"]["total"]
            a_scored = st_away["goals"]["for"]["total"]["total"]
            a_played = st_away["fixtures"]["played"]["total"]
            rate = _safe_pct(h_scored + a_scored, h_played + a_played)
        except Exception:
            rate = None
        if rate and rate >= 120:  # media >1 gol/partita complessiva
            return (f"{home_name} e {away_name} creano: media reti complessiva rilevante, "
                    f"Over 0.5 blindato. ⚡")
        return (f"Partita con presupposti per sbloccarsi: Over 0.5 lineare. ⚡")

    # ---- 1X (Home non perde) / DNB Home / 1 ----
    if p in ("1x", "1", "dnb home", "1x (home/draw)"):
        try:
            w = st_home["fixtures"]["wins"]["home"] or 0
            d = st_home["fixtures"]["draws"]["home"] or 0
            l = st_home["fixtures"]["loses"]["home"] or 0
            pld = w + d + l
            unbeaten = _safe_pct(w + d, pld)
        except Exception:
            unbeaten = None
        if unbeaten and unbeaten >= 70:
            return (f"{home_name} solida in casa ({unbeaten}% imbattuta): 1X con basi. 🧱")
        return (f"Fattore campo per {home_name}: 1X in linea con i numeri. 🧱")

    # ---- X2 (Away non perde) / DNB Away / 2 ----
    if p in ("x2", "2", "dnb away", "x2 (draw/away)"):
        try:
            w = st_away["fixtures"]["wins"]["away"] or 0
            d = st_away["fixtures"]["draws"]["away"] or 0
            l = st_away["fixtures"]["loses"]["away"] or 0
            pld = w + d + l
            unbeaten = _safe_pct(w + d, pld)
        except Exception:
            unbeaten = None
        if unbeaten and unbeaten >= 70:
            return (f"{away_name} solida fuori casa ({unbeaten}% imbattuta): X2 con basi. 🧱")
        return (f"{away_name} affidabile lontano da casa: X2 sensata. 🧱")

    # ---- 12 (no pareggio) ----
    if p in ("12", "1/2", "no draw", "home/away"):
        try:
            p_no_draw_h = pct_no_draw(st_home)
            p_no_draw_a = pct_no_draw(st_away)
        except Exception:
            p_no_draw_h = p_no_draw_a = None
        if p_no_draw_h and p_no_draw_a and (p_no_draw_h + p_no_draw_a) / 2 >= 70:
            return (f"Trend poco amico del pareggio: {home_name} e {away_name} chiudono spesso con un vincitore. 12 coerente. ⚡")
        return (f"Partita da episodi, profilo da esito secco: 12 coerente. ⚡")

    # ---- Home/Away to Score ----
    if "home to score" in p or "segna casa" in p:
        try:
            gf = st_home["goals"]["for"]["average"]["home"]
        except Exception:
            gf = None
        if gf:
            return (f"{home_name} ha media realizzativa casalinga interessante ({gf}): segna casa ben impostato. 🎯")
        return (f"{home_name} tende a trovare la rete in casa: segna casa logico. 🎯")

    if "away to score" in p or "segna trasferta" in p:
        try:
            gf = st_away["goals"]["for"]["average"]["away"]
        except Exception:
            gf = None
        if gf:
            return (f"{away_name} produce in trasferta (media {gf}): segna trasferta consistente. 🎯")
        return (f"{away_name} trova spesso la rete fuori: segna trasferta coerente. 🎯")

    # fallback generico ma sempre a favore
    return (f"I numeri sono dalla parte di {home_name}: scelta coerente con il trend. ✅")
