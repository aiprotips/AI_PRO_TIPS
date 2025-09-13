# app/value_builder.py
from __future__ import annotations
from typing import Dict, Any, List, Tuple
from math import pow
from collections import Counter
from .stats_engine import StatsEngine, clamp

# -------------------------
# Range quota per formato (prima passata "soft")
# -------------------------
RANGES = {
    "single":  (1.45, 1.65),
    "double":  (1.28, 1.42),
    "triple":  (1.22, 1.35),
    "quint":   (1.18, 1.30),
    "long":    (1.10, 1.22),  # 8–12 eventi
}

# Soglie 'value' (delta minimo vs p_imp)
VALUE_TH = {"single":0.06, "double":0.04, "triple":0.03, "quint":0.02, "long":0.01}

# Soglie fallback 'sicurezza' (probabilità nostra per leg)
SAFE_TH  = {"single":0.75, "double":0.70, "triple":0.65, "quint":0.60, "long":0.55}

# Soglie minime PER-LEG e MEDIA schedina (per alzare il tasso di cassa)
MIN_PMOD_PER_LEG = {"single":0.78, "double":0.74, "triple":0.70, "quint":0.68, "long":0.64}
MIN_AVG_PMOD     = {"single":0.78, "double":0.73, "triple":0.69, "quint":0.67, "long":0.63}

# Ordine di "sicurezza" per fallback
SAFE_MARKETS_ORDER = ("Over 1.5","Under 3.5","1X","X2","No Gol","Over 0.5","Under 2.5","Gol","1","2")

# Minimi di quota TOTALE richiesti
MIN_TOTAL = {"quint": 4.00, "long": 6.00}

# Cap massimo per quote per-leg nel "secondo pass" (quando serve alzare)
UPPER_CAP = {"single":1.70,"double":1.50,"triple":1.45,"quint":1.45,"long":1.30}

# Target quota totali per lo scoring (per misurare “quanto ci avviciniamo all’ideale”)
TARGET_TOTAL = {"single":1.55,"double":1.90,"triple":2.10,"quint":4.00,"long":6.00}

# Scoring pesi (priorità alla presa, poi quota, poi varietà)
ALPHA = 0.70  # peso probabilità di cassa del ticket
BETA  = 0.20  # peso “quota/target”
GAMMA = 0.10  # peso varianza interna al ticket

# -------------------------
# CATEGORIE per la VARIANZA
# -------------------------
def market_category(m: str) -> str:
    m = m.strip()
    if m in ("1","2"):                 return "outright"
    if m in ("1X","12","X2"):          return "double_chance"
    if m in ("Over 0.5","Over 1.5","Over 2.5"): return "totals_over"
    if m in ("Under 2.5","Under 3.5"): return "totals_under"
    if m in ("Gol","No Gol"):          return "btts"
    return "other"

# Profili di diversità minimi per formato
DIVERSITY_PROFILE = {
    "single": {"min_cats": 1, "max_per_cat": 1},
    "double": {"min_cats": 2, "max_per_cat": 1},
    "triple": {"min_cats": 2, "max_per_cat": 2},
    "quint":  {"min_cats": 3, "max_per_cat": 2},
    "long":   {"min_cats": 4, "max_per_cat": None},
}

def _p_imp(odd: float) -> float:
    try:
        if odd and odd > 1.001:
            return clamp(1.0 / float(odd), 0.01, 0.99)
    except Exception:
        pass
    return 0.0

def _avg(a: float, b: float) -> float: return (a + b) / 2.0

def _strength_gap(markets: Dict[str, float]) -> float:
    p1 = _p_imp(markets.get("1", 0.0)); p2 = _p_imp(markets.get("2", 0.0))
    return abs(p1 - p2)

def _fav_side(markets: Dict[str, float]) -> str:
    p1 = _p_imp(markets.get("1", 0.0)); p2 = _p_imp(markets.get("2", 0.0))
    return "home" if p1 >= p2 else "away"

