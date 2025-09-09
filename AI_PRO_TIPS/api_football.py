import requests
from typing import Dict, Any, List, Optional

class APIFootball:
    def __init__(self, api_key: str, tz: str = "Europe/Rome"):
        self.base = "https://v3.football.api-sports.io"
        self.headers = {"x-apisports-key": api_key}
        self.tz = tz

    def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base}{path}"
        if "timezone" not in params:
            params["timezone"] = self.tz
        r = requests.get(url, params=params, headers=self.headers, timeout=20)
        if not r.ok:
            raise RuntimeError(f"API-Football error {r.status_code}: {r.text}")
        return r.json()

    # Fixtures
    def fixtures_by_date(self, date: str) -> List[Dict]:
        js = self._get("/fixtures", {"date": date})
        return js.get("response", [])

    def live_fixtures(self) -> List[Dict]:
        js = self._get("/fixtures", {"live": "all"})
        return js.get("response", [])

    def fixture_by_id(self, fixture_id: int) -> Optional[Dict]:
        js = self._get("/fixtures", {"id": fixture_id})
        arr = js.get("response", [])
        return arr[0] if arr else None

    # Odds
    def odds_by_fixture(self, fixture_id: int) -> List[Dict]:
        js = self._get("/odds", {"fixture": fixture_id})
        return js.get("response", [])

    def odds_by_date(self, date: str) -> List[Dict]:
        js = self._get("/odds", {"date": date})
        return js.get("response", [])

    # Events (best-effort per red card check)
    def fixture_events(self, fixture_id: int) -> List[Dict]:
        js = self._get("/fixtures/events", {"fixture": fixture_id})
        return js.get("response", [])

    # Market parser
    @staticmethod
    def parse_markets(odds_resp: List[Dict]) -> Dict[str, float]:
        out = {}
        def put(k, v):
            if v is None: return
            try: x = float(v)
            except: return
            if k not in out or x < out[k]:
                out[k] = x

        for entry in odds_resp:
            for bm in entry.get("bookmakers", []):
                for bet in bm.get("bets", []):
                    name = bet.get("name","").lower()
                    vals = bet.get("values", [])
                    if "match winner" in name or name == "winner":
                        for v in vals:
                            val = v.get("value","").lower()
                            odd = v.get("odd")
                            if val.startswith("home") or val == "1":
                                put("1", odd)
                            elif val.startswith("away") or val == "2":
                                put("2", odd)
                    elif "double chance" in name:
                        for v in vals:
                            lab = v.get("value","").lower()
                            odd = v.get("odd")
                            if "home/draw" in lab or lab in ("1x","1X","home or draw"):
                                put("1X", odd)
                            elif "home/away" in lab or lab == "12" or "home or away" in lab:
                                put("12", odd)
                            elif "draw/away" in lab or lab in ("x2","X2","draw or away"):
                                put("X2", odd)
                    elif "draw no bet" in name:
                        for v in vals:
                            lab = v.get("value","").lower()
                            odd = v.get("odd")
                            if "home" in lab:
                                put("DNB Home", odd)
                            elif "away" in lab:
                                put("DNB Away", odd)
                    elif "total" in name or "goals over/under" in name:
                        for v in vals:
                            lab = v.get("value","").lower().replace(" ", "")
                            odd = v.get("odd")
                            if lab in ("under3.5", "u3.5"):
                                put("Under 3.5", odd)
                            elif lab in ("over0.5", "o0.5"):
                                put("Over 0.5", odd)
                    elif "team to score" in name:
                        for v in vals:
                            lab = v.get("value","").lower()
                            odd = v.get("odd")
                            if "home - yes" in lab or lab.strip() in ("home yes",):
                                put("Home to Score", odd)
                            elif "away - yes" in lab or lab.strip() in ("away yes",):
                                put("Away to Score", odd)
        return out

    # -----------------------------
    # Aggiunte per mapping pick → statistica coerente
    # -----------------------------

    def team_statistics(self, league_id: int, season: int, team_id: int) -> dict:
        """
        Stats squadra nella lega e stagione specificate.
        API: /teams/statistics?league={id}&season={year}&team={id}
        Return: dict 'response' (singolo oggetto) oppure {}.
        """
        js = self._get("/teams/statistics", {
            "league": league_id,
            "season": season,
            "team": team_id
        })
        return js.get("response", {}) or {}

    def team_last_fixtures(self, team_id: int, last: int = 10, league_id: Optional[int] = None, season: Optional[int] = None) -> List[Dict]:
        """
        Ultime partite della squadra (opz. filtrate per lega/stagione).
        API: /fixtures?team={id}&last={n}[&league=..][&season=..]
        Return: list 'response' (fixtures) o [].
        """
        params: Dict[str, Any] = {"team": team_id, "last": last}
        if league_id: params["league"] = league_id
        if season: params["season"] = season
        js = self._get("/fixtures", params)
        return js.get("response", []) or []

    def head_to_head(self, home_id: int, away_id: int, last: int = 10, league_id: Optional[int] = None) -> List[Dict]:
        """
        Scontri diretti tra due squadre.
        API: /fixtures/headtohead?h2h=homeId-awayId[&last=..][&league=..]
        Return: list 'response' (fixtures) o [].
        """
        h2h = f"{home_id}-{away_id}"
        params: Dict[str, Any] = {"h2h": h2h, "last": last}
        if league_id: params["league"] = league_id
        js = self._get("/fixtures/headtohead", params)
        return js.get("response", []) or []
