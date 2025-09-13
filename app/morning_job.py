# app/morning_job.py
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .value_builder import plan_day   # usa il tuo planner
from .templates_schedine import render_value_single, render_multipla
from .repo_sched import ensure_table, enqueue
from .repo_bets import ensure_tables as ensure_bets, create_betslip, add_selection

import random

def _short_id() -> str:
    return str(random.randint(10000, 99999))

def _parse_iso_local(iso_str: str, tz: str):
    if not iso_str: return None
    try:
        return datetime.fromisoformat(iso_str.replace("Z","+00:00")).astimezone(ZoneInfo(tz))
    except Exception:
        return None

def _first_kickoff_local(legs: list, tz: str):
    dts = []
    for leg in legs or []:
        dt = _parse_iso_local(leg.get("kickoff_iso") or "", tz)
        if dt: dts.append(dt)
    return min(dts) if dts else None

def _compute_send_at_utc(first_local: datetime, tz: str) -> str:
    send_local = first_local - timedelta(hours=3)
    clamp = first_local.replace(hour=8, minute=0, second=0, microsecond=0)
    if send_local < clamp: send_local = clamp
    return send_local.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%d %H:%M:%S")

def _kickoff_local_str(dt: datetime) -> str:
    try: return dt.strftime("%H:%M")
    except Exception: return "n/d"

def _safe_send(tg, chat_id: int, text: str):
    try: return tg.send_message(text, chat_id=chat_id)
    except TypeError: return tg.send_message(chat_id, text)
    except Exception:
        try: return tg.send_message(text, chat_id=chat_id)
        except Exception: pass

def run_morning(cfg, tg, api):
    tz = getattr(cfg, "TZ", "Europe/Rome")
    tzinfo = ZoneInfo(tz)
    today = datetime.now(tzinfo).strftime("%Y-%m-%d")
    plan = plan_day(api, cfg, today, want_long_legs=10)

    # blocchi per messaggi + calcolo orari invio
    link = getattr(cfg, "PUBLIC_LINK", "https://t.me/AIProTips")
    blocks = []  # [{kind, legs, payload, first_local}]
    # singole
    for s in plan.get("singole") or []:
        first_local = _parse_iso_local(s.get("kickoff_iso",""), tz) or datetime.now(tzinfo).replace(hour=11, minute=0, second=0, microsecond=0)
        blocks.append({
            "kind": "single",
            "legs": [s],
            "payload": render_value_single(s["home"], s["away"], s["pick"], float(s["odds"]), s.get("kickoff_local", _kickoff_local_str(first_local)), link),
            "first_local": first_local
        })
    # multiple
    def push_combo(key, kind, title):
        blk = plan.get(key)
        if not blk: return
        legs = blk.get("legs") or []; 
        if not legs: return
        first_local = _first_kickoff_local(legs, tz) or datetime.now(tzinfo).replace(hour=11, minute=0, second=0, microsecond=0)
        blocks.append({
            "kind": kind,
            "legs": legs,
            "payload": render_multipla(title, legs, float(blk["total_odds"]), blk.get("kickoff_local", _kickoff_local_str(first_local)), link),
            "first_local": first_local
        })
    push_combo("doppia", "double", "🧩 <b>DOPPIA</b> 🧩")
    push_combo("tripla", "triple", "🎻 <b>TRIPLA</b> 🎻")
    push_combo("quintupla", "quint", "🎬 <b>QUINTUPLA</b> 🎬")
    push_combo("supercombo", "long", "💎 <b>SUPER COMBO</b> 💎")

    if not blocks:
        _safe_send(tg, int(cfg.ADMIN_ID), "<b>📋 Report 08:00</b>\nNessuna schedina pianificata oggi.")
        return

    # accoda invii + scrivi DB schedine/selezioni per il Closer
    from .repo_sched import ensure_table as ensure_sched
    ensure_sched(); ensure_bets()
    planned = []
    for b in blocks:
        first_local = b["first_local"]
        send_at_utc = _compute_send_at_utc(first_local, tz)
        sid = _short_id()
        enqueue(sid, b["kind"], b["payload"], send_at_utc)
        planned.append((sid, b["kind"], first_local))

        # scrivi DB betslip + selections per tracking
        code = f"{today.replace('-','')}-{sid}"
        legs = b["legs"]
        total_odds = 1.0
        for l in legs: total_odds *= float(l["odds"])
        bet_id = create_betslip(code, 
                                {"single":"single","double":"double","triple":"triple","quint":"quint","long":"long"}[b["kind"]],
                                today, float(total_odds), len(legs))
        for l in legs:
            add_selection(bet_id, l, tz)

    # report
    lines = ["<b>📋 Report 08:00</b>", "<b>Schedine pianificate</b>"]
    for sid, kind, fl in planned:
        # mostra orario locale di invio (fl - 3h, clamp >= 08:00)
        send_loc = max(fl - timedelta(hours=3), fl.replace(hour=8, minute=0, second=0, microsecond=0))
        lines.append(f"ID <b>{sid}</b> — {kind} — invio: <b>{send_loc.strftime('%H:%M')}</b>")
    _safe_send(tg, int(cfg.ADMIN_ID), "\n".join(lines))
