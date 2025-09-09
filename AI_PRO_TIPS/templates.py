import os, json, random, time

# Carica da AI_PRO_TIPS/data/templates.json, con fallback se non esiste.
_TPL_PATH = os.path.join(os.path.dirname(__file__), "data", "templates.json")
_cache = {"ts": 0, "data": {}}

FALLBACK = {
    "banter": [
        "Quote più basse della linea difensiva al 90’. 😏",
        "Multipla più sexy di un gol al 94’.",
        "Oggi la VAR la facciamo noi: verifichiamo solo casse. ✅",
        "Questa quota è più pulita di un contropiede al 92’.",
    ],
    "celebrations": ["CASSA!", "IN CASSA!", "LO SHOW CONTINUA!", "VOLANO I TICKET!"],
    "almost_win": ["A un passo dalla leggenda… oggi manca solo un dettaglio. 💔"],
    "heartbreak": [
        "Abbiamo preso più gol noi di un portiere bendato. 💔",
        "Il calcio è crudele, ma noi domani di più. 😤",
        "A un passo dalla gloria… inciampati sul traguardo. 💔",
    ],
    "story_titles": ["Il leone contro la preda","Sfida d’acciaio al tramonto","Notte di casse (o quasi)","Calma piatta prima del gol"],
    "stat_flash_phrases": [
        "Negli ultimi 8, {HOME} ha segnato in 6 partite. {HOME}–{AWAY} oggi può sbloccarsi presto.",
        "{HOME} imbattuta in 7/9: oggi {HOME}–{AWAY} promette solidità.",
        "{AWAY} concede spesso nel primo tempo: occhio all’avvio in {HOME}–{AWAY}."
    ]
}

def _load():
    try:
        ts = os.path.getmtime(_TPL_PATH)
        if ts != _cache["ts"]:
            with open(_TPL_PATH, "r", encoding="utf-8") as f:
                _cache["data"] = json.load(f)
            _cache["ts"] = ts
    except Exception:
        _cache["data"] = FALLBACK
        _cache["ts"] = time.time()

def _choice(key: str) -> str:
    _load()
    arr = _cache["data"].get(key) or FALLBACK.get(key, [])
    return random.choice(arr) if arr else ""

# ---- Render helpers ----
def render_banter_line() -> str:
    return _choice("banter")

def render_stat_flash_phrase(home: str, away: str) -> str:
    _load()
    arr = _cache["data"].get("stat_flash_phrases") or FALLBACK["stat_flash_phrases"]
    phrase = random.choice(arr)
    return f"📊 <b>Statistica lampo</b>\n{phrase.replace('{HOME}', home).replace('{AWAY}', away)}"

def render_progress_bar(taken: int, total: int) -> str:
    bar = "✅" * taken + "⬜" * (total - taken)
    return f"Avanzamento schedina: {bar} ({taken}/{total})"

def render_quasi_vincente(code: str, missed_leg: str) -> str:
    line = _choice("almost_win") or "A un passo dalla leggenda"
    return f"💔 <b>{line}</b> (#{code})\nSaltata per: {missed_leg}"

def render_cuori_spezzati(code: str) -> str:
    line = _choice("heartbreak") or "Ci rifacciamo subito. 💔"
    return f"💔 <b>Cuori Spezzati</b> (#{code})\n{line}"

def render_story_for_match(home: str, away: str) -> str:
    title = _choice("story_titles") or "Sfida calda"
    body  = f"{home}–{away}: scegliamo il colpo facile, solidi e rumorosi. 😉"
    return f"⚔️ <b>{title}</b>\n{body}"

def render_value_scanner(match_str: str, market: str, odds: float, note: str) -> str:
    return f"🔎 <b>Value Scanner</b>\n{match_str}\n{market} @ {odds:.2f}\n{note}"

def render_live_alert(txt: str) -> str:
    return f"⚠️ <b>LIVE ALERT</b>\n{txt}"

def render_celebration(code: str, total_odds: float) -> str:
    shout = _choice("celebrations") or "CASSA!"
    return f"🎉 <b>{shout}</b> (#{code}) @ {total_odds:.2f}\nAI Pro Tips non dorme mai. 🔥"
