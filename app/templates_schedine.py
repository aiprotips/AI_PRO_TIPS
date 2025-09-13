# app/templates_schedine.py
from __future__ import annotations
from typing import List, Dict, Any
from zoneinfo import ZoneInfo
from datetime import datetime
import random

# ------------------------------
# EMOJI BASE
# ------------------------------
_EMOJI = ["🔥","⚡","🚀","🎯","🏆","💎","🎉","💪","📈","🧩"]

def _e() -> str:
    return random.choice(_EMOJI)

# ------------------------------
# SINGOLA (value scanner)
# ------------------------------
def render_value_single(home: str, away: str, pick: str, odd: float, kickoff_local: str, link: str) -> str:
    outro_pool = [
        "Andiamo a prendercela.",
        "Linea pulita, si va.",
        "Semplice e solida: dentro.",
        "Niente fronzoli: questa è da fare."
    ]
    outro = random.choice(outro_pool)
    return (
        "🔎 <b>VALUE SCANNER</b>\n\n"
        f"{home} 🆚 {away}\n"
        f"🎯 {pick}\n\n"
        f"💰 <b>{odd:.2f}</b>\n"
        f"🕒 Calcio d’inizio: {kickoff_local}\n\n"
        f"{_e()} {outro}\n"
        f"👉 {link}"
    )

# ------------------------------
# MULTIPLA (doppia/tripla/quintupla/super combo)
# ------------------------------
def render_multipla(title: str, selections: List[Dict[str, Any]], total_odds: float, kickoff_local: str, link: str) -> str:
    body = "\n".join(
        f"• {s['home']} 🆚 {s['away']}\n   🎯 {s['pick']} — <b>{float(s['odd']):.2f}</b>"
        for s in selections
    )
    outro_pool = [
        "Una a una fino alla cassa.",
        "Costruiamo valore, non fortuna.",
        "Ordine, criterio e sangue freddo.",
        "Combo bilanciata, andiamo."
    ]
    outro = random.choice(outro_pool)
    return (
        f"{title}\n\n"
        f"{body}\n\n"
        f"💰 Quota totale: <b>{total_odds:.2f}</b>\n"
        f"🕒 Primo calcio d’inizio: {kickoff_local}\n\n"
        f"{_e()} {outro}\n"
        f"👉 {link}"
    )

# ------------------------------
# LIVE ALERT
# ------------------------------
def render_live_alert(fav: str, other: str, minute: int, preodd: str, odds_str: str, link: str) -> str:
    outro_pool = [
        "Situazione perfetta per rientrare.",
        "Momento ideale per colpire.",
        "Ribaltone in vista: opportunità.",
        "Timing giusto, pressione on."
    ]
    outro = random.choice(outro_pool)
    return (
        "⚡ <b>LIVE ALERT</b>\n\n"
        f"⏱️ {minute}' — la favorita <b>{fav}</b> è sotto contro {other}.\n"
        f"Quota pre: {preodd} | Quota live: {odds_str}\n\n"
        f"{_e()} {outro}\n"
        f"👉 {link}"
    )

# ------------------------------
# LIVE ENERGY
# ------------------------------
def render_live_energy(home: str, away: str, minute: int, line: str, sid: str) -> str:
    return f"⏱️ {minute}' — {home}–{away}: {line}  (#{sid})"

# ------------------------------
# CELEBRAZIONI (cassa)
# ------------------------------
def render_celebration_singola(home: str, away: str, score: str, pick: str, odds: float, link: str) -> str:
    titles = ["CASSA!", "Dentro! 🎯", "Boom! 💥", "Che colpo! 🏆", "Pulita e in tasca! 💎"]
    title = random.choice(titles)
    return (
        f"{_e()} <b>{title}</b> {_e()}\n\n"
        f"{home} 🆚 {away}\n"
        f"Risultato: <b>{score}</b>\n"
        f"Pick: {pick} ✅ @ <b>{odds:.2f}</b>\n\n"
        f"👉 {link}"
    )

