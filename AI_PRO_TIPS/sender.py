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

def _mk(api: APIFootball, fixture_id: int) -> dict:
    try:
        return api.parse_markets_bet365(api.odds_by_fixture(fixture_id))
    except Exception:
        return {}

def _render_value_now(api: APIFootball, cfg: Config, sel: dict) -> str | None:
    mk = _mk(api, int(sel.get("fixture_id", 0)))
    odd = mk.get(sel.get("market"))
    if odd is None:
        return None
    return render_value_single(sel.get("home"), sel.get("away"), sel.get("market"),
                               float(odd), _fmt_local(sel.get("start_time"), cfg.TZ), cfg.CHANNEL_LINK)

def _render_combo_now(api: APIFootball, cfg: Config, selections: list) -> tuple[str | None, float | None, str | None]:
    events = []; total=1.0; min_kick=None
    for sel in selections:
        mk = _mk(api, int(sel.get("fixture_id", 0)))
        odd = mk.get(sel.get("market"))
        if odd is None:
            return None, None, None
        events.append({"home": sel.get("home"), "away": sel.get("away"), "pick": sel.get("market"), "odds": float(odd)})
        total *= float(odd)
        if not min_kick or sel.get("start_time","") < min_kick:
            min_kick = sel.get("start_time")
    if not events:
        return None, None, None
    txt = render_multipla(events, float(total), _fmt_local(min_kick, cfg.TZ), cfg.CHANNEL_LINK)
    return txt, total, min_kick

def process_due_messages(tg: TelegramClient, api: APIFootball, cfg: Config):
    due = schedule_due_now(limit=20)
    for rec in due:
        rec_id = rec["id"]; kind = (rec.get("kind") or "").lower()
        payload = rec.get("payload") or ""
        text_to_send = None

        # JSON? allora rigenero con quote attuali
        if isinstance(payload, str) and payload[:1] in ("{","["):
            try:
                data = json.loads(payload)
            except Exception as e:
                log_error("sender", f"payload json parse error id={rec_id}: {e}")
                text_to_send = payload
            else:
                if kind == "value":
                    sel = data.get("selection") or {}
                    text_to_send = _render_value_now(api, cfg, sel)
                elif kind == "combo":
                    sels = data.get("selections") or []
                    text_to_send, _, _ = _render_combo_now(api, cfg, sels)
                else:
                    text_to_send = data.get("text")
        else:
            text_to_send = payload  # legacy

        if not text_to_send:
            # quote non disponibili adesso: rimanda di 2 minuti
            try:
                new_dt = (datetime.now(timezone.utc) + timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M:%S")
                schedule_reschedule(rec_id, new_dt)
            except Exception as e:
                log_error("sender", f"resched fail id={rec_id}: {e}")
            continue

        try:
            tg.send_message(text_to_send)
            schedule_mark_sent(rec_id)
        except Exception as e:
            log_error("sender", f"send fail id={rec_id}: {e}")
