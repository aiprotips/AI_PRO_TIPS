import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .api_football import APIFootball
from .telegram_client import TelegramClient
from .config import Config
from .templates import render_value_single, render_multipla
from .repo import schedule_due_now, schedule_mark_sent, schedule_reschedule, log_error

def _fmt_local(kick_iso: str, tz: str) -> str:
    try:
        from .util import parse_dt
        dt = parse_dt(kick_iso)
        return dt.astimezone(ZoneInfo(tz)).strftime("%H:%M")
    except Exception:
        return "n/d"

def _current_odds_map(api: APIFootball, fixture_id: int) -> dict:
    try:
        return api.parse_markets_bet365(api.odds_by_fixture(fixture_id))
    except Exception:
        return {}

def _render_value_now(api: APIFootball, cfg: Config, payload: dict) -> str | None:
    sel = payload.get("selection") or {}
    fid = int(sel.get("fixture_id", 0))
    market = sel.get("market")
    home = sel.get("home"); away = sel.get("away")
    kickoff_iso = sel.get("start_time")
    mk = _current_odds_map(api, fid)
    odd = mk.get(market)
    if odd is None:
        return None
    return render_value_single(home, away, market, float(odd), _fmt_local(kickoff_iso, cfg.TZ), cfg.CHANNEL_LINK)

def _render_combo_now(api: APIFootball, cfg: Config, payload: dict) -> str | None:
    events = []
    min_kick = None
    total = 1.0
    for sel in payload.get("selections", []):
        fid = int(sel.get("fixture_id", 0))
        market = sel.get("market")
        home = sel.get("home"); away = sel.get("away")
        kickoff_iso = sel.get("start_time")
        mk = _current_odds_map(api, fid)
        odd = mk.get(market)
        if odd is None:
            return None
        events.append({"home": home, "away": away, "pick": market, "odds": float(odd)})
        total *= float(odd)
        if not min_kick or (kickoff_iso and kickoff_iso < min_kick):
            min_kick = kickoff_iso
    if not events:
        return None
    return render_multipla(events, float(total), _fmt_local(min_kick, cfg.TZ), cfg.CHANNEL_LINK)

def process_due_messages(tg: TelegramClient, api: APIFootball, cfg: Config):
    """
    Prende i messaggi in coda con send_at <= UTC now,
    se payload è JSON rigenera con quote attuali; se stringa, invia così.
    Se non riusciamo a rigenerare (quote mancanti), rimanda di 2 minuti.
    """
    due = schedule_due_now(limit=20)
    for rec in due:
        rec_id = rec["id"]
        payload = rec.get("payload") or ""
        kind = (rec.get("kind") or "").lower()

        text_to_send = None
        # payload JSON?
        if isinstance(payload, str) and payload[:1] in ("{","["):
            try:
                data = json.loads(payload)
            except Exception as e:
                log_error("sender", f"payload json parse error id={rec_id}: {e}")
                # invio raw per non bloccare
                text_to_send = payload
            else:
                if kind == "value":
                    text_to_send = _render_value_now(api, cfg, data)
                elif kind == "combo":
                    text_to_send = _render_combo_now(api, cfg, data)
                else:
                    # altri tipi testuali
                    text_to_send = data.get("text")

                if text_to_send is None:
                    # quote non disponibili ora: riprova tra 2 minuti
                    try:
                        new_dt = (datetime.now(timezone.utc) + timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M:%S")
                        schedule_reschedule(rec_id, new_dt)
                    except Exception as e:
                        log_error("sender", f"resched fail id={rec_id}: {e}")
                    continue
        else:
            # payload pre-formattato vecchio stil
            text_to_send = payload

        try:
            if text_to_send:
                tg.send_message(text_to_send)
                schedule_mark_sent(rec_id)
        except Exception as e:
            log_error("sender", f"send fail id={rec_id}: {e}")
