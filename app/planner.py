# app/planner.py
from __future__ import annotations
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .api_football import APIFootball
from .templates_schedine import render_value_single, render_multipla, render_report
from .repo_sched import ensure_table, enqueue, list_today
from .live_alerts import LiveAlerts

SAFE_MARKETS = (
    "Over 1.5","Under 3.5","1X","X2","No Gol","Gol","Over 0.5",
    "Under 2.5","Over 2.5","1","2"   # meno preferiti ma utili per varianza
)

# range per-leg
RANGE_SINGLE   = (1.50, 1.80)
RANGE_DOUBLE   = (1.30, 1.50)
RANGE_TRIPLE   = (1.20, 1.50)
RANGE_QUINT    = (1.20, 1.50)
RANGE_LONG     = (1.10, 1.36)

MIN_TOTAL_QUINT = 4.0
MIN_TOTAL_LONG  = 6.0

def _is_allowed(league_country: str, league_name: str) -> bool:
    try:
        from .leagues import allowed_league
        return allowed_league(league_country, league_name)
    except Exception:
        return True

def _within_time_window(kickoff_iso: str, tz: str) -> bool:
    try:
        dt = datetime.fromisoformat(kickoff_iso.replace("Z","+00:00"))
        local = dt.astimezone(ZoneInfo(tz))
        return 8 <= local.hour < 24
    except Exception:
        return True

def _short_id() -> str:
    return str(random.randint(10000, 99999))

def _first_kickoff_local(selections: list, tz: str) -> datetime:
    dts = []
    for s in selections:
        dt = datetime.fromisoformat(s["kickoff_iso"].replace("Z","+00:00")).astimezone(ZoneInfo(tz))
        dts.append(dt)
    return min(dts)

def _send_at_utc_from_first_kickoff(first_local: datetime, tz: str) -> datetime:
    send_local = first_local - timedelta(hours=3)
    clamp = first_local.replace(hour=8, minute=0, second=0, microsecond=0)
    if send_local < clamp:
        send_local = clamp
    return send_local.astimezone(ZoneInfo("UTC"))

def _kickoff_local_str(dt_iso: str, tz: str) -> str:
    dt = datetime.fromisoformat(dt_iso.replace("Z","+00:00")).astimezone(ZoneInfo(tz))
    return dt.strftime("%H:%M")

def _pick_candidates(entries: list, per_leg_range, used_fixtures: set, max_per_market: int | None = None):
    lo, hi = per_leg_range
    pool = []
    for e in entries:
        fid = int(e["fixture_id"])
        if fid in used_fixtures:
            continue
        if not _is_allowed(e["league_country"], e["league_name"]):
            continue
        if not _within_time_window(e["kickoff_iso"], "Europe/Rome"):
            continue
        mk = e["markets"]
        # seleziona i mercati dentro range, priorità SAFE_MARKETS
        for m in SAFE_MARKETS:
            if m in mk:
                try:
                    odd = float(mk[m])
                except:
                    continue
                if lo <= odd <= hi:
                    pool.append((fid, m, odd, e))
    # ordina “più probabile” ~ odd crescente con piccolo peso per varianza
    pool.sort(key=lambda x: (x[2], SAFE_MARKETS.index(x[1]) if x[1] in SAFE_MARKETS else 99))
    return pool

def _build_pack(entries, legs, per_leg_range, tz: str, kind_title: str, min_total: float | None, channel_link: str):
    used = set()
    sel = []
    chosen_markets_count = {}
    # limite varianza: non più di 2 uguali per combo
    max_per_market = 2 if legs >= 3 else 3
    pool = _pick_candidates(entries, per_leg_range, used, max_per_market)
    for fid, m, odd, e in pool:
        if fid in used:
            continue
        if chosen_markets_count.get(m, 0) >= max_per_market:
            continue
        sel.append({
            "fixture_id": fid,
            "league_country": e["league_country"],
            "league_name": e["league_name"],
            "home": e["home"], "away": e["away"],
            "pick": m, "odd": float(odd),
            "kickoff_iso": e["kickoff_iso"]
        })
        used.add(fid)
        chosen_markets_count[m] = chosen_markets_count.get(m, 0) + 1
        if len(sel) >= legs:
            break
    if len(sel) < legs:
        return None  # non abbastanza scelte di valore

    total = 1.0
    for s in sel:
        total *= float(s["odd"])

    if min_total and total < min_total:
        # prova ad alzare leggermente la media sostituendo 1-2 gambe con odd leggermente più alte
        pool2 = [x for x in pool if x[0] not in {s["fixture_id"] for s in sel}]
        pool2.sort(key=lambda x: -x[2])  # più alte prima
        i = 0
        while total < min_total and i < len(pool2):
            # rimpiazza la gamba con odd più bassa
            idx_low = min(range(len(sel)), key=lambda j: sel[j]["odd"])
            cand = pool2[i]; i += 1
            # evita duplicati di match
            if cand[0] in {s["fixture_id"] for s in sel}:
                continue
            # sostituisci
            total /= sel[idx_low]["odd"]
            sel[idx_low] = {
                "fixture_id": cand[0],
                "league_country": cand[3]["league_country"],
                "league_name": cand[3]["league_name"],
                "home": cand[3]["home"], "away": cand[3]["away"],
                "pick": cand[1], "odd": float(cand[2]),
                "kickoff_iso": cand[3]["kickoff_iso"]
            }
            total *= float(sel[idx_low]["odd"])
        if min_total and total < min_total:
            return None

    first_local = _first_kickoff_local(sel, tz)
    send_at_utc = _send_at_utc_from_first_kickoff(first_local, tz)
    kickoff_local = first_local.strftime("%H:%M")

    # messaggio canale
    preview = render_multipla(kind_title, sel, total, kickoff_local, channel_link)
    return {
        "selections": sel,
        "total_odds": total,
        "send_at_utc": send_at_utc.strftime("%Y-%m-%d %H:%M:%S"),
        "send_at_local": first_local.replace(hour=first_local.hour-3 if first_local.hour>=3 else 8, minute=0).strftime("%H:%M"),
        "preview": preview
    }

