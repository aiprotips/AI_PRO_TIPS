import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .api_football import APIFootball
from .telegram_client import TelegramClient
from .config import Config
from .templates import render_value_single, render_multipla
from .repo import schedule_due_now, schedule_mark_sent, schedule_reschedule, log_error

MAX_RETRIES = 6         # fino a ~12 minuti di attesa
RETRY_DELAY_MIN = 2
MIN_ODD_VALID = 1.06

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

def _odd_ok(odd: float, lo: float, hi: float) -> bool:
    try:
        x = float(odd)
    except Exception:
        return False
    if x < MIN_ODD_VALID:
        return False
    return lo <= x <= hi

def _render_value_now(api: APIFootball, cfg: Config, payload: dict) -> str | None:
    sel = payload.get("selection") or {}
    rng = payload.get("range") or {}
    lo = float(rng.get("lo", 1.10)); hi = float(rng.get("hi", 3.00))
    fid = int(sel.get("fixture_id", 0))
    mk = _mk(api, fid)
    odd = mk.get(sel.get("market"))
    if odd is None or not _odd_ok(odd, lo, hi):
        return None
    return render_value_single(sel.get("home"), sel.get("away"), sel.get("market"),
                               float(odd), _fmt_local(sel.get("start_time"), cfg.TZ), cfg.CHANNEL_LINK)

def _render_combo_now(api: APIFootball, cfg: Config, payload: dict) -> str | None:
    sels = payload.get("selections") or []
    rng = payload.get("range") or {}
    lo = float(rng.get("lo", 1.10)); hi = float(rng.get("hi", 2.50))
    events = []; total=1.0; min_kick=None
    for sel in sels:
        fid = int(sel.get("fixture_id", 0))
        mk = _mk(api, fid)
        odd = mk.get(sel.get("market"))
        if odd is None or not _odd_ok(odd, lo, hi):
            return None
        events.append({"home": sel.get("home"), "away": sel.get("away"), "pick": sel.get("market"), "odds": float(odd)})
        total *= float(odd)
        k = sel.get("start_time","")
        if not min_kick or k < min_kick: min_kick = k
    if not events:
        return None
    return render_multipla(events, float(total), _fmt_local(min_kick, cfg.TZ), cfg.CHANNEL_LINK)

def _resched_with_retry(rec: dict, reason: str):
    rec_id = rec["id"]
    # bump retry counter in notes
    notes = (rec.get("notes") or "")
    try_count = 0
    if notes.startswith("retry="):
        try_count = int(notes.split("=",1)[1])
    if try_count >= MAX_RETRIES:
        log_error("sender", f"id={rec_id} max retry; motivo: {reason}")
        return  # resta QUEUED, ma non spingiamo più
    new_dt = (datetime.now(timezone.utc) + timedelta(minutes=RETRY_DELAY_MIN)).strftime("%Y-%m-%d %H:%M:%S")
    from .db import get_session
    from sqlalchemy import text
    with get_session() as s:
        s.execute(text("UPDATE scheduled_messages SET send_at=:sa, notes=:n WHERE id=:i AND status='QUEUED'"),
                  {"sa": new_dt, "n": f"retry={try_count+1}", "i": rec_id})
        s.commit()
    log_error("sender", f"id={rec_id} rimandato: {reason}")

def process_due_messages(tg: TelegramClient, api: APIFootball, cfg: Config):
    due = schedule_due_now(limit=30)
    for rec in due:
        payload = rec.get("payload") or ""
        kind = (rec.get("kind") or "").lower()
        text_to_send = None

        if isinstance(payload, str) and payload[:1] in ("{","["):
            try:
                data = json.loads(payload)
            except Exception as e:
                log_error("sender", f"payload json parse error id={rec['id']}: {e}")
                text_to_send = payload
            else:
                if kind == "value":
                    text_to_send = _render_value_now(api, cfg, data)
                elif kind == "combo":
                    text_to_send = _render_combo_now(api, cfg, data)
                else:
                    text_to_send = data.get("text")

                if not text_to_send:
                    _resched_with_retry(rec, "odd non disponibile o fuori range/freschezza")
                    continue
        else:
            # legacy: manda così (sconsigliato)
            text_to_send = payload

        try:
            tg.send_message(text_to_send)
            schedule_mark_sent(rec["id"])
        except Exception as e:
            log_error("sender", f"send fail id={rec['id']}: {e}")
