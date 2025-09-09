import requests
from typing import Dict, Any, List, Optional

# Normalizziamo i nomi di Bet365 (alcune risposte la riportano in minuscolo/varianti)
BET365_NAMES = {"bet365", "bet 365", "bet-365"}

class APIFootball:
    def __init__(self, api_key: str, tz: str = "Europe/Rome"):
        self.base = "https://v3.football.api-sports.io"
        self.headers = {"x-apisports-key": api_key}
        self.tz = tz

    def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Wrapper GET con gestione timezone default."""
        url = f"{self.base}{path}"
        if "timezone" not in params:
            params["timezone"] = self.tz
        r = requests.get(url, params=params, headers=self.headers, timeout=20)
        if not r.ok:
            raise RuntimeError(f"API-Football error {r.status_code}: {r.text}")
        return r.json()

    # ----------------------
    # Fixtures
    # ----------------------
    def fixtures_by_date(self, date: str) -> List[Dict]:
        """Tutte le partite in una data (rispettando self.tz)."""
        js = self._get("/fixtures", {"date": date})
        return js.get("response", [])

    def live_fixtures(self) -> List[Dict]:
        """Tutte le partite live (per engine live/alert)."""
        js = self._get("/fixtures", {"live": "all"})
        return js.get("response", [])

    def fixture_by_id(self, fixture_id: int) -> Optional[Dict]:
        """Dettaglio singolo fixture."""
        js = self._get("/fixtures", {"id": fixture_id})
        arr = js.get("response", [])
        return arr[0] if arr else None

    # ----------------------
    # Odds
    # ----------------------
    def odds_by_fixture(self, fixture_id: int) -> List[Dict]:
        """Quote per un fixture (tutti i bookmaker)."""
        js = self._get("/odds", {"fixture": fixture_id})
        return js.get("response", [])

    def bet365_markets(self, odds_resp: List[Dict]) -> List[Dict]:
        """Estrae solo i bookmaker 'Bet365' (con normalizzazione nome)."""
        out = []
        for entry in odds_resp:
            for bm in entry.get("bookmakers", []):
                name = (bm.get("name", "") or "").lower().strip()
                if name in BET365_NAMES:
                    out.append(bm)
        return out

    def parse_markets_bet365(self, odds_resp: List[Dict]) -> Dict[str, float]:
        """
        Ritorna mappa 'market' -> quota (float) usando SOLO Bet365:
          - Match Winner: '1','2' (salviamo anche 'X' se disponibile)
          - Double Chance: '1X','12','X2'
          - Draw No Bet: 'DNB Home','DNB Away'
          - Totali: 'Under 3.5','Over 0.5'
          - Team to Score: 'Home to Score','Away to Score'
          - BTTS: 'BTTS Yes','BTTS No'
        """
        out: Dict[str, float] = {}

        def put(k: str, v):
            if v is None:
                return
            try:
                x = float(v)
            except Exception:
                return
            if k not in out or x < out[k]:
                out[k] = x

        for bm in self.bet365_markets(odds_resp):
            for bet in bm.get("bets", []):
                name = (bet.get("name", "") or "").lower()
                vals = bet.get("values", [])

                # Match Winner
                if "match winner" in name or name == "winner":
                    for v in vals:
                        val = (v.get("value", "") or "").lower()
                        odd = v.get("odd")
                        if val.startswith("home") or val == "1":
                            put("1", odd)
                        elif val.startswith("away") or val == "2":
                            put("2", odd)
                        elif val.startswith("draw") or val == "x":
                            put("X", odd)

                # Double Chance
                elif "double chance" in name:
                    for v in vals:
                        lab = (v.get("value", "") or "").lower()
                        odd = v.get("odd")
                        if "home/draw" in lab or lab in ("1x", "home or draw"):
                            put("1X", odd)
                        elif "home/away" in lab or lab == "12" or "home or away" in lab:
                            put("12", odd)
                        elif "draw/away" in lab or lab in ("x2", "draw or away"):
                            put("X2", odd)

                # Draw No Bet
                elif "draw no bet" in name:
                    for v in vals:
                        lab = (v.get("value", "") or "").lower()
                        odd = v.get("odd")
                        if "home" in lab:
                            put("DNB Home", odd)
                        elif "away" in lab:
                            put("DNB Away", odd)

                # Totali principali
                elif "goals over/under" in name or "total" in name:
                    for v in vals:
                        lab = (v.get("value", "") or "").lower().replace(" ", "")
                        odd = v.get("odd")
                        if lab in ("under3.5", "u3.5"):
                            put("Under 3.5", odd)
                        elif lab in ("over0.5", "o0.5"):
                            put("Over 0.5", odd)

                # Entrambe segnano
                elif "both teams to score" in name or "goal/no goal" in name:
                    for v in vals:
                        lab = (v.get("value", "") or "").lower()
                        odd = v.get("odd")
                        if "yes" in lab:
                            put("BTTS Yes", odd)
                        elif "no" in lab:
                            put("BTTS No", odd)

                # Team to score
                elif "team to score" in name:
                    for v in vals:
                        lab = (v.get("value", "") or "").lower()
                        odd = v.get("odd")
                        if "home - yes" in lab or lab.strip() in ("home yes",):
                            put("Home to Score", odd)
                        elif "away - yes" in lab or lab.strip() in ("away yes",):
                            put("Away to Score", odd)

        return out

    # ----------------------
    # Stats helpers (per coerenza Statistica Lampo)
    # ----------------------
    def team_statistics(self, league_id: int, season: int, team_id: int) -> dict:
        """ /teams/statistics?league={id}&season={year}&team={id} """
        js = self._get("/teams/statistics", {"league": league_id, "season": season, "team": team_id})
        return js.get("response", {}) or {}

    def team_last_fixtures(self, team_id: int, last: int = 10, league_id: Optional[int] = None, season: Optional[int] = None) -> list:
        """ /fixtures?team={id}&last={n}[&league=..][&season=..] """
        params = {"team": team_id, "last": last}
        if league_id:
            params["league"] = league_id
        if season:
            params["season"] = season
        js = self._get("/fixtures", params)
        return js.get("response", []) or []

    def head_to_head(self, home_id: int, away_id: int, last: int = 10, league_id: Optional[int] = None) -> list:
        """ /fixtures/headtohead?h2h=homeId-awayId[&last=..][&league=..] """
        params = {"h2h": f"{home_id}-{away_id}", "last": last}
        if league_id:
            params["league"] = league_id
        js = self._get("/fixtures/headtohead", params)
        return js.get("response", []) or []