class DailyPlanner:
    def __init__(self, cfg, tg, api: APIFootball, la: LiveAlerts | None = None):
        self.cfg = cfg
        self.tg = tg
        self.api = api
        self.la = la
        self.tz = cfg.TZ
        ensure_table()  # assicura scheduled_messages

    def _entries_for_date(self, date_str: str):
        # Quote Bet365 già parse-ate dal tuo api_football
        return self.api.entries_by_date_bet365(date_str)

    def run_08_tasks(self):
        tz = ZoneInfo(self.tz)
        today = datetime.now(tz).strftime("%Y-%m-%d")
        # 1) Rebuild watchlist favorite ≤1.26 (live alerts)
        if self.la:
            try:
                self.la.build_morning_watchlist()
            except Exception:
                pass

        # 2) Genera le schedine del giorno
        entries = self._entries_for_date(today)
        channel_link = "https://t.me/AIProTips"

        # pool per singles (1.50–1.80) con forte priorità a mercati stabili
        pool_single = _pick_candidates(entries, RANGE_SINGLE, used_fixtures=set())
        singles = []
        used_singles = set()
        for fid, m, odd, e in pool_single:
            if fid in used_singles:
                continue
            singles.append({
                "fixture_id": fid,
                "league_country": e["league_country"],
                "league_name": e["league_name"],
                "home": e["home"], "away": e["away"],
                "pick": m, "odd": float(odd),
                "kickoff_iso": e["kickoff_iso"]
            })
            used_singles.add(fid)
            if len(singles) >= 2:
                break

        planned_rows = []

        # Enqueue SINGLES (fino a 2)
        for s in singles:
            first_local = datetime.fromisoformat(s["kickoff_iso"].replace("Z","+00:00")).astimezone(ZoneInfo(self.tz))
            send_at_utc = _send_at_utc_from_first_kickoff(first_local, self.tz)
            sid = _short_id()
            payload = render_value_single(s["home"], s["away"], s["pick"], float(s["odd"]),
                                          first_local.strftime("%H:%M"), channel_link)
            enqueue(sid, "single", payload, send_at_utc.strftime("%Y-%m-%d %H:%M:%S"))
            planned_rows.append({
                "short_id": sid,
                "kind": "single",
                "send_at_local": (send_at_utc.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo(self.tz))).strftime("%H:%M"),
                "preview": payload
            })

        # Enqueue DOPPIA, TRIPLA, QUINTUPLA, LONG (8-12)
        # DOPPIA
        pack = _build_pack(entries, 2, RANGE_DOUBLE, self.tz, "🧩 <b>DOPPIA</b> 🧩", None, channel_link)
        if pack:
            sid = _short_id()
            enqueue(sid, "double", pack["preview"], pack["send_at_utc"])
            planned_rows.append({"short_id": sid, "kind": "double", "send_at_local": pack["send_at_local"], "preview": pack["preview"]})

        # TRIPLA
        pack = _build_pack(entries, 3, RANGE_TRIPLE, self.tz, "🎻 <b>TRIPLA</b> 🎻", None, channel_link)
        if pack:
            sid = _short_id()
            enqueue(sid, "triple", pack["preview"], pack["send_at_utc"])
            planned_rows.append({"short_id": sid, "kind": "triple", "send_at_local": pack["send_at_local"], "preview": pack["preview"]})

        # QUINTUPLA con min totale >= 4.0
        pack = _build_pack(entries, 5, RANGE_QUINT, self.tz, "🎬 <b>QUINTUPLA</b> 🎬", MIN_TOTAL_QUINT, channel_link)
        if pack:
            sid = _short_id()
            enqueue(sid, "quint", pack["preview"], pack["send_at_utc"])
            planned_rows.append({"short_id": sid, "kind": "quint", "send_at_local": pack["send_at_local"], "preview": pack["preview"]})

        # LONG 8-12 con min totale >= 6.0 (prova 8; se non c'è valore, salta)
        for n in range(8, 13):
            pack = _build_pack(entries, n, RANGE_LONG, self.tz, "💎 <b>SUPER COMBO</b> 💎", MIN_TOTAL_LONG, channel_link)
            if pack:
                sid = _short_id()
                enqueue(sid, "long", pack["preview"], pack["send_at_utc"])
                planned_rows.append({"short_id": sid, "kind": f"long x{n}", "send_at_local": pack["send_at_local"], "preview": pack["preview"]})
                break  # una sola long

        # 3) Report DM admin: schedine + watchlist
        watch_rows = []
        if self.la and getattr(self.la, "watch", None):
            for fid, rec in self.la.watch.items():
                watch_rows.append({
                    "league": rec["league"],
                    "fav": rec["fav_name"],
                    "other": rec["other_name"],
                    "pre": rec["pre_odd"],
                })
        report = render_report(self.tz, planned_rows, watch_rows)
        try:
            self.tg.send_message(report, chat_id=self.cfg.ADMIN_ID, disable_web_page_preview=True)
        except Exception:
            pass
