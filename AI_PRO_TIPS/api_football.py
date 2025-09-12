import requests
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from dateutil import parser as duparser

BET365_NAMES = {"bet365", "bet 365", "bet-365"}
BET365_ID = 8  # bookmaker id per API-Football
MIN_VALID_ODD = 1.06  # scarta 1.00/1.05 (sospesi/placeholder)

class APIFootball:
    def __init__(self, api_key: str, tz: str = "Europe/Rome"):
        self.base = "https://v3.football.api-sports.io"
        self.headers = {"x-apisports-key": api_key}
        self.tz = tz

    def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if "timezone" not in params:
            params["timezone"] = self.tz
        r = requests.get(f"{self.base}{path}", params=params, headers=self.headers, timeout=20)
        if not r.ok:
            raise RuntimeError(f"API-Football error {r.status_code}: {r.text}")
        return r.json()

    # --- Fixtures base ---
    def fixtures_by_date(self, date: str) -> List[Dict]:
        return self._get("/fixtures", {"date": date}).get("response", [])

    def live_fixtures(self) -> List[Dict]:
        return self._get("/fixtures", {"live": "all"}).get("response", [])

    def fixture_by_id(self, fixture_id: int) -> Optional[Dict]:
        arr = self._get("/fixtures", {"id": fixture_id}).get("response", [])
        return arr[0] if arr else None

    # --- ODDS SOLO BET365 ---
    def odds_by_fixture(self, fixture_id: int) -> List[Dict]:
        """
        Carica SOLO Bet365 (bookmaker=8) per ridurre rumore e discrepanze.
        """
        return self._get("/odds", {"fixture": fixture_id, "bookmaker": BET365_ID}).get("response", [])

    # --- Parser con filtro (opzionale) di “freschezza” ---
    def parse_markets_bet365(self, odds_resp: List[Dict], fresh_only: bool = False, max_staleness_min: int = 15) -> Dict[str, float]:
        """
        Ritorna mercati -> quota (float) SOLO da Bet365, scartando odd <= MIN_VALID_ODD.
        Se fresh_only=True, considera SOLO blocchi con lastUpdate <= max_staleness_min minuti.
        Mercati mappati:
          1,X,2, 1X,12,X2, DNB Home,DNB Away,
          Under 3.5,Under 2.5, Over 0.5,Over 1.5,Over 2.5,
          Home to Score,Away to Score, Gol,No Gol
        """
        out: Dict[str, float] = {}

        def put(k: str, v):
            if v is None:
                return
            try:
                x = float(v)
            except:
                return
            if x <= MIN_VALID_ODD:
                return
            if k not in out or x < out[k]:
                out[k] = x

        now_utc = datetime.now(timezone.utc)
        # prendi SOLO blocchi Bet365
        bet_blocks = []
        for entry in odds_resp:
            for bm in entry.get("bookmakers", []):
                name = (bm.get("name", "") or "").lower().strip()
                if name not in BET365_NAMES:
                    continue
                if fresh_only:
                    lu = bm.get("lastUpdate")
                    if not lu:
                        continue
                    try:
                        ts = duparser.isoparse(lu)
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=timezone.utc)
                        age_min = (now_utc - ts.astimezone(timezone.utc)).total_seconds() / 60.0
                        if age_min > max_staleness_min:
                            continue
                    except Exception:
                        continue
                bet_blocks.append(bm)

        # parse mercati
        for bm in bet_blocks:
            for bet in bm.get("bets", []):
                name = (bet.get("name", "") or "").lower()
                vals = bet.get("values", [])

                # 1X2
                if "match winner" in name or name == "winner":
                    for v in vals:
                        val = (v.get("value", "") or "").lower(); odd = v.get("odd")
                        if val.startswith("home") or val == "1": put("1", odd)
                        elif val.startswith("away") or val == "2": put("2", odd)
                        elif val.startswith("draw") or val == "x": put("X", odd)

                # Double Chance
                elif "double chance" in name:
                    for v in vals:
                        lab = (v.get("value", "") or "").lower(); odd = v.get("odd")
                        if "home/draw" in lab or lab in ("1x", "home or draw"): put("1X", odd)
                        elif "home/away" in lab or lab == "12" or "home or away" in lab: put("12", odd)
                        elif "draw/away" in lab or lab in ("x2", "draw or away"): put("X2", odd)

                # Draw No Bet
                elif "draw no bet" in name:
                    for v in vals:
                        lab = (v.get("value", "") or "").lower(); odd = v.get("odd")
                        if "home" in lab: put("DNB Home", odd)
                        elif "away" in lab: put("DNB Away", odd)

                # Totali (principali)
                elif "goals over/under" in name or "total" in name:
                    for v in vals:
                        lab = (v.get("value","") or "").lower().replace(" ",""); odd = v.get("odd")
                        if lab in ("under3.5","u3.5"): put("Under 3.5", odd)
                        elif lab in ("under2.5","u2.5"): put("Under 2.5", odd)
                        elif lab in ("over0.5","o0.5"): put("Over 0.5", odd)
                        elif lab in ("over1.5","o1.5"): put("Over 1.5", odd)
                        elif lab in ("over2.5","o2.5"): put("Over 2.5", odd)

                # Gol / No Gol (BTTS)
                elif "both teams to score" in name or "goal/no goal" in name:
                    for v in vals:
                        lab = (v.get("value","") or "").lower(); odd = v.get("odd")
                        if "yes" in lab: put("Gol", odd)
                        elif "no"  in lab: put("No Gol", odd)

                # Segna squadra
                elif "team to score" in name:
                    for v in vals:
                        lab = (v.get("value","") or "").lower(); odd = v.get("odd")
                        if "home - yes" in lab or lab.strip() == "home yes": put("Home to Score", odd)
                        elif "away - yes" in lab or lab.strip() == "away yes": put("Away to Score", odd)

        return out
