import random
from datetime import timedelta
from zoneinfo import ZoneInfo

from .config import Config
from .api_football import APIFootball
from .util import parse_dt


# -----------------------------
# Helpers filtro leghe/orari
# -----------------------------

def _norm(s: str) -> str:
    return (s or "").lower().strip()

def _allowed_league(league: dict, cfg: Config) -> bool:
    """
    Verifica che la competizione sia nella whitelist per (country, name).
    """
    name = _norm(league.get("name"))
    country = _norm(league.get("country"))
    key = (country, name)
    return key in cfg.ALLOWED_COMP_NAMES

def _within_day_window_local(dt_aware, tz: str, start_h: int = 8, end_h: int = 24) -> bool:
    """
    True se l'orario locale del fixture è compreso tra start_h e end_h (24 escluso).
    """
    if dt_aware is None:
        return False
    local = dt_aware.astimezone(ZoneInfo(tz))
    h = local.hour + local.minute / 60.0
    return (start_h <= h) and (h < end_h)

def _format_kickoff_local(iso_dt: str, tz: str) -> str:
    """
    Formatta l'orario di kickoff in locale (HH:MM).
    """
    try:
        dt = parse_dt(iso_dt)
        local = dt.astimezone(ZoneInfo(tz))
        return local.strftime("%H:%M")
    except Exception:
        return "n/d"


# -----------------------------
# API wrapper per Bet365 markets
# -----------------------------

def _parse_bet365_markets(api: APIFootball, fixture_id: int) -> dict:
    """
    Ritorna mappa market -> quota (float) usando SOLO Bet365.
    """
    odds_resp = api.odds_by_fixture(fixture_id)
    return api.parse_markets_bet365(odds_resp)


# -----------------------------
# Costruzione lista fixture idonei (oggi)
# -----------------------------

def fixtures_allowed_today(api: APIFootball, date: str, cfg: Config):
    """
    Elenca i fixtures della data (self.tz) che:
      - appartengono a leghe whitelist (country/name)
      - hanno orario locale compreso tra 08:00 e 24:00
    """
    tz = cfg.TZ
    all_fx = api.fixtures_by_date(date)
    out = []
    for fx in all_fx:
        league = fx.get("league", {}) or {}
        if not _allowed_league(league, cfg):
            continue

        iso = (fx.get("fixture", {}) or {}).get("date")
        dt = parse_dt(iso)
        if not dt:
            continue
        if not _within_day_window_local(dt, tz, start_h=8, end_h=24):
            continue

        out.append(fx)

    return out


# -----------------------------
# Scelta mercati/quote (varietà + range)
# -----------------------------

_PREFERRED_ORDER = (
    "1X", "X2", "12",
    "Under 3.5", "Over 0.5",
    "DNB Home",
    "Home to Score", "Away to Score",
    "1", "2",
    "BTTS Yes", "BTTS No"
)

def _choose_market_from_bet365(api: APIFootball, fx: dict) -> dict:
    """
    Sceglie UN mercato “safe” con quota Bet365 e ritorna un dict standardizzato:
      {fixture_id, league_id, home, away, market, pick, odds, start_time, kickoff_local}
    Varietà: shuffla i mercati preferiti e sceglie il più vicino a ~1.35–1.50 per non essere monotoni.
    """
    fid = int((fx.get("fixture", {}) or {}).get("id") or 0)
    mk = _parse_bet365_markets(api, fid)
    if not mk:
        return {}

    # costruisci lista candidati disponibili
    candidates = [(m, float(mk[m])) for m in _PREFERRED_ORDER if m in mk]
    if not candidates:
        return {}

    # shuffla per variare, poi prendi quello con odds più vicina a 1.40 (centro fascia)
    random.shuffle(candidates)
    market, odds = min(candidates, key=lambda t: abs(t[1] - 1.40))

    teams = fx.get("teams", {}) or {}
    home = teams.get("home", {}).get("name", "Home")
    away = teams.get("away", {}).get("name", "Away")
    league_id = int((fx.get("league", {}) or {}).get("id") or 0)
    start_time = (fx.get("fixture", {}) or {}).get("date")

    return {
        "fixture_id": fid,
        "league_id": league_id,
        "home": home,
        "away": away,
        "market": market,
        "pick": market,
        "odds": float(odds),
        "start_time": start_time,
        "kickoff_local": _format_kickoff_local(start_time, api.tz)
    }


# -----------------------------
# Singole (value) e multiple
# -----------------------------

def build_value_single(api: APIFootball, date: str, cfg: Config, used_fixtures: set) -> dict:
    """
    Ritorna una singola in range 1.50–1.80 (Bet365 only), rispettando il dedup su used_fixtures.
    """
    fixtures = fixtures_allowed_today(api, date, cfg)
    random.shuffle(fixtures)

    for fx in fixtures:
        fid = int((fx.get("fixture", {}) or {}).get("id") or 0)
        if fid in used_fixtures:
            continue

        sel = _choose_market_from_bet365(api, fx)
        if not sel:
            continue

        if 1.50 <= sel["odds"] <= 1.80:
            used_fixtures.add(fid)
            return sel

    return {}


def build_combo_with_range(api: APIFootball, date: str, legs: int, lo: float, hi: float,
                           cfg: Config, used_fixtures: set):
    """
    Costruisce una multipla con 'legs' eventi, con ciascuna quota in [lo, hi].
    Se non trova abbastanza leg:
      - se >= 2 leg, ritorna la multipla più corta disponibile (degradazione)
      - altrimenti ritorna lista vuota
    Ritorna lista di dict come quelli di _choose_market_from_bet365.
    """
    fixtures = fixtures_allowed_today(api, date, cfg)
    # ordina per kickoff per avere un invio coerente con T-3h
    fixtures.sort(key=lambda f: (f.get("fixture", {}) or {}).get("date"))

    out = []
    tried = set()

    for fx in fixtures:
        if len(out) >= legs:
            break

        fid = int((fx.get("fixture", {}) or {}).get("id") or 0)
        if fid in used_fixtures or fid in tried:
            continue

        sel = _choose_market_from_bet365(api, fx)
        if not sel:
            tried.add(fid)
            continue

        if lo <= sel["odds"] <= hi:
            used_fixtures.add(fid)
            out.append(sel)

    if len(out) < legs:
        # degrada se almeno 2 leg (altrimenti vuoto)
        if len(out) >= 2:
            return out
        return []

    return out


# -----------------------------
# Calcolo orario invio T-3h
# -----------------------------

def calc_send_at_for_combo(combo: list, tz: str):
    """
    Ritorna il datetime (aware, UTC) dell'orario di invio:
      send_at = max(minKickoffLocal - 3h, oggi 08:00 local)
    Se combo ha un solo elemento, usa il suo kickoff.
    """
    from dateutil import parser as duparser
    from datetime import datetime
    if not combo:
        return None

    # trova il kickoff più vicino all'interno della combo
    min_iso = min(c["start_time"] for c in combo)
    dt_aware = duparser.isoparse(min_iso)

    # calcola T-3h in locale
    local = dt_aware.astimezone(ZoneInfo(tz))
    send_local = local - timedelta(hours=3)

    # clamp a 08:00 locali
    clamp = local.replace(hour=8, minute=0, second=0, microsecond=0)
    if send_local.hour < 8:
        send_local = clamp

    # ritorna in UTC (aware)
    return send_local.astimezone(ZoneInfo("UTC"))
