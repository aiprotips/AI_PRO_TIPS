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

    def odds_by_fixture(self, fixture_id: int) -> List[Dict]:
        js = self._get("/odds", {"fixture": fixture_id})
        return js.get("response", [])

    def odds_by_date(self, date: str) -> List[Dict]:
        js = self._get("/odds", {"date": date})
        return js.get("response", [])

    @staticmethod
    def parse_markets(odds_resp: List[Dict]) -> Dict[str, float]:
        out = {}
        def put(k, v):
            if v is None: return
            try:
                x = float(v)
            except:
                return
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
                                pass
                    elif "double chance" in name:
                        for v in vals:
                            lab = v.get("value","").lower()
                            odd = v.get("odd")
                            if "home/draw" in lab or lab in ("1x","1X","home or draw"):
                                put("1X", odd)
                            elif "home/away" in lab or lab == "12" or "home or away" in lab:
                                put("12", odd)
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
                            if lab in ("under3.5", "u3.5", "under 3.5", "u 3.5"):
                                put("Under 3.5", odd)
                            elif lab in ("over0.5", "o0.5", "over 0.5", "o 0.5"):
                                put("Over 0.5", odd)
                    elif "team to score" in name:
                        for v in vals:
                            lab = v.get("value","").lower()
                            odd = v.get("odd")
                            if "home - yes" in lab or lab in ("home yes","home yes "):
                                put("Home to Score", odd)
                            elif "away - yes" in lab or lab in ("away yes","away yes "):
                                put("Away to Score", odd)
        return out
