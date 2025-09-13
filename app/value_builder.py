# app/value_builder.py
from __future__ import annotations
from typing import Dict, Any, List, Tuple
from math import isfinite
from .stats_engine import StatsEngine, clamp

# Range quote per formato (prima passata "soft")
RANGES = {
    "single":  (1.45, 1.65),
    "double":  (1.28, 1.42),
    "triple":  (1.22, 1.35),
    "quint":   (1.18, 1.30),
    "long":    (1.10, 1.22),  # 8–10–12 eventi
}

# Soglie 'value' (delta minimo vs p_imp)
VALUE_TH = {
    "single": 0.06,
    "double": 0.04,
    "triple": 0.03,
    "quint":  0.02,
    "long":   0.01,
}

# Soglie fallback 'sicurezza' se non c'è value
SAFE_TH = {
    "single": 0.75,
    "double": 0.70,
    "triple": 0.65,
    "quint":  0.60,
    "long":   0.55,
}

# Ordine di "sicurezza" per fallback
SAFE_MARKETS_ORDER = (
    "Over 1.5", "Under 3.5", "1X", "X2", "No Gol", "Over 0.5",
    "Under 2.5", "Gol", "1", "2"
)

# >>> NUOVO: minimi di quota TOTALE richiesti
MIN_TOTAL = {
    "quint": 4.00,  # quintupla
    "long":  6.00,  # super combo 8–12
}

# >>> NUOVO: cap massimo per quote per-leg nel "secondo pass" (quando serve alzare)
UPPER_CAP = {
    "single": 1.70,
    "double": 1.50,
    "triple": 1.45,
    "quint":  1.45,  # alziamo per raggiungere 4x su 5 leg
    "long":   1.30,  # consente 8 leg a GM ~1.25 quando serve arrivare a 6x
}

def _p_imp(odd: float) -> float:
    try:
        if odd and odd > 1.001:
            return clamp(1.0 / float(odd), 0.01, 0.99)
    except Exception:
        pass
    return 0.0

def _avg(a: float, b: float) -> float:
    return (a + b) / 2.0

def _strength_gap(markets: Dict[str, float]) -> float:
    """Gap di forza stimato da 1 e 2 implicite."""
    p1 = _p_imp(markets.get("1", 0.0))
    p2 = _p_imp(markets.get("2", 0.0))
    return abs(p1 - p2)

def _fav_side(markets: Dict[str, float]) -> str:
    p1 = _p_imp(markets.get("1", 0.0))
    p2 = _p_imp(markets.get("2", 0.0))
    return "home" if p1 >= p2 else "away"

def _adj_market(market: str, markets: Dict[str, float], feats: Dict[str, Any]) -> float:
    """
    Aggiustamento (+/-) da sommare alla probabilità implicita p_imp del mercato.
    Bounded in [-0.12, +0.12] per non strappare dai prezzi bookmaker.
    """
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
    else:
        adj = 0.0

    return clamp(adj, -0.12, 0.12)

def _mk_candidate(entry: Dict[str, Any], market: str, feats: Dict[str, Any]) -> Dict[str, Any]:
    mk = entry["markets"]
    if market not in mk:
        return {}
    odd = float(mk[market])
    p_imp = _p_imp(odd)
    if p_imp <= 0.0:
        return {}

    adj = _adj_market(market, mk, feats)
    p_mod = clamp(p_imp + adj, 0.01, 0.99)
    value = p_mod - p_imp

    return {
        "fixture_id": entry["fixture_id"],
        "league": f"{entry['league_country']} — {entry['league_name']}",
        "home": entry["home"],
        "away": entry["away"],
        "kickoff_iso": entry["kickoff_iso"],
        "market": market,
        "odd": odd,
        "p_imp": round(p_imp, 4),
        "p_mod": round(p_mod, 4),
        "value": round(value, 4)
    }

def _fits_range(odd: float, lo: float, hi: float) -> bool:
    try:
        x = float(odd)
        return lo <= x <= hi
    except Exception:
        return False

def build_daily_candidates(api, cfg, date_str: str) -> List[Dict[str, Any]]:
    """
    Restituisce una lista di candidati (uno per mercato) con p_mod e value.
    Usa solo le leghe whitelisted (se presente .leagues.allowed_league).
    """
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
            if cand:
                out.append(cand)

    return out

