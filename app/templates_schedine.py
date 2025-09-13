# app/templates_schedine.p
from datetime import datetime
from zoneinfo import ZoneInfo

EMOJI_FIRE = ["🔥","⚡","🚀","💥","🏆","💎","🎯","✅","🎉","🥇"]

def _fmt_local(hhmm: datetime, tz: str) -> str:
    return hhmm.astimezone(ZoneInfo(tz)).strftime("%H:%M")

def render_value_single(home, away, pick, odd, kickoff_local, link: str) -> str:
    return (
        "🔎 <b>VALUE SCANNER</b>\n\n"
        f"{home} 🆚 {away}\n"
        f"🎯 {pick}\n\n"
        f"💰 <b>{odd:.2f}</b>\n"
        f"🕒 Calcio d’inizio: {kickoff_local}\n\n"
        f"{EMOJI_FIRE[odd.__hash__()%len(EMOJI_FIRE)]} Andiamo a prendercela.\n"
        f"👉 {link}"
    )

def render_multipla(title: str, selections: list, total_odds: float, kickoff_local: str, link: str) -> str:
    body = "\n".join([f"• {s['home']} 🆚 {s['away']}\n   🎯 {s['pick']} — <b>{s['odd']:.2f}</b>" for s in selections])
    return (
        f"{title}\n\n"
        f"{body}\n\n"
        f"💰 Quota totale: <b>{total_odds:.2f}</b>\n"
        f"🕒 Primo calcio d’inizio: {kickoff_local}\n\n"
        "⚡ In pista.\n"
        f"👉 {link}"
    )

def render_report(admin_tz: str, rows: list, watchlist_rows: list) -> str:
    parts = ["<b>📋 Report 08:00</b>\n"]
    if rows:
        parts.append("<b>Schedine pianificate</b>")
        for r in rows:
            when_local = r['send_at_local']
            parts.append(
                f"ID <b>{r['short_id']}</b> — {r['kind']} — invio: <b>{when_local}</b>\n{r['preview']}"
            )
    else:
        parts.append("Nessuna schedina pianificata oggi.")

    if watchlist_rows:
        parts.append("\n<b>Favorite monitorate (≤1.26, primi 20')</b>")
        for w in watchlist_rows:
            parts.append(f"• {w['league']} — {w['fav']} vs {w['other']} (pre {w['pre']:.2f})")
    else:
        parts.append("\nNessuna favorita da monitorare.")

    return "\n\n——————————\n\n".join(parts)
