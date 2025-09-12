import requests
from typing import Dict, Any, List, Optional, Tuple
from dateutil import parser as duparser
from datetime import datetime, timezone

BET365_NAMES = {"bet365", "bet 365", "bet-365"}

# minuti massimi di “staleness” accettata per i prezzi Bet365
MAX_STALENESS_MIN = 15

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
        # SOLO Bet365 (bookmaker=8) per ridurre rumore
        js = self._get("/odds", {"fixture": fixture_id, "bookmaker": 8})
        return js.get("response", [])

    def _bet365_blocks_fresh(self, odds_resp: List[Dict]) -> List[Dict]:
        """
        Estrae SOLO i blocchi bookmaker=Bet365 con lastUpdate “fresco”.
        Se lastUpdate manca, li consideriamo stali -> scartati.
        """
        out = []
        now_utc = datetime.now(timezone.utc)
        for entry in odds_resp:
            for bm in entry.get("bookmakers", []):
                name = (bm.get("name", "") or "").lower().strip()
                if name not in BET365_NAMES:
                    continue
                last_upd = bm.get("lastUpdate")
                if not last_upd:
                    continue
                try:
                    ts = duparser.isoparse(last_upd)
                    # normalizza a UTC se privo di tz
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    age_min = (now_utc - ts.astimezone(timezone.utc)).total_seconds() / 60.0
                except Exception:
                    continue
                if age_min <= MAX_STALENESS_MIN:
                    out.append(bm)
        return out

    def parse_markets_bet365(self, odds_resp: List[Dict]) -> Dict[str, float]:
        """
        Ritorna mappa mercato->odd (float) SOLO da Bet365, SOLO se lastUpdate è “fresco”.
        Scarta mercati sospesi (odd <= 1.05).
        """
        out: Dict[str, float] = {}

        def put(k: str, v):
            if v is None:
                return
            try:
                x = float(v)
            except:
                return
            if x <= 1.05:
                return
            if k not in out or x < out[k]:
                out[k] = x

        bet365_fresh = self._bet365_blocks_fresh(odds_resp)
        for bm in bet365_fresh:
            for bet in bm.get("bets", []):
                name = (bet.get("name", "") or "").lower()
                vals = bet.get("values", [])

                # 1X2
                if "match winner" in name or name == "winner":
                    for v in vals:
                        val = (v.get("value", "") or "").lower()
                        odd = v.get("odd")
                        if val.startswith("home") or val == "1": put("1", odd)
                        elif val.startswith("away") or val == "2": put("2", odd)
                        elif val.startswith("draw") or val == "x": put("X", odd)

                # Doppie chance
                elif "double chance" in name:
                    for v in vals:
                        lab = (v.get("value", "") or "").lower(); odd = v.get("odd")
                        if "home/draw" in lab or lab in ("1x","home or draw"): put("1X", odd)
                        elif "home/away" in lab or lab == "12" or "home or away" in lab: put("12", odd)
                        elif "draw/away" in lab or lab in ("x2","draw or away"): put("X2", odd)

                # DNB
                elif "draw no bet" in name:
                    for v in vals:
                        lab = (v.get("value", "") or "").lower(); odd = v.get("odd")
                        if "home" in lab: put("DNB Home", odd)
                        elif "away" in lab: put("DNB Away", odd)

                # Totali
                elif "goals over/under" in name or "total" in name:
                    for v in vals:
                        lab = (v.get("value","") or "").lower().replace(" ",""); odd = v.get("odd")
                        if lab in ("under3.5","u3.5"): put("Under 3.5", odd)
                        elif lab in ("over0.5","o0.5"): put("Over 0.5", odd)
                        elif lab in ("over1.5","o1.5"): put("Over 1.5", odd)
                        elif lab in ("over2.5","o2.5"): put("Over 2.5", odd)
                        elif lab in ("under2.5","u2.5"): put("Under 2.5", odd)

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
