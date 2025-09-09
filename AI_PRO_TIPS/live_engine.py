from api_football import APIFootball
from telegram_client import TelegramClient
from repo import (
    get_open_betslips, get_selections_for_betslip, mark_selection_result,
    update_betslip_progress, close_betslip_if_done, cache_get_fixture, log_error
)
from templates import (
    render_live_alert,
    render_progress_bar,
    render_quasi_vincente,
    render_cuori_spezzati,
    render_celebration_singola,
    render_celebration_multipla,
)
from config import Config
import json

class LiveEngine:
    def __init__(self, tg: TelegramClient, api: APIFootball, cfg: Config):
        self.tg = tg
        self.api = api
        self.cfg = cfg
        self.sent_fav_under_alerts = set()

    def _favorite_side_from_cache(self, fid: int):
        row = cache_get_fixture(fid)
        if not row or not row.get("odds_json"):
            return None
        try:
            mk = json.loads(row["odds_json"])
        except Exception:
            return None
        # prova a dedurre la favorita guardand la quota più bassa tra 1 e 2
        try:
            o1 = float(mk.get("1")) if "1" in mk else None
            o2 = float(mk.get("2")) if "2" in mk else None
            if o1 is not None and o2 is not None:
                return "home" if o1 <= o2 else "away"
            if o1 is not None:
                return "home"
            if o2 is not None:
                return "away"
        except Exception:
            pass
        return "home"

    def _no_red_card_for_favorite(self, fx, fav_side: str) -> bool:
        # Best-effort: se non riusciamo a leggere gli eventi, non blocchiamo l’alert
        fid = int((fx.get("fixture",{}) or {}).get("id") or 0)
        try:
            events = self.api.fixture_events(fid)
        except Exception:
            events = []
        fav_name = (fx.get("teams",{}) or {}).get(fav_side,{}).get("name","")
        for ev in (events or []):
            if (ev.get("type") == "Card") and (str(ev.get("detail","")).lower().startswith("red")):
                team_name = (ev.get("team") or {}).get("name","")
                if team_name == fav_name:
                    return False
        return True

    def _is_favorite_losing_early(self, fx: dict) -> bool:
        # limita ai campionati whitelisted
        if self.cfg.ALLOWED_LEAGUES and fx.get("league",{}).get("id") not in self.cfg.ALLOWED_LEAGUES:
            return False
        info = fx.get("fixture",{}) or {}
        minute = (info.get("status",{}) or {}).get("elapsed") or 0
        if not minute or minute > 20:
            return False
        fid = int(info.get("id") or 0)
        fav = self._favorite_side_from_cache(fid) or "home"
        goals = fx.get("goals",{}) or {}
        gh, ga = goals.get("home") or 0, goals.get("away") or 0
        losing = (gh < ga) if fav == "home" else (ga < gh)
        if not losing:
            return False
        # niente rosso alla favorita
        return self._no_red_card_for_favorite(fx, fav)

    def check_favorite_under_20(self):
        try:
            lives = self.api.live_fixtures()
        except Exception as e:
            log_error("live_fav", f"live_fixtures error: {e}")
            return
        for fx in (lives or []):
            fid = int((fx.get("fixture",{}) or {}).get("id") or 0)
            if fid in self.sent_fav_under_alerts:
                continue
            if self._is_favorite_losing_early(fx):
                teams = (fx.get("teams",{}) or {})
                home = teams.get("home",{}).get("name","Home")
                away = teams.get("away",{}).get("name","Away")
                minute = ((fx.get("fixture",{}) or {}).get("status",{}) or {}).get("elapsed") or 0
                fav_side = self._favorite_side_from_cache(fid) or "home"
                fav_name = home if fav_side == "home" else away
                other_name = away if fav_side == "home" else home
                # Se vuoi integrare quote live, qui puoi aggiungere una fetch ad endpoint live-odds; per ora "n/d".
                odds_str = "n/d"
                self.tg.send_message(
                    render_live_alert(fav_name, other_name, minute, odds_str, "https://t.me/AIProTips")
                )
                self.sent_fav_under_alerts.add(fid)

    def _resolve_market(self, market: str, gh: int, ga: int, status_short: str):
        market = (market or "").strip()
        finished = status_short in ("FT", "AET", "PEN")

        if market == "Under 3.5":
            if finished:
                return "WON" if (gh + ga) <= 3 else "LOST"
            return "PENDING"

        if market == "Over 0.5":
            if finished:
                return "WON" if (gh + ga) >= 1 else "LOST"
            return "PENDING"

        if market == "1":
            if finished:
                if (gh or 0) > (ga or 0): return "WON"
                if (gh or 0) < (ga or 0): return "LOST"
                return "VOID"
            return "PENDING"

        if market == "2":
            if finished:
                if (ga or 0) > (gh or 0): return "WON"
                if (ga or 0) < (gh or 0): return "LOST"
                return "VOID"
            return "PENDING"

        if market == "1X":
            if finished:
                if (gh or 0) >= (ga or 0): return "WON"  # home win o draw
                return "LOST"
            return "PENDING"

        if market == "X2":
            if finished:
                if (ga or 0) >= (gh or 0): return "WON"  # away win o draw
                return "LOST"
            return "PENDING"

        if market == "12":
            if finished:
                if (gh or 0) != (ga or 0): return "WON"
                return "LOST"
            return "PENDING"

        if market == "Home to Score":
            if finished:
                return "WON" if (gh or 0) >= 1 else "LOST"
            return "PENDING"

        if market == "Away to Score":
            if finished:
                return "WON" if (ga or 0) >= 1 else "LOST"
            return "PENDING"

        if market == "DNB Home":
            if finished:
                if (gh or 0) > (ga or 0): return "WON"
                if (gh or 0) < (ga or 0): return "LOST"
                return "VOID"
            return "PENDING"

        if market == "DNB Away":
            if finished:
                if (ga or 0) > (gh or 0): return "WON"
                if (ga or 0) < (gh or 0): return "LOST"
                return "VOID"
            return "PENDING"

        return "PENDING"

    def update_betslips_progress_and_close(self):
        open_bets = get_open_betslips()
        if not open_bets:
            return

        # mappa live per ridurre chiamate API
        live_map = {}
        try:
            lives = self.api.live_fixtures()
            for fx in (lives or []):
                fid = int((fx.get("fixture",{}) or {}).get("id") or 0)
                if fid:
                    live_map[fid] = fx
        except Exception as e:
            log_error("live_progress", f"live_fixtures error: {e}")

        for b in open_bets:
            bid = int(b["id"])
            sels = get_selections_for_betslip(bid)

            # aggiorna i risultati delle selezioni quando definitivi
            for sel in sels:
                fid = int(sel["fixture_id"])
                fx = live_map.get(fid)
                if not fx:
                    try:
                        fx = self.api.fixture_by_id(fid)
                    except Exception:
                        fx = None
                if not fx:
                    continue
                info = fx.get("fixture",{}) or {}
                status_short = (info.get("status",{}) or {}).get("short") or "NS"
                goals = fx.get("goals",{}) or {}
                gh = goals.get("home") or 0
                ga = goals.get("away") or 0
                res = self._resolve_market(sel["market"], gh, ga, status_short)
                if res in ("WON","LOST","VOID"):
                    try:
                        mark_selection_result(sel["id"], res)
                        w, t = update_betslip_progress(bid)
                        if t > 1:
                            self.tg.send_message(render_progress_bar(w, t))
                    except Exception as e:
                        log_error("live_progress", f"update selection error: {e}")

            # prova a chiudere la schedina
            try:
                status = close_betslip_if_done(bid)
            except Exception as e:
                log_error("live_progress", f"close bet error: {e}")
                status = None

            if not status:
                continue

            code = b["code"]
            legs_count = int(b.get("legs_count", 0))

            if status == "WON":
                if legs_count <= 1:
                    # singola: recupera la selezione
                    sel = None
                    for s in sels:
                        if int(s.get("betslip_id")) == int(b["id"]):
                            sel = s
                            break
                    if sel:
                        # prova a costruire lo score finale
                        score = ""
                        try:
                            fx = self.api.fixture_by_id(int(sel["fixture_id"]))
                            if fx:
                                goals = fx.get("goals",{}) or {}
                                score = f"{goals.get('home',0)}–{goals.get('away',0)}"
                        except Exception:
                            pass
                        self.tg.send_message(
                            render_celebration_singola(
                                home=sel["home"],
                                away=sel["away"],
                                score=score,
                                pick=sel["market"],
                                odds=float(sel["odds"]),
                                link="https://t.me/AIProTips"
                            )
                        )
                    else:
                        self.tg.send_message("🎉 <b>CASSA!</b>")
                else:
                    # multipla: riassunto selezioni
                    summary = []
                    for s in sels:
                        score = ""
                        try:
                            fx = self.api.fixture_by_id(int(s["fixture_id"]))
                            if fx:
                                goals = fx.get("goals",{}) or {}
                                score = f"{goals.get('home',0)}–{goals.get('away',0)}"
                        except Exception:
                            pass
                        summary.append({
                            "home": s["home"],
                            "away": s["away"],
                            "pick": s["market"],
                            "score": score
                        })
                    self.tg.send_message(
                        render_celebration_multipla(
                            selections=summary,
                            total_odds=float(b["total_odds"]),
                            link="https://t.me/AIProTips"
                        )
                    )
            elif status == "LOST_1":
                missed = None
                for s in sels:
                    if s.get("result") == "LOST":
                        missed = f"{s['home']}–{s['away']} ({s['market']})"
                        break
                self.tg.send_message(render_quasi_vincente(missed or "1 leg"))
            else:
                self.tg.send_message(render_cuori_spezzati())
