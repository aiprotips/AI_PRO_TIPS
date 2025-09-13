import requests
from typing import Dict, Any, List
from dateutil import parser as duparser
from datetime import timezone

BET365_ID = 8
MIN_VALID_ODD = 1.06

REQUIRED_MARKETS = (
    "1","X","2",
    "1X","12","X2",
    "Over 0.5","Over 1.5","Over 2.5",
    "Under 2.5","Under 3.5",
    "Gol","No Gol"
)

# parole che indicano mercati parziali (da escludere)
_EXCLUDE_PARTIAL = ("half", "period", "1st", "2nd", "first half", "second half")

class APIFootball:
    def __init__(self, api_key: str, tz: str = "Europe/Rome"):
        self.base = "https://v3.football.api-sports.io"
        self.headers = {"x-apisports-key": api_key}
        self.tz = tz

    def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if "timezone" not in params:
            params["timezone"] = self.tz
        r = requests.get(f"{self.base}{path}", params=params, headers=self.headers, timeout=25)
        if not r.ok:
            raise RuntimeError(f"API-Football error {r.status_code}: {r.text}")
        return r.json()

    def _get_paged(self, path: str, base_params: Dict[str, Any]) -> List[Dict]:
        page = 1
        out: List[Dict] = []
        while True:
            params = dict(base_params)
            params["page"] = page
            js = self._get(path, params)
            resp = js.get("response", []) or []
            out.extend(resp)
            paging = js.get("paging", {}) or {}
            cur = int(paging.get("current") or page)
            tot = int(paging.get("total") or page)
            if cur >= tot:
                break
            page += 1
        return out

    # -------- Odds per data (Bet365) --------
    def odds_by_date_bet365(self, date: str) -> List[Dict]:
        return self._get_paged("/odds", {"date": date, "bookmaker": BET365_ID})

    # -------- Fixtures per data (paginato) --------
    def fixtures_by_date(self, date: str) -> List[Dict]:
        return self._get_paged("/fixtures", {"date": date})

    # -------- Odds per fixture (Bet365) --------
    def odds_by_fixture_bet365(self, fixture_id: int) -> List[Dict]:
        js = self._get("/odds", {"fixture": fixture_id, "bookmaker": BET365_ID})
        return js.get("response", []) or []

    # -------- Helpers parsing --------
    @staticmethod
    def _put(out: Dict[str, float], key: str, val):
        if val is None:
            return
        try:
            x = float(val)
        except:
            return
        if x <= MIN_VALID_ODD:
            return
        if key not in out or x < out[key]:
            out[key] = x

    @staticmethod
    def _is_partial(name: str) -> bool:
        return any(tok in name for tok in _EXCLUDE_PARTIAL)

    @staticmethod
    def _parse_market_block(bets: List[Dict]) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for bet in bets:
            raw_name = (bet.get("name","") or "")
            name = raw_name.lower().strip()
            vals = bet.get("values", []) or []

            # salta mercati parziali (HT, 1st Half, 2nd Half, periods, ecc.)
            if APIFootball._is_partial(name):
                continue

            # 1X2 full-time
            if name == "match winner" or name == "winner":
                for v in vals:
                    val = (v.get("value","") or "").lower(); odd = v.get("odd")
                    if val.startswith("home") or val == "1": APIFootball._put(out, "1", odd)
                    elif val.startswith("away") or val == "2": APIFootball._put(out, "2", odd)
                    elif val.startswith("draw") or val == "x": APIFootball._put(out, "X", odd)

            # Double Chance FT
            elif name == "double chance":
                for v in vals:
                    lab = (v.get("value","") or "").lower(); odd = v.get("odd")
                    if "home/draw" in lab or lab in ("1x","home or draw"): APIFootball._put(out, "1X", odd)
                    elif "home/away" in lab or lab == "12" or "home or away" in lab: APIFootball._put(out, "12", odd)
                    elif "draw/away" in lab or lab in ("x2","draw or away","away or draw"): APIFootball._put(out, "X2", odd)

            # Totali full-time
            elif name in ("goals over/under", "total"):
                for v in vals:
                    lab = (v.get("value","") or "").lower().replace(" ", ""); odd = v.get("odd")
                    if lab in ("over0.5","o0.5"): APIFootball._put(out, "Over 0.5", odd)
                    elif lab in ("over1.5","o1.5"): APIFootball._put(out, "Over 1.5", odd)
                    elif lab in ("over2.5","o2.5"): APIFootball._put(out, "Over 2.5", odd)
                    elif lab in ("under2.5","u2.5"): APIFootball._put(out, "Under 2.5", odd)
                    elif lab in ("under3.5","u3.5"): APIFootball._put(out, "Under 3.5", odd)

            # Gol/No Gol (BTTS) FT
            elif name in ("both teams to score", "goal/no goal"):
                for v in vals:
                    lab = (v.get("value","") or "").lower(); odd = v.get("odd")
                    if "yes" in lab: APIFootball._put(out, "Gol", odd)
                    elif "no"  in lab: APIFootball._put(out, "No Gol", odd)

            # Draw No Bet (non richiesto) -> ignoriamo
            else:
                continue

        # Solo i mercati richiesti nell'ordine voluto
        return {k: out[k] for k in REQUIRED_MARKETS if k in out}

    def parse_odds_entries(self, entries: List[Dict]) -> List[Dict]:
        """
        Converte la risposta /odds?date=... in una lista uniforme:
        [{
          "fixture_id": int,
          "kickoff_iso": str,
          "league_country": str,
          "league_name": str,
          "home": str,
          "away": str,
          "markets": {...},
          "last_update": "HH:MM"
        }, ...]
        """
        out = []
        for e in entries:
            fixture = e.get("fixture", {}) or {}
            league = e.get("league", {}) or {}
            fid = int(fixture.get("id") or 0)
            kickoff_iso = fixture.get("date") or ""

            # Nomi squadra robusti: e["teams"] oppure fixture["teams"]; se mancano ancora, chiama fixture_by_id
            teams = e.get("teams") or (fixture.get("teams") or {})
            home = ((teams.get("home") or {}).get("name"))
            away = ((teams.get("away") or {}).get("name"))
            if not home or not away:
                try:
                    fx = self._get("/fixtures", {"id": fid}).get("response", []) or []
                    if fx:
                        fteams = (fx[0].get("teams") or {})
                        home = home or ((fteams.get("home") or {}).get("name"))
                        away = away or ((fteams.get("away") or {}).get("name"))
                except Exception:
                    pass
            home = home or "Home"
            away = away or "Away"

            bookmakers = e.get("bookmakers", []) or []
            if not bookmakers:
                continue
            bm = bookmakers[0]
            bets = bm.get("bets", []) or []
            markets = self._parse_market_block(bets)
            if not markets:
                continue

            lu = bm.get("lastUpdate")
            upd = ""
            if lu:
                try:
                    ts = duparser.isoparse(lu)
                    upd = ts.astimezone(timezone.utc).strftime("%H:%M")
                except Exception:
                    upd = ""

            out.append({
                "fixture_id": fid,
                "kickoff_iso": kickoff_iso,
                "league_country": (league.get("country","") or ""),
                "league_name": (league.get("name","") or ""),
                "home": home,
                "away": away,
                "markets": markets,
                "last_update": upd
            })
        return out

    def entries_by_date_bet365(self, date: str) -> List[Dict]:
        """
        Prova /odds?date=... (Bet365) con paginazione; se vuoto, fallback:
        - /fixtures?date=... (paginazione) -> per ogni fixture: /odds?fixture=...&bookmaker=8
        - Assembla entries nel formato già usato da parse_odds_entries
        """
        odds_entries = self.odds_by_date_bet365(date)
        parsed_from_odds = self.parse_odds_entries(odds_entries)
        if parsed_from_odds:
            return parsed_from_odds

        fixtures = self.fixtures_by_date(date)
        out = []
        for fx in fixtures:
            fixture = fx.get("fixture", {}) or {}
            league = fx.get("league", {}) or {}
            fid = int(fixture.get("id") or 0)
            if not fid:
                continue

            teams = fx.get("teams") or (fixture.get("teams") or {})
            home = ((teams.get("home") or {}).get("name")) or "Home"
            away = ((teams.get("away") or {}).get("name")) or "Away"
            kickoff_iso = fixture.get("date") or ""

            oresp = self.odds_by_fixture_bet365(fid)
            bookmakers = []
            for e in oresp:
                for bm in (e.get("bookmakers") or []):
                    bookmakers = [bm]; break
                if bookmakers: break
            if not bookmakers:
                continue

            markets = self._parse_market_block(bookmakers[0].get("bets", []) or [])
            if not markets:
                continue

            lu = bookmakers[0].get("lastUpdate")
            upd = ""
            if lu:
                try:
                    ts = duparser.isoparse(lu)
                    upd = ts.astimezone(timezone.utc).strftime("%H:%M")
                except Exception:
                    upd = ""

            out.append({
                "fixture_id": fid,
                "kickoff_iso": kickoff_iso,
                "league_country": (league.get("country","") or ""),
                "league_name": (league.get("name","") or ""),
                "home": home,
                "away": away,
                "markets": markets,
                "last_update": upd
            })
        return out