def _adj_market(market: str, markets: Dict[str, float], feats: Dict[str, Any]) -> float:
    """Aggiusta p_imp con stats in [-0.12, +0.12] (semplice e trasparente)."""
    h, a = feats["home"], feats["away"]
    tot_avg = _avg(h["tot_avg"], a["tot_avg"])
    btts_avg = _avg(h["btts"], a["btts"])
    cs_avg = _avg(h["cs"], a["cs"])
    gap = _strength_gap(markets)
    fav = _fav_side(markets)
    form_h = h["form_pts_rate"]; form_a = a["form_pts_rate"]

    adj = 0.0
    if market == "Over 0.5":
        adj = 0.02*(tot_avg - 2.3) + 0.02*(btts_avg - 0.55)
    elif market == "Over 1.5":
        adj = 0.04*(_avg(h["over15"], a["over15"]) - 0.60) + 0.03*(tot_avg - 2.4) + 0.02*(btts_avg - 0.55)
    elif market == "Over 2.5":
        adj = 0.05*(_avg(h["over25"], a["over25"]) - 0.50) + 0.03*(tot_avg - 2.6) + 0.02*(btts_avg - 0.55)
    elif market == "Under 2.5":
        adj = 0.05*(0.50 - _avg(h["over25"], a["over25"])) + 0.03*(2.5 - tot_avg) + 0.02*(0.55 - btts_avg)
    elif market == "Under 3.5":
        adj = 0.05*(_avg(h["under35"], a["under35"]) - 0.60) + 0.03*(3.0 - tot_avg) + 0.02*(0.55 - btts_avg)
    elif market == "Gol":
        adj = 0.06*(btts_avg - 0.50) + 0.03*(tot_avg - 2.5) - 0.02*(cs_avg - 0.30)
    elif market == "No Gol":
        adj = 0.06*(cs_avg - 0.30) + 0.03*(0.55 - btts_avg) + 0.02*(gap - 0.12)
    elif market == "1X":
        base = 0.05*(form_h - 0.50) + 0.03*(gap - 0.12) - 0.02*(form_a - 0.50)
        adj = base if fav == "home" else base*0.5
    elif market == "X2":
        base = 0.05*(form_a - 0.50) + 0.03*(gap - 0.12) - 0.02*(form_h - 0.50)
        adj = base if fav == "away" else base*0.5
    elif market == "1":
        adj = 0.07*(form_h - 0.50) + 0.04*(gap - 0.12) - 0.03*(form_a - 0.50)
    elif market == "2":
        adj = 0.07*(form_a - 0.50) + 0.04*(gap - 0.12) - 0.03*(form_h - 0.50)
    return clamp(adj, -0.12, 0.12)

def _mk_candidate(entry: Dict[str, Any], market: str, feats: Dict[str, Any]) -> Dict[str, Any]:
    mk = entry["markets"]
    if market not in mk: return {}
    odd = float(mk[market]); p_imp = _p_imp(odd)
    if p_imp <= 0.0: return {}
    adj = _adj_market(market, mk, feats)
    p_mod = clamp(p_imp + adj, 0.01, 0.99)
    value = p_mod - p_imp
    return {
        "fixture_id": entry["fixture_id"],
        "league": f"{entry['league_country']} — {entry['league_name']}",
        "home": entry["home"], "away": entry["away"],
        "kickoff_iso": entry["kickoff_iso"],
        "market": market, "odd": odd,
        "p_imp": round(p_imp, 4), "p_mod": round(p_mod, 4), "value": round(value, 4),
        "cat": market_category(market),
        "markets_all": mk,
    }

def _fits_range(odd: float, lo: float, hi: float) -> bool:
    try:
        x = float(odd); return lo <= x <= hi
    except Exception: return False

# -------------------------
# VETO RISCHIO (no pick forzati)
# -------------------------
def _risk_veto(c: Dict[str, Any]) -> bool:
    mk = c.get("markets_all") or {}
    m = c["market"]
    p1 = _p_imp(mk.get("1", 0.0)); p2 = _p_imp(mk.get("2", 0.0))
    gap = abs(p1 - p2)
    if m in ("1","2") and gap < 0.08:
        return True
    u35 = float(mk.get("Under 3.5", 99))
    u25 = float(mk.get("Under 2.5", 99))
    o25 = float(mk.get("Over 2.5", 0))
    if m == "Gol" and (u35 <= 1.22 or u25 <= 1.35):
        return True
    if m == "No Gol" and (o25 <= 1.60):
        return True
    return False

