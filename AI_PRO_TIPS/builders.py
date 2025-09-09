from typing import List, Dict, Tuple, Optional
from datetime import datetime
import random
from api_football import APIFootball
from util import json_dumps
from repo import cache_upsert_fixture

# Market priority for safe picks
PRIORITY = ["1X", "Over 0.5", "Under 3.5", "DNB Home", "Home to Score", "Away to Score", "12", "1"]

def pick_safe_market(markets: Dict[str, float], lo: float, hi: float) -> Optional[Tuple[str, float]]:
    for k in PRIORITY:
        if k in markets:
            odd = markets[k]
            if lo <= odd <= hi:
                return (k, odd)
    return None

def build_safe_combo_for_date(api: APIFootball, date_str: str, legs: int, lo: float, hi: float):
    fixtures = api.fixtures_by_date(date_str)
    if not fixtures:
        return None
    random.shuffle(fixtures)
    combo = []
    used_ids = set()
    for fx in fixtures:
        info = fx.get("fixture", {})
        teams = fx.get("teams", {})
        status_short = (info.get("status",{}) or {}).get("short") or "NS"
        if not info or status_short not in ("NS","TBD"):
            continue
        fid = int(info.get("id"))
        if fid in used_ids:
            continue
        # odds for fixture
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
        })  # pick label == market for normalized markets
        used_ids.add(fid)

        # cache basic fixture & odds (to aid live + favorite)
        cache_upsert_fixture(fid, int(league_id or 0), start_time, "NS", home, away, json_dumps(mk))

        if len(combo) == legs:
            break
    return combo if len(combo) == legs else None
