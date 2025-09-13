import requests
from typing import Dict, Any, List, Optional
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

    # -------- Fixture singolo --------
    def fixture_by_id(self, fixture_id: int) -> Optional[Dict]:
        js = self._get("/fixtures", {"id": fixture_id})
        arr = js.get("response", []) or []
        return arr[0] if arr else None

    # -------- Odds per fixture (Bet365) --------
    def odds_by_fixture_bet365(self, fixture_id: int) -> List[Dict]:
        js = self._get("/odds", {"fixture": fixture_id, "bookmaker": BET365_ID})
        return js.get("response", []) or []

    # -------- Helpers parsing --------
    @staticmethod
    def _put(out: Dict[str, float], key: str, val):
        if val is None: return
        try:
            x = float(val)
        except:
            return
        if x <= MIN_VALID_ODD:
            return
        if key not in out or x < out[key]:
            out[key] = x

    @staticmethod
    def _parse_market_block(bets: List[Dict]) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for bet in bets or []:
            name = (bet.get("name","") or "").lower()
            vals = bet.get("values", []) or []

            if "match winner" in name or name == "winner":
                for v in vals:
                    val = (v.get("value","") or "").lower(); odd = v.get("odd")
                    if val.startswith("home") or val == "1": APIFootball._put(out, "1", odd)
                    elif val.startswith("away") or val == "2": APIFootball._put(out, "2", odd)
                    elif val.startswith("draw") or val == "x": APIFootball._put(out, "X", odd)

            elif "double chance" in name:
                for v in vals:
                    lab = (v.get("value","") or "").lower(); odd = v.get("odd")
                    if "home/draw" in lab or lab in ("1x", "home or draw"): APIFootball._put(out, "1X", odd)
                    elif "home/away" in lab or lab == "12" or "home or away" in lab: APIFootball._put(out, "12", odd)
                    elif "draw/away" in lab or lab in ("x2", "draw or away"): APIFootball._put(out, "X2", odd)

            elif "draw no bet" in name:
                pass

            elif "both teams to score" in name or "goal/no goal" in name:
                for v in vals:
                    lab = (v.get("value","") or "").lower(); odd = v.get("odd")
                    if "yes" in lab: APIFootball._put(out, "Gol", odd)
                    elif "no" in lab: APIFootball._put(out, "No Gol", odd)

            elif "goals over/under" in name or "total" in name:
                for v in vals:
                    lab = (v.get("value","") or "").lower().replace(" ", ""); odd = v.get("odd")
                    if lab in ("over0.5","o0.5"): APIFootball._put(out, "Over 0.5", odd)
                    elif lab in ("over1.5","o1.5"): APIFootball._put(out, "Over 1.5", odd)
                    elif lab in ("over2.5","o2.5"): APIFootball._put(out, "Over 2.5", odd)
                    elif lab in ("under2.5","u2.5"): APIFootball._put(out, "Under 2.5", odd)
                    elif lab in ("under3.5","u3.5"): APIFootball._put(out, "Under 3.5", odd)

        return {k: out[k] for k in REQUIRED_MARKETS if k in out}

    def parse_odds_entries(self, entries: List[Dict]) -> List[Dict]:
        out = []
        for e in entries or []:
            fixture = e.get("fixture", {}) or {}
            league = e.get("league", {}) or {}
            fid = int(fixture.get("id") or 0)
            if not fid:
                continue
            kickoff_iso = fixture.get("date") or ""

            # team names robusti
            home = ""; away = ""
            teams = e.get("teams") or (fixture.get("teams") if isinstance(fixture.get("teams"), dict) else {}) or {}
            home = (teams.get("home") or {}).get("name") if isinstance(teams, dict) else ""
            away = (teams.get("away") or {}).get("name") if isinstance(teams, dict) else ""
            if not home or not away:
                game = e.get("game") or {}
                home = home or (game.get("home") or {}).get("name", "")
                away = away or (game.get("away") or {}).get("name", "")
            if not home or not away:
                try:
                    fx = self.fixture_by_id(fid) or {}
                    t = fx.get("teams", {}) or {}
                    home = home or (t.get("home") or {}).get("name", "")
                    away = away or (t.get("away") or {}).get("name", "")
                except Exception:
                    pass
            home = home or "Home"
            away = away or "Away"

            bookmakers = e.get("bookmakers", []) or []
            bm = None
            for b in bookmakers:
                name = (b.get("name","") or "").lower().strip()
                if "bet365" in name:
                    bm = b; break
            if bm is None and bookmakers:
                bm = bookmakers[0]
            if bm is None:
                continue
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
        odds_entries = self.odds_by_date_bet365(date)
        parsed_from_odds = self.parse_odds_entries(odds_entries)
        if parsed_from_odds:
            return parsed_from_odds

        fixtures = self.fixtures_by_date(date)
        out = []
        for fx in fixtures or []:
            fixture = fx.get("fixture", {}) or {}
            league = fx.get("league", {}) or {}
            fid = int(fixture.get("id") or 0)
            if not fid:
                continue
            teams = (fx.get("teams") or {}) if isinstance(fx.get("teams"), dict) else {}
            home = (teams.get("home") or {}).get("name") or "Home"
            away = (teams.get("away") or {}).get("name") or "Away"
            kickoff_iso = fixture.get("date") or ""

            oresp = self.odds_by_fixture_bet365(fid)
            bookmakers = []
            for e in oresp or []:
                for bm in (e.get("bookmakers") or []):
                    name = (bm.get("name","") or "").lower().strip()
                    if "bet365" in name:
                        bookmakers = [bm]
                        break
                if bookmakers:
                    break
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