def render_celebration_multipla(selections: list, total_odds: float, link: str) -> str:
    titles = ["CASSA!", "Dentro! 🎯", "Boom! 💥", "Che colpo! 🏆", "Pulita e in tasca! 💎"]
    title = random.choice(titles)
    lines = [f"• {s['home']} 🆚 {s['away']}\n   Risultato: <b>{s.get('score','')}</b>\n   Pick: {s['pick']} ✅" for s in selections]
    body = "\n".join(lines)
    return (
        f"{_e()} <b>{title}</b> {_e()}\n\n"
        f"{body}\n\n"
        f"Quota totale: <b>{total_odds:.2f}</b>\n\n"
        f"👉 {link}"
    )

# ------------------------------
# QUASI VINCENTE
# ------------------------------
def render_quasi_vincente(missed_leg: str) -> str:
    titles = ["PER UN SOFFIO", "QUASI LEGGENDA", "SFUMATA SUL PIÙ BELLO", "CI È MANCATO UN NULLA"]
    motivs = [
        "Non preoccupatevi, la prossima volta sarà nostra. 💪🔥",
        "Stessa fame, testa fredda, si riparte subito. 🚀",
        "La linea è giusta: continuità e arriva la cassa. 🎯",
        "Zero drammi: rifocalizziamoci e andiamo. ⚡"
    ]
    return (
        f"💔 <b>{random.choice(titles)}</b>\n\n"
        f"Saltata per 1: {missed_leg}\n\n"
        f"{random.choice(motivs)}"
    )

# ------------------------------
# CUORI SPEZZATI
# ------------------------------
def render_cuori_spezzati() -> str:
    lines = [
        "Scivolata a tempo scaduto: testa alta, ripartiamo. 🚀",
        "Giornata storta: archiviamo e torniamo a far male. 💪",
        "Succede: reset e si torna sul pezzo. ⚙️",
        "Non cambia la rotta: disciplina e avanti. 🎯"
    ]
    return f"💔 <b>CUORI SPEZZATI</b>\n\n{random.choice(lines)}"

# ------------------------------
# STORYTELLING
# ------------------------------
def render_story_long(home: str, away: str) -> str:
    titles = ["Il colpo facile", "Partita di sostanza", "Dettagli che fanno la differenza", "Qui si vince col ritmo"]
    bodies = [
        "Non è solo una sensazione: i numeri parlano chiaro, l’inerzia è dalla nostra. 🔥",
        "La narrativa dice equilibrio, i dati raccontano un’altra storia: intensità, continuità e struttura. 🚀",
        "Quando forma e trend si allineano, la value non è un’opinione. 🎯"
    ]
    return f"⚔️ <b>{random.choice(titles)}</b>\n\n{home}–{away}: {random.choice(bodies)}"

# ------------------------------
# BANTER
# ------------------------------
def render_banter() -> str:
    pool = [
        "La value oggi è tutta dalla nostra parte. 🚀",
        "Noi lavoriamo, gli altri sperano. 😉",
        "Poche parole, tanti ticket. 💎",
        "Linee pulite, mani ferme. Andiamo. ⚡"
    ]
    return random.choice(pool)

# ------------------------------
# REPORT (08:00, DM admin)
# ------------------------------
def render_report(admin_tz: str, rows: List[Dict[str, Any]], watchlist_rows: List[Dict[str, Any]]) -> str:
    parts = ["<b>📋 Report 08:00</b>\n"]

    if rows:
        parts.append("<b>Schedine pianificate</b>")
        for r in rows:
            when_local = r.get("send_at_local") or "n/d"
            preview = r.get("preview") or ""
            parts.append(
                f"ID <b>{r['short_id']}</b> — {r['kind']} — invio: <b>{when_local}</b>\n{preview}"
            )
    else:
        parts.append("Nessuna schedina pianificata oggi.")

    if watchlist_rows:
        parts.append("\n<b>Favorite monitorate (≤1.26, primi 20')</b>")
        for w in watchlist_rows:
            league = w.get("league","")
            fav    = w.get("fav","")
            other  = w.get("other","")
            pre    = w.get("pre", 0.0)
            try:
                pre_s = f"{float(pre):.2f}"
            except Exception:
                pre_s = str(pre)
            parts.append(f"• {league} — {fav} vs {other} (pre {pre_s})")
    else:
        parts.append("\nNessuna favorita da monitorare.")

    return "\n\n——————————\n\n".join(parts)