# -------------------------
# COSTRUZIONE CANDIDATI
# -------------------------
def build_daily_candidates(api, cfg, date_str: str) -> List[Dict[str, Any]]:
    entries = api.entries_by_date_bet365(date_str)
    try:
        from .leagues import allowed_league
        entries = [e for e in entries if allowed_league(e["league_country"], e["league_name"])]
    except Exception:
        pass
    se = StatsEngine(api)
    out: List[Dict[str, Any]] = []
    for e in entries:
        fid = int(e["fixture_id"])
        try:
            feats = se.features_for_fixture(fid)
        except Exception:
            continue
        for m in ("1","X","2","1X","12","X2","Over 0.5","Over 1.5","Over 2.5","Under 2.5","Under 3.5","Gol","No Gol"):
            cand = _mk_candidate(e, m, feats)
            if not cand: 
                continue
            if _risk_veto(cand):
                continue
            out.append(cand)
    return out

# -------------------------
# Utility selezione
# -------------------------
def _dedup_by_fixture(picks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set(); out = []
    for p in picks:
        fid = int(p["fixture_id"])
        if fid in seen: continue
        seen.add(fid); out.append(p)
    return out

def _diversify_league(picks: List[Dict[str, Any]], max_per_league: int = 3) -> List[Dict[str, Any]]:
    cnt: Dict[str, int] = {}; out: List[Dict[str, Any]] = []
    for p in picks:
        lg = p["league"]
        if cnt.get(lg, 0) >= max_per_league: continue
        cnt[lg] = cnt.get(lg, 0) + 1; out.append(p)
    return out

def _compute_total(legs: List[Dict[str, Any]]) -> float:
    tot = 1.0
    for p in legs:
        try: tot *= float(p["odd"])
        except Exception: pass
    return round(tot, 2)

def _format_block(label: str, legs: List[Dict[str, Any]], tz_str: str) -> str:
    if not legs: return f"<b>{label}</b>\nN/D"
    lines = [f"<b>{label}</b>"]
    for p in legs:
        lines.append(f"• {p['home']} 🆚 {p['away']} — {p['market']} <b>{p['odd']:.2f}</b>")
    if len(legs) > 1:
        lines.append(f"Totale: <b>{_compute_total(legs):.2f}</b>")
    try:
        from dateutil import parser as duparser
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(tz_str)
        first = min(legs, key=lambda x: x["kickoff_iso"])
        dt = duparser.isoparse(first["kickoff_iso"]).astimezone(tz)
        lines.append(f"🕒 {dt.strftime('%H:%M')}")
    except Exception:
        pass
    return "\n".join(lines)

# -------------------------
# DIVERSITÀ & SELEZIONE DI BASE
# -------------------------
def _enforce_diversity(sorted_pool: List[Dict[str, Any]], n_legs: int, fmt: str,
                       day_cat_bias: Counter | None = None) -> List[Dict[str, Any]]:
    profile = DIVERSITY_PROFILE[fmt]
    max_per_cat = profile["max_per_cat"]
    min_cats = profile["min_cats"]
    if fmt == "long" and (max_per_cat is None):
        max_per_cat = max(2, (n_legs + 2)//3)

    picks: List[Dict[str, Any]] = []
    seen_fix = set()
    cat_count = Counter()

    for c in sorted_pool:
        if len(picks) >= n_legs: break
        if c["fixture_id"] in seen_fix: continue
        cat = c["cat"]
        if day_cat_bias and day_cat_bias.get(cat, 0) > max(0, day_cat_bias.total()//3):
            continue
        if max_per_cat and cat_count[cat] >= max_per_cat:
            continue
        fmt_key = "single" if n_legs == 1 else fmt
        if c["p_mod"] < MIN_PMOD_PER_LEG[fmt_key]:
            continue
        picks.append(c); seen_fix.add(c["fixture_id"]); cat_count[cat] += 1

    def cats_ok(ps: List[Dict[str, Any]]) -> bool:
        return len({p["cat"] for p in ps}) >= min_cats

    if len(picks) == n_legs and cats_ok(picks):
        fmt_key = "single" if n_legs == 1 else fmt
        if sum(p["p_mod"] for p in picks)/n_legs >= MIN_AVG_PMOD[fmt_key]:
            return picks

    # miglioramenti varianza/media p_mod
    improved = picks[:]
    pool = [c for c in sorted_pool if c not in improved]
    for i in range(len(improved)):
        for cand in pool:
            if cand["fixture_id"] in {p["fixture_id"] for p in improved}: continue
            trial = improved[:]; trial[i] = cand
            if max_per_cat and Counter([t["cat"] for t in trial])[cand["cat"]] > max_per_cat:
                continue
            if not cats_ok(trial): continue
            fmt_key = "single" if n_legs == 1 else fmt
            if any(t["p_mod"] < MIN_PMOD_PER_LEG[fmt_key] for t in trial): continue
            if (sum(t["p_mod"] for t in trial)/n_legs) < MIN_AVG_PMOD[fmt_key]: continue
            improved = trial
    if len(improved) == n_legs:
        return improved
    return picks[:n_legs]

def _select_base(cands: List[Dict[str, Any]], fmt: str, n_legs: int,
                 day_cat_bias: Counter | None = None) -> List[Dict[str, Any]]:
    lo, hi = RANGES[fmt]
    pool = [c for c in cands if _fits_range(c["odd"], lo, hi)]
    pool.sort(key=lambda x: (x["value"], x["p_mod"], -(SAFE_MARKETS_ORDER.index(x["market"]) if x["market"] in SAFE_MARKETS_ORDER else -99)), reverse=True)
    picks = _enforce_diversity(pool, n_legs, fmt, day_cat_bias=day_cat_bias)
    picks = _dedup_by_fixture(picks)
    picks = _diversify_league(picks, max_per_league=3)
    fmt_key = "single" if n_legs == 1 else fmt
    if picks and (sum(p["p_mod"] for p in picks)/len(picks) < MIN_AVG_PMOD[fmt_key]):
        return []
    return picks[:n_legs]

def _reselect_to_meet_total(cands: List[Dict[str, Any]], fmt: str, n_legs: int, min_total: float,
                            day_cat_bias: Counter | None = None) -> List[Dict[str, Any]]:
    gm_needed = pow(float(min_total), 1.0 / n_legs)
    cap_hi = UPPER_CAP.get(fmt, 1.45)
    hi_pool = [c for c in cands if (c["odd"] >= gm_needed and c["odd"] <= cap_hi and (c["value"] >= VALUE_TH[fmt] or c["p_mod"] >= SAFE_TH[fmt]))]
    hi_pool.sort(key=lambda x: (x["value"], x["p_mod"], x["odd"]), reverse=True)
    picks = _enforce_diversity(hi_pool, n_legs, fmt, day_cat_bias=day_cat_bias)
    fmt_key = "single" if n_legs == 1 else fmt
    if not picks or (sum(p["p_mod"] for p in picks)/len(picks) < MIN_AVG_PMOD[fmt_key]):
        return []
    return picks if _compute_total(picks) >= min_total else []

def _select_with_min_total(cands: List[Dict[str, Any]], fmt: str, n_legs: int,
                           day_cat_bias: Counter | None = None) -> List[Dict[str, Any]]:
    picks = _select_base(cands, fmt, n_legs, day_cat_bias=day_cat_bias)
    if not picks: return []
    need_min = MIN_TOTAL.get(fmt)
    if not need_min: return picks
    if _compute_total(picks) >= need_min: return picks
    boosted = _reselect_to_meet_total(cands, fmt, n_legs, need_min, day_cat_bias=day_cat_bias)
    return boosted if boosted else []

def _select_long_with_min_total(cands: List[Dict[str, Any]], max_legs: int,
                                day_cat_bias: Counter | None = None) -> List[Dict[str, Any]]:
    min_total = MIN_TOTAL["long"]
    for n in range(max_legs, 7, -1):
        picks = _select_with_min_total(cands, "long", n, day_cat_bias=day_cat_bias)
        if picks and _compute_total(picks) >= min_total:
            return picks
    return []

# -------------------------
# SCORING TICKET & PACK
# -------------------------
def _ticket_prob(legs: List[Dict[str, Any]]) -> float:
    p = 1.0
    for leg in legs: p *= float(leg["p_mod"])
    return round(p, 4)

def _ticket_var_score(legs: List[Dict[str, Any]]) -> float:
    cats = {leg["cat"] for leg in legs}
    return min(len(cats) / max(1, len(legs)), 1.0)  # 0..1

def _ticket_score(fmt: str, legs: List[Dict[str, Any]]) -> float:
    p = _ticket_prob(legs)
    tot = _compute_total(legs)
    target = TARGET_TOTAL.get(fmt, 1.0)
    quota_norm = min(tot / target, 1.0)
    var_score = _ticket_var_score(legs)
    return ALPHA * p + BETA * quota_norm + GAMMA * var_score

def _pack_score(tickets: List[Tuple[str, List[Dict[str, Any]]]]) -> float:
    # somma degli score + bonus “più schedine con alta P = più chance di fare almeno una cassa”
    base = sum(_ticket_score(fmt, legs) for fmt, legs in tickets)
    bonus = sum(_ticket_prob(legs) for _, legs in tickets) * 0.15
    return base + bonus

# -------------------------
# PACKAGING ADATTIVO (SCELTA MIGLIORE)
# -------------------------
def _make_ticket(fmt: str, legs: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]]]:
    return (fmt, legs)

def _choose_best_pack(cands: List[Dict[str, Any]], want_long_legs: int) -> Dict[str, List[Dict[str, Any]]]:
    """Genera più combinazioni sensate, le valuta, sceglie il pack con score più alto."""
    day_cat_bias = Counter()
    plans: List[Dict[str, List[Dict[str, Any]]]] = []

    # Helper per clonare cands e accumulare used fixtures
    def take_fmt(current_used: set, fmt: str, n: int, need_total: bool = False):
        pool = [c for c in cands if c["fixture_id"] not in current_used]
        if fmt == "long":
            pick = _select_long_with_min_total(pool, want_long_legs, day_cat_bias=day_cat_bias)
        elif need_total:
            pick = _select_with_min_total(pool, fmt, n, day_cat_bias=day_cat_bias)
        else:
            pick = _select_base(pool, fmt, n, day_cat_bias=day_cat_bias)
        if pick:
            current_used |= set(p["fixture_id"] for p in pick)
        return pick, current_used

    # opzioni candidate (costruiamo in ordine diverso, senza forzare)
    # A) quintupla (min 4x) + singola
    usedA = set()
    q5A, usedA = take_fmt(usedA, "quint", 5, need_total=True)
    if q5A:
        s1A, usedA = take_fmt(usedA, "single", 1, need_total=False)
        plans.append({"quintupla": q5A, "tripla": [], "doppia": [], "singole": s1A or [], "long": []})

    # B) tripla + doppia + singola
    usedB = set()
    t3B, usedB = take_fmt(usedB, "triple", 3)
    d2B, usedB = take_fmt(usedB, "double", 2)
    s1B, usedB = take_fmt(usedB, "single", 1)
    if t3B and d2B and s1B:
        plans.append({"quintupla": [], "tripla": t3B, "doppia": d2B, "singole": s1B, "long": []})

    # C) tripla + doppia
    usedC = set()
    t3C, usedC = take_fmt(usedC, "triple", 3)
    d2C, usedC = take_fmt(usedC, "double", 2)
    if t3C and d2C:
        plans.append({"quintupla": [], "tripla": t3C, "doppia": d2C, "singole": [], "long": []})

    # D) doppia + doppia + singola
    usedD = set()
    d2D1, usedD = take_fmt(usedD, "double", 2)
    d2D2, usedD = take_fmt(usedD, "double", 2)
    s1D, usedD = take_fmt(usedD, "single", 1)
    if d2D1 and d2D2 and s1D:
        plans.append({"quintupla": [], "tripla": [], "doppia": d2D1 + d2D2, "singole": s1D, "long": []})

    # E) due singole + doppia
    usedE = set()
    s1E1, usedE = take_fmt(usedE, "single", 1)
    s1E2, usedE = take_fmt(usedE, "single", 1)
    d2E,  usedE = take_fmt(usedE, "double", 2)
    if s1E1 and s1E2 and d2E:
        plans.append({"quintupla": [], "tripla": [], "doppia": d2E, "singole": s1E1 + s1E2, "long": []})

    # F) super combo (8..N, min 6x) da sola
    usedF = set()
    longF, usedF = take_fmt(usedF, "long", want_long_legs, need_total=True)
    if longF:
        plans.append({"quintupla": [], "tripla": [], "doppia": [], "singole": [], "long": longF})

    # G) fallback minimi (tripla oppure doppia oppure singole)
    usedG = set()
    t3G, usedG = take_fmt(usedG, "triple", 3)
    if t3G:
        plans.append({"quintupla": [], "tripla": t3G, "doppia": [], "singole": [], "long": []})
    usedH = set()
    d2H, usedH = take_fmt(usedH, "double", 2)
    if d2H:
        plans.append({"quintupla": [], "tripla": [], "doppia": d2H, "singole": [], "long": []})
    usedI = set()
    s1I, usedI = take_fmt(usedI, "single", 1)
    if s1I:
        plans.append({"quintupla": [], "tripla": [], "doppia": [], "singole": s1I, "long": []})

    if not plans:
        return {"singole": [], "doppia": [], "tripla": [], "quintupla": [], "long": []}

    # valuta ogni plan
    best = None; best_score = -1.0
    for pl in plans:
        tickets: List[Tuple[str, List[Dict[str, Any]]]] = []
        if pl["quintupla"]: tickets.append(("quint", pl["quintupla"]))
        if pl["tripla"]:    tickets.append(("triple", pl["tripla"]))
        if pl["doppia"]:    tickets.append(("double", pl["doppia"]))
        if pl["singole"]:
            # ogni singola è un ticket
            for s in pl["singole"]:
                tickets.append(("single", [s]))
        if pl["long"]:      tickets.append(("long", pl["long"]))
        score = _pack_score(tickets)
        if score > best_score:
            best_score = score; best = pl
    return best or {"singole": [], "doppia": [], "tripla": [], "quintupla": [], "long": []}

# -------------------------
# Planner (usa la scelta migliore)
# -------------------------
def plan_day(api, cfg, date_str: str, want_long_legs: int = 10) -> Dict[str, List[Dict[str, Any]]]:
    cands = build_daily_candidates(api, cfg, date_str)
    best = _choose_best_pack(cands, want_long_legs)
    return best

# -------------------------
# Rendering
# -------------------------
def render_plan_blocks(api, cfg, plan: Dict[str, List[Dict[str, Any]]]) -> List[str]:
    tz_str = getattr(cfg, "TZ", "Europe/Rome")
    blocks: List[str] = []
    singles = plan["singole"]
    if singles:
        for idx, s in enumerate(singles, start=1):
            blocks.append(_format_block(f"🔎 <b>SINGOLA {idx}</b>", [s], tz_str))
    if plan["doppia"]:
        blocks.append(_format_block("🧩 <b>DOPPIA</b>", plan["doppia"], tz_str))
    if plan["tripla"]:
        blocks.append(_format_block("🎻 <b>TRIPLA</b>", plan["tripla"], tz_str))
    if plan["quintupla"]:
        blocks.append(_format_block("🎬 <b>QUINTUPLA</b>", plan["quintupla"], tz_str))
    if plan["long"]:
        title = f"💎 <b>SUPER COMBO x{len(plan['long'])}</b>"
        blocks.append(_format_block(title, plan["long"], tz_str))
    return blocks
