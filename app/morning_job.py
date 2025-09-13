# app/morning_job.py
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .value_builder import plan_day   # usa il tuo planner
from .templates_schedine import render_value_single, render_multipla
from .repo_sched import ensure_table, enqueue

import random

def _short_id() -> str:
    return str(random.randint(10000, 99999))

def _parse_iso_local(iso_str: str, tz: str) -> datetime | None:
    if not iso_str:
        return None
    try:
        # ISO dell'API è UTC con suffisso Z; normalizziamo
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.astimezone(ZoneInfo(tz))
    except Exception:
        return None

def _first_kickoff_local(legs: list, tz: str) -> datetime | None:
    dts = []
    for leg in legs or []:
        dt = _parse_iso_local(leg.get("kickoff_iso") or "", tz)
        if dt:
            dts.append(dt)
    return min(dts) if dts else None

def _compute_send_at_utc(first_local: datetime, tz: str) -> str:
    """
    Invio = (primo kickoff - 3h), ma non prima delle 08:00 locali.
    Ritorna stringa UTC 'YYYY-MM-DD HH:MM:SS'
    """
    send_local = first_local - timedelta(hours=3)
    clamp = first_local.replace(hour=8, minute=0, second=0, microsecond=0)
    if send_local < clamp:
        send_local = clamp
    return send_local.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%d %H:%M:%S")

def _kickoff_local_str(first_local: datetime) -> str:
    try:
        return first_local.strftime("%H:%M")
    except Exception:
        return "n/d"

def _safe_send(tg, chat_id: int, text: str):
    """
    Firma a prova di wrapper: prima (text, chat_id=...), fallback (chat_id, text).
    """
    try:
        return tg.send_message(text, chat_id=chat_id)
    except TypeError:
        return tg.send_message(chat_id, text)
    except Exception:
        try:
            return tg.send_message(text, chat_id=chat_id)
        except Exception:
            pass

def _make_blocks_from_plan(cfg, plan: dict) -> list[dict]:
    """
    Converte il dict del planner in una lista di blocchi schedinabili:
    ciascun blocco = {"kind","payload","legs":[{home,away,pick,odds,kickoff_iso}], "first_local": datetime}
    """
    tz = getattr(cfg, "TZ", "Europe/Rome")
    link = getattr(cfg, "PUBLIC_LINK", "https://t.me/AIProTips")
    blocks: list[dict] = []

    # SINGOLE (lista di leg pronte dal planner)
    for s in plan.get("singole") or []:
        # s: {home,away,pick,odds,kickoff_iso,kickoff_local,...}
        first_local = _parse_iso_local(s.get("kickoff_iso") or "", tz)
        kickoff_local_str = s.get("kickoff_local") or (_kickoff_local_str(first_local) if first_local else "n/d")
        payload = render_value_single(
            s.get("home","Home"),
            s.get("away","Away"),
            s.get("pick",""),
            float(s.get("odds", 0.0) or 0.0),
            kickoff_local_str,
            link
        )
        blocks.append({
            "kind": "single",
            "payload": payload,
            "legs": [s],
            "first_local": first_local
        })

    # MULTIPLE
    def _push_combo(key: str, kind: str, title: str):
        blk = plan.get(key)
        if not blk:
            return
        legs = blk.get("legs") or []
        if not legs:
            return
        first_local = _first_kickoff_local(legs, tz)
        kickoff_local_str = blk.get("kickoff_local") or (_kickoff_local_str(first_local) if first_local else "n/d")
        total = float(blk.get("total_odds", 0.0) or 0.0)
        payload = render_multipla(title, legs, total, kickoff_local_str, link)
        blocks.append({
            "kind": kind,
            "payload": payload,
            "legs": legs,
            "first_local": first_local
        })

    _push_combo("doppia",     "double", "🧩 <b>DOPPIA</b> 🧩")
    _push_combo("tripla",     "triple", "🎻 <b>TRIPLA</b> 🎻")
    _push_combo("quintupla",  "quint",  "🎬 <b>QUINTUPLA</b> 🎬")
    _push_combo("supercombo", "long",   "💎 <b>SUPER COMBO</b> 💎")

    # ordina i blocchi per primo kickoff
    blocks.sort(key=lambda b: (b.get("first_local") or datetime.max))
    return blocks

def run_morning(cfg, tg, api):
    """
    Job 08:00:
      - genera piano della giornata con plan_day(...)
      - costruisce blocchi e li accoda per invio 3h prima del primo kickoff (min 08:00)
      - invia report DM con ID / formato / orario locale di invio
    """
    tz = getattr(cfg, "TZ", "Europe/Rome")
    tzinfo = ZoneInfo(tz)
    today = datetime.now(tzinfo).strftime("%Y-%m-%d")

    # 1) genera piano (usa il TUO planner)
    plan = plan_day(api, cfg, today, want_long_legs=10)

    # 2) costruisci i blocchi (messaggi + legs)
    blocks = _make_blocks_from_plan(cfg, plan)

    if not blocks:
        _safe_send(tg, int(cfg.ADMIN_ID), "<b>📋 Report 08:00</b>\nNessuna schedina pianificata oggi.")
        return

    # 3) accoda invii in scheduled_messages
    ensure_table()
    rows_for_report = []
    for b in blocks:
        first_local = b.get("first_local")
        if not first_local:
            # fallback: se manca kickoff, manda comunque dopo le 11:00 locali
            first_local = datetime.now(tzinfo).replace(hour=11, minute=0, second=0, microsecond=0)
        send_at_utc = _compute_send_at_utc(first_local, tz)
        sid = _short_id()
        enqueue(sid, b.get("kind") or "single", b.get("payload") or "", send_at_utc)

        # prepara riga report
        # mostra l'orario locale effettivo (send_at_utc convertito)
        try:
            send_dt_local = datetime.fromisoformat(send_at_utc.replace(" ", "T")).replace(tzinfo=ZoneInfo("UTC")).astimezone(tzinfo)
            send_hhmm = send_dt_local.strftime("%H:%M")
        except Exception:
            send_hhmm = "n/d"
        rows_for_report.append((sid, b.get("kind") or "single", send_hhmm))

    # 4) report DM admin
    lines = ["<b>📋 Report 08:00</b>", "<b>Schedine pianificate</b>"]
    for sid, kind, hhmm in rows_for_report:
        lines.append(f"ID <b>{sid}</b> — {kind} — invio: <b>{hhmm}</b>")
    report = "\n".join(lines)
    _safe_send(tg, int(cfg.ADMIN_ID), report)
