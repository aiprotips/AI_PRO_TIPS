from typing import Dict, Tuple
from zoneinfo import ZoneInfo

from .config import Config
from .telegram_client import TelegramClient
from .api_football import APIFootball
from .util import now_tz
from .repo import (
    get_open_betslips,
    get_selections_for_betslip,
    mark_selection_result,
    update_betslip_progress,
    close_betslip_if_done,
    log_error,
)
from .templates import (
    render_live_alert,
    render_live_energy,
    render_celebration_singola,
    render_celebration_multipla,
    render_quasi_vincente,
    render_cuori_spezzati,
)


class LiveEngine:
    """
    Regole:
      - Rispetta QUIET_HOURS (nessun messaggio tra 00:00–07:59 locali).
      - Live Alert: favorita pre @ Bet365 <= 1.25, sotto entro 20', senza rosso alla favorita.
      - Live Energy: solo se la schedina è ancora viva (nessuna gamba persa).
      - Niente progress bar: Live Energy la sostituisce.
      - Chiusure: Cassa / Quasi / Cuori.
    """

    def __init__(self, tg: TelegramClient, api: APIFootball, cfg: Config):
        self.tg = tg
        self.api = api
        self.cfg = cfg
        self._alert_sent_fixtures = set()          # fixtures che hanno già ricevuto l'alert favorita sotto
        self._energy_sent_selections = set()       # selections.id per cui è già uscito un Live Energy "presa"
        self._final_message_sent_bets = set()      # betslip.id già chiusi e messaggi finali inviati

    # -----------------------
    # Guardie
    # -----------------------
    def _in_quiet_hours(self) -> bool:
        return now_tz(self.cfg.TZ).hour in range(self.cfg.QUIET_HOURS[0], self.cfg.QUIET_HOURS[1])

    # -----------------------
    # Favorite detection @ Bet365 + condizioni alert
    # -----------------------
    def _favorite_pre_from_bet365(self, fx: Dict) -> Tuple[str, float]:
        """
        Ritorna (fav_side, fav_preodd). fav_side in {'home','away'}.
        Se non disponibile, fallback ('home', 99.0).
        """
        fid = int((fx.get("fixture", {}) or {}).get("id") or 0)
        try:
            odds = self.api.odds_by_fixture(fid)
            mk = self.api.parse_markets_bet365(odds)
            o1 = float(mk.get("1")) if "1" in mk else None
            o2 = float(mk.get("2")) if "2" in mk else None
            if o1 is None and o2 is None:
                return "home", 99.0
            if o2 is None or (o1 is not None and o1 <= o2):
                return "home", o1 or 99.0
            return "away", o2 or 99.0
        except Exception:
            return "home", 99.0

    def _no_red_card_for_favorite(self, fx: Dict, fav_side: str) -> bool:
        """True se non ci sono rossi contro la favorita (best-effort)."""
        try:
            fid = int((fx.get("fixture", {}) or {}).get("id") or 0)
            js = self.api._get("/fixtures/events", {"fixture": fid})  # best-effort
            events = js.get("response", []) if js else []
        except Exception:
            events = []
        fav_name = (fx.get("teams", {}) or {}).get(fav_side, {}).get("name", "")
        for ev in events:
            if (ev.get("type") == "Card") and str(ev.get("detail", "")).lower().startswith("red"):
                if (ev.get("team") or {}).get("name", "") == fav_name:
                    return False
        return True

    def _should_send_fav_under20_alert(self, fx: Dict) -> Tuple[bool, str, str, int]:
        """
        Verifica tutte le condizioni alert favorita sotto <=20':
          - Lega whitelisted (by name/country)
          - minuto <= 20
          - favorita pre <= 1.25 (Bet365)
          - favorita in svantaggio
          - nessun rosso alla favorita
        Ritorna (ok, fav_name, other_name, minute)
        """
        # Filtro leghe whitelisted (by country/name)
        lg = fx.get("league", {}) or {}
        country = (lg.get("country", "") or "").lower().strip()
        name = (lg.get("name", "") or "").lower().strip()
        if (country, name) not in self.cfg.ALLOWED_COMP_NAMES:
            return False, "", "", 0

        info = fx.get("fixture", {}) or {}
        minute = int(((info.get("status", {}) or {}).get("elapsed") or 0))
        if not minute or minute > 20:
            return False, "", "", 0

        fav_side, preodd = self._favorite_pre_from_bet365(fx)
        if preodd > 1.25:
            return False, "", "", 0

        goals = fx.get("goals", {}) or {}
        gh, ga = int(goals.get("home") or 0), int(goals.get("away") or 0)
        losing = (gh < ga) if fav_side == "home" else (ga < gh)
        if not losing:
            return False, "", "", 0

        if not self._no_red_card_for_favorite(fx, fav_side):
            return False, "", "", 0

        teams = fx.get("teams", {}) or {}
        home = teams.get("home", {}).get("name", "Home")
        away = teams.get("away", {}).get("name", "Away")
        fav_name = home if fav_side == "home" else away
        other_name = away if fav_side == "home" else home
        return True, fav_name, other_name, minute

    # -----------------------
    # Resolve mercato
    # -----------------------
    def _resolve_market(self, market: str, gh: int, ga: int, status_short: str) -> str:
        finished = status_short in ("FT", "AET", "PEN")

        if market == "Under 3.5":
            return "WON" if finished and (gh + ga) <= 3 else ("PENDING" if not finished else "LOST")

        if market == "Over 0.5":
            if gh + ga >= 1:
                return "WON"
            return "PENDING" if not finished else "LOST"

        if market == "1":
            if finished:
                if gh > ga: return "WON"
                if gh < ga: return "LOST"
                return "VOID"
            return "PENDING"

        if market == "2":
            if finished:
                if ga > gh: return "WON"
                if ga < gh: return "LOST"
                return "VOID"
            return "PENDING"

        if market == "1X":
            return "WON" if finished and gh >= ga else ("PENDING" if not finished else "LOST")

        if market == "X2":
            return "WON" if finished and ga >= gh else ("PENDING" if not finished else "LOST")

        if market == "12":
            return "WON" if finished and gh != ga else ("PENDING" if not finished else "LOST")

        if market == "Home to Score":
            if gh >= 1:
                return "WON"
            return "PENDING" if not finished else "LOST"

        if market == "Away to Score":
            if ga >= 1:
                return "WON"
            return "PENDING" if not finished else "LOST"

        if market == "DNB Home":
            if finished:
                if gh > ga: return "WON"
                if gh < ga: return "LOST"
                return "VOID"
            return "PENDING"

        if market == "DNB Away":
            if finished:
                if ga > gh: return "WON"
                if ga < gh: return "LOST"
                return "VOID"
            return "PENDING"

        if market in ("BTTS Yes", "BTTS No"):
            if finished:
                if market == "BTTS Yes":
                    return "WON" if (gh >= 1 and ga >= 1) else "LOST"
                else:
                    return "WON" if (gh == 0 or ga == 0) else "LOST"
            return "PENDING"

        return "PENDING"

    # -----------------------
    # Public API
    # -----------------------
    def check_favorite_under_20(self):
        """Manda l'alert favorita sotto entro 20' (pre @ Bet365 <=1.25), fuori dalle quiet hours."""
        if self._in_quiet_hours():
            return
        try:
            lives = self.api.live_fixtures()
        except Exception as e:
            log_error("live_fav", f"live_fixtures error: {e}")
            return
        for fx in (lives or []):
            fid = int((fx.get("fixture", {}) or {}).get("id") or 0)
            if fid in self._alert_sent_fixtures:
                continue
            ok, fav_name, other_name, minute = self._should_send_fav_under20_alert(fx)
            if ok:
                # Live odds non sempre affidabili/rapide: mostriamo 'n/d'
                preodd = f"{self._favorite_pre_from_bet365(fx)[1]:.2f}"
                self.tg.send_message(render_live_alert(fav_name, other_name, minute, preodd, "n/d", "https://t.me/AIProTips"))
                self._alert_sent_fixtures.add(fid)

    def update_betslips_live(self):
        """Live Energy & chiusure schedine. Nessun output durante quiet hours."""
        if self._in_quiet_hours():
            return

        # Mappa live fixtures (riduce chiamate)
        try:
            lives = self.api.live_fixtures()
            live_map = {int((fx.get("fixture", {}) or {}).get("id") or 0): fx for fx in (lives or [])}
        except Exception:
            live_map = {}

        # Scorri tutte le schedine ancora aperte
        for b in get_open_betslips():
            bid = int(b["id"])
            legs_count = int(b.get("legs_count", 0))
            short_id = str(b.get("short_id", "-----"))
            sels = get_selections_for_betslip(bid)

            # Se una qualunque gamba è LOST → schedina morta => niente Live Energy
            already_lost = any((s.get("result") == "LOST") for s in sels)
            if already_lost:
                # Aggiorna stato per eventuale chiusura
                update_betslip_progress(bid)
                status = close_betslip_if_done(bid)
                if status and bid not in self._final_message_sent_bets:
                    self._final_message_sent_bets.add(bid)
                    if status == "LOST":
                        # Quasi vs Cuori
                        lost_legs = [s for s in sels if s.get("result") == "LOST"]
                        if len(lost_legs) == 1:
                            missed = lost_legs[0]
                            self.tg.send_message(render_quasi_vincente(f"{missed['home']}–{missed['away']} ({missed['market']})"))
                        else:
                            self.tg.send_message(render_cuori_spezzati())
                continue

            # Per ogni selezione: aggiorna stato live e invia Live Energy se diventa presa
            for sel in sels:
                fid = int(sel["fixture_id"])
                fx = live_map.get(fid)
                if not fx:  # prova fetch singola
                    try:
                        fx = self.api.fixture_by_id(fid)
                    except Exception:
                        fx = None
                if not fx:
                    continue

                info = fx.get("fixture", {}) or {}
                status_short = (info.get("status", {}) or {}).get("short") or "NS"
                minute = int(((info.get("status", {}) or {}).get("elapsed") or 0))
                goals = fx.get("goals", {}) or {}
                gh, ga = int(goals.get("home") or 0), int(goals.get("away") or 0)

                # Valuta esito corrente del mercato
                new_res = self._resolve_market(sel["market"], gh, ga, status_short)

                # Live Energy (presa) — una sola volta per selection
                if new_res == "WON" and sel["result"] == "PENDING" and sel["id"] not in self._energy_sent_selections:
                    line = ""
                    m = sel["market"]
                    if m == "Over 0.5":
                        line = "Over 0.5 preso. ✅"
                    elif m == "Home to Score" and gh >= 1:
                        line = "Segna Casa preso. ✅"
                    elif m == "Away to Score" and ga >= 1:
                        line = "Segna Trasferta preso. ✅"
                    elif m == "1" and gh > ga:
                        line = "Vantaggio casa: siamo sulla traccia. ✅"
                    elif m == "2" and ga > gh:
                        line = "Vantaggio ospiti: siamo sulla traccia. ✅"
                    elif m == "1X" and gh >= ga:
                        line = "Linea 1X in controllo. ✅"
                    elif m == "X2" and ga >= gh:
                        line = "Linea X2 in controllo. ✅"
                    elif m == "Under 3.5" and (gh + ga) <= 3 and status_short in ("HT", "2H"):
                        line = "Under 3.5 in controllo. ✅"
                    elif m in ("BTTS Yes", "BTTS No"):
                        line = f"{m} in traiettoria. ✅"

                    if line:
                        # invia micro-messaggio solo se la schedina è ancora viva
                        self.tg.send_message(render_live_energy(sel["home"], sel["away"], minute, line, short_id))
                        self._energy_sent_selections.add(sel["id"])

                # Aggiorna il result DB quando definito
                if new_res in ("WON", "LOST", "VOID") and sel["result"] != new_res:
                    mark_selection_result(sel["id"], new_res)

            # Chiudi schedina se tutte definite
            won, total = update_betslip_progress(bid)
            status = close_betslip_if_done(bid)
            if status and bid not in self._final_message_sent_bets:
                self._final_message_sent_bets.add(bid)
                if status == "WON":
                    # Singola vs multipla
                    if legs_count <= 1:
                        # prendi la selection
                        sel = sels[0] if sels else None
                        if sel:
                            # prova score live
                            try:
                                fx = self.api.fixture_by_id(int(sel["fixture_id"]))
                                goals = fx.get("goals", {}) or {}
                                score = f"{int(goals.get('home') or 0)}–{int(goals.get('away') or 0)}"
                            except Exception:
                                score = ""
                            self.tg.send_message(
                                render_celebration_singola(
                                    home=sel["home"], away=sel["away"], score=score,
                                    pick=sel["market"], odds=float(sel["odds"]),
                                    link="https://t.me/AIProTips"
                                )
                            )
                    else:
                        # multipla: riassunto
                        summary = []
                        for s in sels:
                            try:
                                fx2 = self.api.fixture_by_id(int(s["fixture_id"]))
                                g2 = fx2.get("goals", {}) or {}
                                sc = f"{int(g2.get('home') or 0)}–{int(g2.get('away') or 0)}"
                            except Exception:
                                sc = ""
                            summary.append({"home": s["home"], "away": s["away"], "pick": s["market"], "score": sc})
                        self.tg.send_message(
                            render_celebration_multipla(
                                selections=summary,
                                total_odds=float(b["total_odds"]),
                                link="https://t.me/AIProTips"
                            )
                        )
                elif status == "LOST":
                    # Quasi se una sola persa, altrimenti Cuori
                    lost = [s for s in sels if s.get("result") == "LOST"]
                    if len(lost) == 1:
                        missed = lost[0]
                        self.tg.send_message(render_quasi_vincente(f"{missed['home']}–{missed['away']} ({missed['market']})"))
                    else:
                        self.tg.send_message(render_cuori_spezzati())
