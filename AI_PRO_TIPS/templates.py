import json, os, random

DEFAULTS = {
    "banter": [
        "Quote più basse della linea difensiva al 90’. 😏",
        "Multipla più sexy di un gol al 94’.",
        "Oggi la VAR la facciamo noi: verifichiamo solo casse. ✅",
        "Questa quota è più pulita di un contropiede al 92’.",
    ],
    "story_titles": [
        "Il leone contro la preda",
        "Sfida d’acciaio al tramonto",
        "Notte di casse (o quasi)",
        "Calma piatta prima del gol",
    ],
    "celebrations": [
        "CASSA!", "IN CASSA!", "LO SHOW CONTINUA!", "VOLANO I TICKET!"
    ],
    "heartbreak": [
        "Abbiamo preso più gol noi di un portiere bendato. 💔",
        "Il calcio è crudele, ma noi domani di più. 😤",
        "A un passo dalla gloria… inciampati sul traguardo. 💔",
    ]
}

def load_custom():
    path = os.path.join("AI_PRO_TIPS", "data", "templates_custom.json")
    if os.path.exists(path):
        try:
            import json
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

CUSTOM = load_custom()

def choice(group: str):
    arr = CUSTOM.get(group) or DEFAULTS.get(group, [])
    return random.choice(arr) if arr else ""

def render_banter_line() -> str:
    return choice("banter")

def render_stat_flash(stat_text: str) -> str:
    return f"📊 <b>Statistica lampo</b>\n{stat_text}"

def render_progress_bar(taken: int, total: int) -> str:
    bar = "✅" * taken + "⬜" * (total - taken)
    return f"Avanzamento schedina: {bar} ({taken}/{total})"

def render_quasi_vincente(code: str, missed_leg: str) -> str:
    return f"💔 <b>A un passo dalla leggenda</b> (#{code})\nSaltata per: {missed_leg}"

def render_cuori_spezzati(code: str) -> str:
    return f"💔 <b>Cuori Spezzati</b> (#{code})\n{choice('heartbreak')}"

def render_story_headline(title: str, body: str) -> str:
    return f"⚔️ <b>{title}</b>\n{body}"

def render_value_scanner(match_str: str, market: str, odds: float, note: str) -> str:
    return f"🔎 <b>Value Scanner</b>\n{match_str}\n{market} @ {odds:.2f}\n{note}"

def render_live_alert(txt: str) -> str:
    return f"⚠️ <b>LIVE ALERT</b>\n{txt}"

def render_celebration(code: str, total_odds: float) -> str:
    shout = choice("celebrations")
    return f"🎉 <b>{shout}</b> (#{code}) @ {total_odds:.2f}\nAI Pro Tips non dorme mai. 🔥"
