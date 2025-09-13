# app/value_builder.py
from __future__ import annotations
from typing import Dict, Any, List, Tuple
from math import isfinite
from .stats_engine import StatsEngine, clamp

# Range quote per formato
RANGES = {
    "single":  (1.45, 1.65),
    "double":  (1.28, 1.42),
    "triple":  (1.22, 1.35),
    "quint":   (1.18, 1.30),
    "long":    (1.10, 1.22),  # 8–10 eventi
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

SAFE_MARKETS_ORDER = (
    "Over 1.5", "Under 3.5", "1X", "X2", "No Gol", "Over 0.5",
    "Under 2.5", "Gol", "1", "2"
)

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
    Bounded in [-0.12, +0.12] per non 'strappare' dai prezzi bookmaker.
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
        adj = base if fav == "home" else base*0.5  # se non è favorita, meno boost
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
    Usa solo le leghe whitelisted: cfg.ALLOWED (label_league) se presente,
    altrimenti presuppone che entries_by_date_bet365 sia già filtrata a monte.
    """
    # entries già pronte da api_football (quote reali/paginate/FT only)
    entries = api.entries_by_date_bet365(date_str)
    # opzionale: se hai un modulo leagues con filtro, usalo qui
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
            # se stats down, salta la partita (meglio pochi ma buoni)
            continue

        # Genera candidati per TUTTI i mercati che l’entry espone
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

def _format_block(label: str, legs: List[Dict[str, Any]]) -> str:
    if not legs:
        return f"<b>{label}</b>\nN/D"
    lines = [f"<b>{label}</b>"]
    for p in legs:
        lines.append(f"• {p['home']} 🆚 {p['away']} — {p['market']} <b>{p['odd']:.2f}</b>")
    # quota totale se >1 leg
    if len(legs) > 1:
        tot = 1.0
        for p in legs: tot *= float(p["odd"])
        lines.append(f"Totale: <b>{tot:.2f}</b>")
    # kick-off più vicino
    try:
        from dateutil import parser as duparser
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(getattr(cfg, "TZ", "Europe/Rome"))
        first = min(legs, key=lambda x: x["kickoff_iso"])
        dt = duparser.isoparse(first["kickoff_iso"]).astimezone(tz)
        lines.append(f"🕒 {dt.strftime('%H:%M')}")
    except Exception:
        pass
    return "\n".join(lines)

def _select_for_format(cands: List[Dict[str, Any]], fmt: str, n_legs: int) -> List[Dict[str, Any]]:
    lo, hi = RANGES[fmt]
    # 1) value prima
    value_cands = [c for c in cands if _fits_range(c["odd"], lo, hi)]
    value_cands.sort(key=lambda x: (x["value"], x["p_mod"]), reverse=True)
    picks = [c for c in value_cands if c["value"] >= VALUE_TH[fmt]][: n_legs * 2]  # shortlist
    # 2) fallback: sicurezza
    if len(picks) < n_legs:
        safe = [c for c in value_cands if c["p_mod"] >= SAFE_TH[fmt]]
        # ordina per mercato 'più safe' prima
        safe.sort(key=lambda x: (SAFE_MARKETS_ORDER.index(x["market"]) if x["market"] in SAFE_MARKETS_ORDER else 99, -x["p_mod"]))
        for s in safe:
            if s not in picks:
                picks.append(s)
            if len(picks) >= n_legs * 2:
                break
    # 3) dedup per fixture e diversificazione lega
    picks = _dedup_by_fixture(picks)
    picks = _diversify_league(picks, max_per_league=3)
    return picks[:n_legs]

def plan_day(api, cfg, date_str: str, want_long_legs: int = 10) -> Dict[str, List[Dict[str, Any]]]:
    """
    Ritorna un piano con blocchi:
    - singole: 2
    - doppia: 2 legs
    - tripla: 3 legs
    - quintupla: 5 legs
    - long: 8–want_long_legs legs (se materiale)
    """
    cands = build_daily_candidates(api, cfg, date_str)
    # due singole
    s1 = _select_for_format(cands, "single", 1)
    # rimuovi fixture usate per non duplicare
    used = set(p["fixture_id"] for p in s1)
    c2 = [c for c in cands if c["fixture_id"] not in used]
    s2 = _select_for_format(c2, "single", 1)

    used |= set(p["fixture_id"] for p in s2)
    c3 = [c for c in cands if c["fixture_id"] not in used]
    d2 = _select_for_format(c3, "double", 2)

    used |= set(p["fixture_id"] for p in d2)
    c4 = [c for c in cands if c["fixture_id"] not in used]
    t3 = _select_for_format(c4, "triple", 3)

    used |= set(p["fixture_id"] for p in t3)
    c5 = [c for c in cands if c["fixture_id"] not in used]
    q5 = _select_for_format(c5, "quint", 5)

    # long 8–N
    used |= set(p["fixture_id"] for p in q5)
    c6 = [c for c in cands if c["fixture_id"] not in used]
    long = _select_for_format(c6, "long", want_long_legs)
    if len(long) < 8:
        long = long[:0]  # se non c'è materiale, non forziamo

    return {
        "singole": s1 + s2,     # 0..2 items (ognuna 1 leg)
        "doppia": d2,           # 0..2 legs
        "tripla": t3,           # 0..3 legs
        "quintupla": q5,        # 0..5 legs
        "long": long            # 0..8..N legs
    }

def render_plan_blocks(api, cfg, plan: Dict[str, List[Dict[str, Any]]]) -> List[str]:
    blocks: List[str] = []
    singles = plan["singole"]
    if singles:
        for idx, s in enumerate(singles, start=1):
            blocks.append(_format_block(f"🔎 <b>SINGOLA {idx}</b>", [s]))
    if plan["doppia"]:
        blocks.append(_format_block("🧩 <b>DOPPIA</b>", plan["doppia"]))
    if plan["tripla"]:
        blocks.append(_format_block("🎻 <b>TRIPLA</b>", plan["tripla"]))
    if plan["quintupla"]:
        blocks.append(_format_block("🎬 <b>QUINTUPLA</b>", plan["quintupla"]))
    if plan["long"]:
        title = f"💎 <b>SUPER COMBO x{len(plan['long'])}</b>"
        blocks.append(_format_block(title, plan["long"]))
    return blocks
