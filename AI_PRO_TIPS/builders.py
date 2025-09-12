import random
from datetime import timedelta
from zoneinfo import ZoneInfo

from .config import Config
from .api_football import APIFootball
from .util import parse_dt

def _norm(s: str) -> str:
    return (s or "").lower().strip()

def _allowed_league(league: dict, cfg: Config) -> bool:
    name = _norm(league.get("name"))
    country = _norm(league.get("country"))
    key = (country, name)
    return key in cfg.ALLOWED_COMP_NAMES

def _within_day_window_local(dt_aware, tz: str, start_h: int = 8, end_h: int = 24) -> bool:
    if dt_aware is None:
        return False
    local = dt_aware.astimezone(ZoneInfo(tz))
    h = local.hour + local.minute / 60.0
    return (start_h <= h) and (h < end_h)

def _format_kickoff_local(iso_dt: str, tz: str) -> str:
    try:
        dt = parse_dt(iso_dt)
        local = dt.astimezone(ZoneInfo(tz))
        return local.strftime("%H:%M")
    except Exception:
        return "n/d"

def _parse_bet365_markets(api: APIFootball, fixture_id: int) -> dict:
    odds_resp = api.odds_by_fixture(fixture_id)
    return api.parse_markets_bet365(odds_resp)

_PREFERRED_ORDER = (
    "1X", "X2", "12",
    "Under 3.5", "Over 0.5",
    "DNB Home",
    "Home to Score", "Away to Score",
    "1", "2",
    "Gol", "No Gol"  # <-- rinominati da "BTTS Yes","BTTS No"
)

def fixtures_allowed_today(api: APIFootball, date: str, cfg: Config):
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

def _choose_market_from_bet365(api: APIFootball, fx: dict) -> dict:
    fid = int((fx.get("fixture", {}) or {}).get("id") or 0)
    mk = _parse_bet365_markets(api, fid)
    if not mk: return {}
    candidates = [(m, float(mk[m])) for m in _PREFERRED_ORDER if m in mk]
    if not candidates: return {}
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

# --- NUOVO: scelta di un mercato SOLO se la quota reale è entro il range richiesto ---
def _pick_market_in_range(api: APIFootball, fx: dict, lo: float, hi: float) -> dict:
    """
    Ritorna un dict standardizzato (come _choose_market_from_bet365) ma
    SOLO se trova un mercato Bet365 con quota reale dentro [lo, hi].
    Altrimenti {}.
    """
    fid = int((fx.get("fixture", {}) or {}).get("id") or 0)
    mk = _parse_bet365_markets(api, fid)
    if not mk:
        return {}

    # Cerca in ordine di priorità mercati la cui quota è nel range
    for m in _PREFERRED_ORDER:
        if m in mk:
            try:
                odd = float(mk[m])
            except Exception:
                continue
            if lo <= odd <= hi:
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
                    "market": m,
                    "pick": m,
                    "odds": odd,
                    "start_time": start_time,
                    "kickoff_local": _format_kickoff_local(start_time, api.tz)
                }

    # Nessun mercato nel range
    return {}

def build_value_single(api: APIFootball, date: str, cfg: Config, used_fixtures: set) -> dict:
    fixtures = fixtures_allowed_today(api, date, cfg)
    random.shuffle(fixtures)
    for fx in fixtures:
        fid = int((fx.get("fixture", {}) or {}).get("id") or 0)
        if fid in used_fixtures: continue
        # SOLO quote reali tra 1.50 e 1.80
        sel = _pick_market_in_range(api, fx, 1.50, 1.80)
        if not sel: continue
        used_fixtures.add(fid)
        return sel
    return {}

def build_combo_with_range(api: APIFootball, date: str, legs: int, lo: float, hi: float, cfg: Config, used_fixtures: set):
    fixtures = fixtures_allowed_today(api, date, cfg)
    fixtures.sort(key=lambda f: (f.get("fixture", {}) or {}).get("date"))
    out = []; tried=set()
    for fx in fixtures:
        if len(out) >= legs: break
        fid = int((fx.get("fixture", {}) or {}).get("id") or 0)
        if fid in used_fixtures or fid in tried: continue
        # SOLO quote reali nel range [lo, hi]
        sel = _pick_market_in_range(api, fx, lo, hi)
        if not sel: tried.add(fid); continue
        used_fixtures.add(fid); out.append(sel)
    if len(out) < legs:
        if len(out) >= 2: return out
        return []
    return out

def calc_send_at_for_combo(combo: list, tz: str):
    from dateutil import parser as duparser
    if not combo: return None
    min_iso = min(c["start_time"] for c in combo)
    dt_aware = duparser.isoparse(min_iso)
    local = dt_aware.astimezone(ZoneInfo(tz))
    send_local = local - timedelta(hours=3)
    clamp = local.replace(hour=8, minute=0, second=0, microsecond=0)
    if send_local.hour < 8: send_local = clamp
    return send_local.astimezone(ZoneInfo("UTC"))
