# app/stats_engine.py
from __future__ import annotations
from typing import Dict, Any, List, Tuple
from functools import lru_cache
from statistics import mean

# Questo modulo usa SOLO api._get(...) del tuo APIFootball
# per non toccare la logica consolidata.

def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else (hi if x > hi else x)

def _wld_points_for_team(fx: Dict[str, Any], team_id: int) -> int:
    """Calcola punti (3/1/0) per il team_id dato in un fixture concluso."""
    try:
        t_home = fx["teams"]["home"]["id"]
        g_home = int(fx["goals"]["home"] or 0)
        g_away = int(fx["goals"]["away"] or 0)
        if team_id == t_home:
            if g_home > g_away: return 3
            if g_home == g_away: return 1
            return 0
        else:
            if g_away > g_home: return 3
            if g_away == g_home: return 1
            return 0
    except Exception:
        return 0

def _team_goals_in_fx(fx: Dict[str, Any], team_id: int) -> Tuple[int, int]:
    try:
        t_home = fx["teams"]["home"]["id"]
        gh = int(fx["goals"]["home"] or 0)
        ga = int(fx["goals"]["away"] or 0)
        if team_id == t_home:
            return gh, ga
        else:
            return ga, gh
    except Exception:
        return 0, 0

class StatsEngine:
    """
    Recupera e compatta statistiche 'essenziali' per un match:
    - medie GF/GA, totali, %Over1.5/2.5/%Under3.5
    - %BTTS (Gol), %CleanSheet
    - forma (ultime 5: punti/partita)
    Tutto in RAM (cache), senza toccare il tuo api_football.
    """

    def __init__(self, api, league_scope_same_league: bool = True):
        self.api = api
        self.same_league = league_scope_same_league
        self._fx_cache: Dict[int, Dict[str, Any]] = {}
        self._team_last_cache: Dict[Tuple[int, int, int, int], List[Dict[str, Any]]] = {}
        # chiave: (team_id, league_id, season, last)

    def _get_fixture(self, fixture_id: int) -> Dict[str, Any]:
        if fixture_id in self._fx_cache:
            return self._fx_cache[fixture_id]
        js = self.api._get("/fixtures", {"id": fixture_id})
        arr = js.get("response", []) or []
        fx = arr[0] if arr else {}
        self._fx_cache[fixture_id] = fx
        return fx

    def _get_team_last(self, team_id: int, league_id: int, season: int, last: int = 10) -> List[Dict[str, Any]]:
        key = (team_id, league_id if self.same_league else -1, season if self.same_league else -1, last)
        if key in self._team_last_cache:
            return self._team_last_cache[key]
        params = {"team": team_id, "last": last}
        if self.same_league:
            params["league"] = league_id
            params["season"] = season
        js = self.api._get("/fixtures", params)
        arr = js.get("response", []) or []
        # tieni solo conclusi
        out = []
        for fx in arr:
            st = ((fx.get("fixture", {}) or {}).get("status", {}) or {}).get("short") or ""
            if st in ("FT", "AET", "PEN"):
                out.append(fx)
        self._team_last_cache[key] = out
        return out

    def _rates_from_last(self, team_id: int, last_fx: List[Dict[str, Any]]) -> Dict[str, float]:
        if not last_fx:
            return {
                "form_pts_rate": 0.5, "gf_avg": 1.2, "ga_avg": 1.1,
                "tot_avg": 2.3, "over15": 0.65, "over25": 0.50,
                "under35": 0.70, "btts": 0.50, "cs": 0.30
            }
        pts = []
        gf_arr, ga_arr, tot_arr = [], [], []
        over15_cnt = over25_cnt = under35_cnt = btts_cnt = cs_cnt = 0
        for fx in last_fx:
            g_for, g_against = _team_goals_in_fx(fx, team_id)
            gf_arr.append(g_for); ga_arr.append(g_against); tot_arr.append(g_for + g_against)
            if (g_for + g_against) >= 2: over15_cnt += 1
            if (g_for + g_against) >= 3: over25_cnt += 1
            if (g_for + g_against) <= 3: under35_cnt += 1
            if g_for >= 1 and g_against >= 1: btts_cnt += 1
            if g_against == 0: cs_cnt += 1
        # forma: ultime 5
        last5 = last_fx[:5]
        for fx in last5:
            pts.append(_wld_points_for_team(fx, team_id))
        games = len(last_fx)
        d = {
            "form_pts_rate": (sum(pts) / (3 * len(last5))) if last5 else 0.5,
            "gf_avg": mean(gf_arr) if gf_arr else 1.2,
            "ga_avg": mean(ga_arr) if ga_arr else 1.1,
            "tot_avg": mean(tot_arr) if tot_arr else 2.3,
            "over15": over15_cnt / games if games else 0.65,
            "over25": over25_cnt / games if games else 0.50,
            "under35": under35_cnt / games if games else 0.70,
            "btts": btts_cnt / games if games else 0.50,
            "cs": cs_cnt / games if games else 0.30,
        }
        # clamp ragionevoli
        d["gf_avg"] = clamp(d["gf_avg"], 0.0, 3.5)
        d["ga_avg"] = clamp(d["ga_avg"], 0.0, 3.5)
        d["tot_avg"] = clamp(d["tot_avg"], 0.0, 4.5)
        for k in ("over15","over25","under35","btts","cs","form_pts_rate"):
            d[k] = clamp(d[k], 0.0, 1.0)
        return d

    def features_for_fixture(self, fixture_id: int) -> Dict[str, Any]:
        """
        Ritorna:
        {
          "league_id": int, "season": int,
          "home_id": int, "away_id": int,
          "home": {...rates...}, "away": {...rates...}
        }
        """
        fx = self._get_fixture(fixture_id)
        league = (fx.get("league") or {})
        league_id = int(league.get("id") or 0)
        season = int(league.get("season") or 0)
        teams = (fx.get("teams") or {})
        home_id = int((teams.get("home") or {}).get("id") or 0)
        away_id = int((teams.get("away") or {}).get("id") or 0)

        last_home = self._get_team_last(home_id, league_id, season, last=10)
        last_away = self._get_team_last(away_id, league_id, season, last=10)

        return {
            "league_id": league_id,
            "season": season,
            "home_id": home_id,
            "away_id": away_id,
            "home": self._rates_from_last(home_id, last_home),
            "away": self._rates_from_last(away_id, last_away),
        }
