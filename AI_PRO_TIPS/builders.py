from typing import List, Dict, Tuple, Optional
import random, json
from api_football import APIFootball
from util import json_dumps
from repo import cache_upsert_fixture
from config import Config

PRIORITY = ["1X", "Over 0.5", "Under 3.5", "DNB Home", "Home to Score", "Away to Score", "12", "1", "X2", "2"]

def pick_safe_market(markets: Dict[str, float], lo: float, hi: float) -> Optional[Tuple[str, float]]:
    for k in PRIORITY:
        if k in markets:
            odd = markets[k]
            if lo <= odd <= hi:
                return (k, odd)
    return None

def _allowed(fixt: Dict, cfg: Config) -> bool:
    if not cfg.ALLOWED_LEAGUES: return True
    lg = fixt.get("league",{}).get("id")
    return lg in cfg.ALLOWED_LEAGUES

def fixtures_allowed_today(api: APIFootball, date_str: str, cfg: Config) -> List[Dict]:
    fixtures = api.fixtures_by_date(date_str)
    out = []
    for f in fixtures:
        st = (f.get("fixture",{}).get("status",{}) or {}).get("short")
        if st not in ("NS","TBD"): 
            continue
        if _allowed(f, cfg):
            out.append(f)
    return out

def build_combo_with_range(api: APIFootball, date_str: str, legs: int, lo: float, hi: float, cfg: Config):
    fixtures = fixtures_allowed_today(api, date_str, cfg)
    if not fixtures: return None
    random.shuffle(fixtures)
    combo = []
    used_ids = set()
    for fx in fixtures:
        info = fx.get("fixture", {})
        teams = fx.get("teams", {})
        fid = int(info.get("id"))
        if fid in used_ids: 
            continue
        try:
            odds = api.odds_by_fixture(fid)
        except Exception:
            continue
        mk = api.parse_markets(odds)
        pick = pick_safe_market(mk, lo, hi)
        if not pick: 
            continue
        market, odd = pick
        home = teams.get("home",{}).get("name","Home")
        away = teams.get("away",{}).get("name","Away")
        league_id = fx.get("league",{}).get("id") or 0
        start_time = info.get("date")
        combo.append({
            "fixture_id": fid, "league_id": int(league_id or 0),
            "start_time": start_time, "home": home, "away": away,
            "market": market, "pick": market, "odds": float(odd)
        })
        used_ids.add(fid)
        cache_upsert_fixture(fid, int(league_id or 0), start_time, "NS", home, away, json_dumps(mk))
        if len(combo) == legs:
            break
    return combo if len(combo) == legs else None

def build_value_single(api: APIFootball, date_str: str, cfg: Config) -> Optional[Dict]:
    """Singola tra 1.50–1.80 su mercati stabili."""
    fixtures = fixtures_allowed_today(api, date_str, cfg)
    if not fixtures: return None
    random.shuffle(fixtures)
    for fx in fixtures:
        info = fx.get("fixture", {})
        fid = int(info.get("id"))
        try:
            odds = api.odds_by_fixture(fid)
        except Exception:
            continue
        mk = api.parse_markets(odds)
        for m in ("1", "1X", "Under 3.5", "Over 0.5", "12", "DNB Home", "Home to Score", "Away to Score", "X2", "2"):
            if m in mk and 1.50 <= mk[m] <= 1.80:
                teams = fx.get("teams", {})
                home = teams.get("home",{}).get("name","Home")
                away = teams.get("away",{}).get("name","Away")
                league_id = fx.get("league",{}).get("id") or 0
                start_time = info.get("date")
                return {
                    "fixture_id": fid, "league_id": int(league_id or 0),
                    "start_time": start_time, "home": home, "away": away,
                    "market": m, "pick": m, "odds": float(mk[m])
                }
    return None