def _dedup_by_fixture(picks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set(); out = []
    for p in picks:
        fid = int(p["fixture_id"])
        if fid in seen:
            continue
        seen.add(fid); out.append(p)
    return out

def _diversify_league(picks: List[Dict[str, Any]], max_per_league: int = 3) -> List[Dict[str, Any]]:
    cnt: Dict[str, int] = {}
    out: List[Dict[str, Any]] = []
    for p in picks:
        lg = p["league"]
        if cnt.get(lg, 0) >= max_per_league:
            continue
        cnt[lg] = cnt.get(lg, 0) + 1
        out.append(p)
    return out

def _compute_total(legs: List[Dict[str, Any]]) -> float:
    tot = 1.0
    for p in legs:
        try:
            tot *= float(p["odd"])
        except Exception:
            pass
    return round(tot, 2)

def _format_block(label: str, legs: List[Dict[str, Any]], tz_str: str) -> str:
    if not legs:
        return f"<b>{label}</b>\nN/D"
    lines = [f"<b>{label}</b>"]
    for p in legs:
        lines.append(f"• {p['home']} 🆚 {p['away']} — {p['market']} <b>{p['odd']:.2f}</b>")
    if len(legs) > 1:
        lines.append(f"Totale: <b>{_compute_total(legs):.2f}</b>")
    # kickoff più vicino
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

def _select_base(cands: List[Dict[str, Any]], fmt: str, n_legs: int) -> List[Dict[str, Any]]:
    lo, hi = RANGES[fmt]
    pool = [c for c in cands if _fits_range(c["odd"], lo, hi)]
    # 1) Value prima
    value_cands = [c for c in pool if c["value"] >= VALUE_TH[fmt]]
    value_cands.sort(key=lambda x: (x["value"], x["p_mod"]), reverse=True)
    picks = value_cands[: n_legs * 2]

    # 2) Fallback sicurezza
    if len(picks) < n_legs:
        safe = [c for c in pool if c["p_mod"] >= SAFE_TH[fmt]]
        safe.sort(key=lambda x: (SAFE_MARKETS_ORDER.index(x["market"]) if x["market"] in SAFE_MARKETS_ORDER else 99, -x["p_mod"]))
        for s in safe:
            if s not in picks:
                picks.append(s)
            if len(picks) >= n_legs * 2:
                break

    # 3) Dedup & diversificazione
    picks = _dedup_by_fixture(picks)
    picks = _diversify_league(picks, max_per_league=3)
    return picks[:n_legs]

def _reselect_to_meet_total(cands: List[Dict[str, Any]], fmt: str, n_legs: int, min_total: float) -> List[Dict[str, Any]]:
    """
    Secondo pass: alza l'asticella delle quote per-leg (senza impazzire),
    puntando a raggiungere la soglia di quota totale richiesta.
    """
    if n_legs <= 0:
        return []

    # Geometric mean richiesta
    from math import pow
    gm_needed = pow(float(min_total), 1.0 / n_legs)
    cap_hi = UPPER_CAP.get(fmt, 1.45)

    # costruiamo una pool "hi" coerente col formato
    hi_pool = [c for c in cands if (c["odd"] >= gm_needed and c["odd"] <= cap_hi and (c["value"] >= VALUE_TH[fmt] or c["p_mod"] >= SAFE_TH[fmt]))]

    # ordina prima per 'value', poi p_mod, poi odd (più alta)
    hi_pool.sort(key=lambda x: (x["value"], x["p_mod"], x["odd"]), reverse=True)

    # Dedup e diversificazione mentre selezioniamo
    picks: List[Dict[str, Any]] = []
    seen_fixtures = set()
    league_cnt: Dict[str, int] = {}
    for c in hi_pool:
        if len(picks) >= n_legs:
            break
        if c["fixture_id"] in seen_fixtures:
            continue
        lg = c["league"]
        if league_cnt.get(lg, 0) >= 3:
            continue
        seen_fixtures.add(c["fixture_id"])
        league_cnt[lg] = league_cnt.get(lg, 0) + 1
        picks.append(c)

    # verifica totale
    if len(picks) == n_legs and _compute_total(picks) >= min_total:
        return picks

    # Se ancora non basta, tenta greedy per alzare il totale (quote più alte)
    # prendendo la migliore combinazione possibile dal pool.
    # (approccio semplice: prova a sostituire elementi con altri a odd più alti)
    improved = picks[:]
    for i in range(len(improved)):
        for cand in hi_pool:
            if cand in improved:
                continue
            if cand["fixture_id"] in {p["fixture_id"] for p in improved}:
                continue
            trial = improved[:]
            trial[i] = cand
            # check league cap
            from collections import Counter
            lc = Counter([t["league"] for t in trial])
            if any(v > 3 for v in lc.values()):
                continue
            if _compute_total(trial) > _compute_total(improved):
                improved = trial
    if len(improved) == n_legs and _compute_total(improved) >= min_total:
        return improved

    return []

def _select_for_format(cands: List[Dict[str, Any]], fmt: str, n_legs: int) -> List[Dict[str, Any]]:
    """Selezione base (value → safe) + vincoli di coerenza; NO soglia totale."""
    return _select_base(cands, fmt, n_legs)

def _select_with_min_total(cands: List[Dict[str, Any]], fmt: str, n_legs: int) -> List[Dict[str, Any]]:
    """
    Come _select_for_format, ma se esiste MIN_TOTAL[fmt] tenta un secondo pass per raggiungere la soglia.
    Se non raggiungibile con materiale buono → restituisce [] (salta il formato).
    """
    picks = _select_for_format(cands, fmt, n_legs)
    if not picks:
        return []
    need_min = MIN_TOTAL.get(fmt)
    if not need_min:
        return picks
    if _compute_total(picks) >= need_min:
        return picks
    # secondo pass "hi-odds" controllato
    boosted = _reselect_to_meet_total(cands, fmt, n_legs, need_min)
    if boosted and _compute_total(boosted) >= need_min:
        return boosted
    # non raggiungibile senza snaturare → salta
    return []

def _select_long_with_min_total(cands: List[Dict[str, Any]], max_legs: int) -> List[Dict[str, Any]]:
    """
    Prova a costruire una super combo con quota totale >= MIN_TOTAL['long'].
    Tenta prima con il numero massimo di leg, poi scende fino a 8 (se necessario).
    Se non raggiungibile → ritorna [] (niente super combo oggi).
    """
    min_total = MIN_TOTAL["long"]
    # prova dal massimo (più facile arrivare a min_total) verso 8
    for n in range(max_legs, 7, -1):
        picks = _select_with_min_total(cands, "long", n)
        if picks and _compute_total(picks) >= min_total:
            return picks
    return []

def plan_day(api, cfg, date_str: str, want_long_legs: int = 10) -> Dict[str, List[Dict[str, Any]]]:
    """
    Ritorna un piano con blocchi:
    - singole: 2
    - doppia: 2 legs
    - tripla: 3 legs
    - quintupla: 5 legs (totale >= 4.0)
    - long: 8–want_long_legs legs (totale >= 6.0), se possibile
    """
    cands = build_daily_candidates(api, cfg, date_str)

    # due singole
    s1 = _select_for_format(cands, "single", 1)
    used = set(p["fixture_id"] for p in s1)
    c2 = [c for c in cands if c["fixture_id"] not in used]
    s2 = _select_for_format(c2, "single", 1)

    # doppia
    used |= set(p["fixture_id"] for p in s2)
    c3 = [c for c in cands if c["fixture_id"] not in used]
    d2 = _select_for_format(c3, "double", 2)

    # tripla
    used |= set(p["fixture_id"] for p in d2)
    c4 = [c for c in cands if c["fixture_id"] not in used]
    t3 = _select_for_format(c4, "triple", 3)

    # quintupla (con minimo totale 4x)
    used |= set(p["fixture_id"] for p in t3)
    c5 = [c for c in cands if c["fixture_id"] not in used]
    q5 = _select_with_min_total(c5, "quint", 5)  # se non raggiunge 4x -> []

    # super combo (8–N) con minimo 6x
    used |= set(p["fixture_id"] for p in (q5 or []))
    c6 = [c for c in cands if c["fixture_id"] not in used]
    long = _select_long_with_min_total(c6, want_long_legs)  # se non raggiunge 6x -> []

    return {
        "singole": s1 + s2,     # 0..2 items
        "doppia": d2,           # 0..2 legs
        "tripla": t3,           # 0..3 legs
        "quintupla": q5,        # [] se non raggiunge x4
        "long": long            # [] se non raggiunge x6
    }

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
