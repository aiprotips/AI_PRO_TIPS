import os, json, random, time
from typing import Dict, Any

_BASE_DIR = os.path.dirname(__file__)
_TPL_PATH = os.path.join(_BASE_DIR, "data", "templates.json")
_PHRASES_DIR = os.path.join(_BASE_DIR, "phrasi")
_cache = {"ts": 0.0, "data": {}}

# ------------------------------
# FALLBACK (usato se mancano templates.json/phrasi)
# ------------------------------
_FALLBACK = {
  "cta_link": "👉 {link}",
  "emojis_gasanti": ["🔥","🚀","⚡","💎","🏆","🎯","💥","🎉","💪","🧨"],

  # Singola/value scanner
  "value_single": {
    "title": "🔎 <b>VALUE SCANNER</b>",
    "outro_pool": [
      "Andiamo a prendercela.",
      "Linea pulita, si va.",
      "Semplice e solida: dentro.",
      "Niente fronzoli: questa è da fare."
    ]
  },

  # Multiple (Doppia / Tripla / Quintupla / Super Combo)
  "multipla": {
    "title_map": {
      "2": "🧩 <b>DOPPIA</b> 🧩",
      "3": "🎻 <b>TRIPLA</b> 🎻",
      "5": "🎬 <b>QUINTUPLA</b> 🎬",
      "long": "💎 <b>SUPER COMBO</b> 💎"  # 8–12
    },
    "leg_line": "• {home} 🆚 {away}\n   🎯 {pick} — <b>{odds:.2f}</b>",
    "footer": "💰 Quota totale: <b>{total_odds:.2f}</b>\n🕒 Calcio d’inizio: {kickoff}",
    "outro_pool": [
      "Una a una fino alla cassa.",
      "Costruiamo valore, non fortuna.",
      "Ordine, criterio e sangue freddo.",
      "Combo bilanciata, andiamo."
    ]
  },

  # Live alert
  "live_alert": {
    "title": "⚡ <b>LIVE ALERT</b> ⚡",
    "body": "⏱️ {minute}’ — {fav} è sotto contro {other}.\nQuota pre: {preodd} | Quota live: {odds_str}",
    "outro_pool": [
      "Situazione perfetta per rientrare.",
      "Momento ideale per colpire.",
      "Ribaltone in vista: opportunità.",
      "Timing giusto, pressione on."
    ]
  },

  # Live energy
  "live_energy": {
    "format": "⏱️ {minute}’ — {home}–{away}: {line}  (#{sid})"
  },

  # Celebrazioni
  "celebrations": {
    "title_pool": [
      "CASSA!",
      "Dentro! 🎯",
      "Boom! 💥",
      "Che colpo! 🏆",
      "Pulita e in tasca! 💎"
    ],
    "singola": "{home} 🆚 {away}\nRisultato: <b>{score}</b>\nPick: {pick} ✅ @ <b>{odds:.2f}</b>",
    "multipla_leg_line": "• {home} 🆚 {away}\n   Risultato: <b>{score}</b>\n   Pick: {pick} ✅",
    "multipla_footer": "Quota totale: <b>{total_odds:.2f}</b>"
  },

  # Quasi vincente
  "almost_win": {
    "title_pool": [
      "PER UN SOFFIO",
      "QUASI LEGGENDA",
      "SFUMATA SUL PIÙ BELLO",
      "CI È MANCATO UN NULLA"
    ],
    "body": "Saltata per 1: {missed_leg}",
    "motivation_pool": [
      "Non preoccupatevi, la prossima volta sarà nostra. 💪🔥",
      "Stessa fame, testa fredda, si riparte subito. 🚀",
      "La linea è giusta: continuità e arriva la cassa. 🎯",
      "Zero drammi: rifocalizziamoci e andiamo. ⚡"
    ]
  },

  # Cuori spezzati
  "heartbreak": {
    "title": "💔 <b>CUORI SPEZZATI</b>",
    "line_pool": [
      "Scivolata a tempo scaduto: testa alta, ripartiamo. 🚀",
      "Giornata storta: archiviamo e torniamo a far male. 💪",
      "Succede: reset e si torna sul pezzo. ⚙️",
      "Non cambia la rotta: disciplina e avanti. 🎯"
    ]
  },

  # Storytelling
  "story": {
    "title_pool": [
      "Il colpo facile",
      "Partita di sostanza",
      "Dettagli che fanno la differenza",
      "Qui si vince col ritmo"
    ],
    "long_body_pool": [
      "Non è solo una sensazione: i numeri parlano chiaro, l’inerzia è dalla nostra. 🔥",
      "La narrativa dice equilibrio, i dati raccontano un’altra storia: intensità, continuità e struttura. 🚀",
      "Quando forma e trend si allineano, la value non è un’opinione. 🎯"
    ]
  },

  # Banter
  "banter": {
    "pool": [
      "La value oggi è tutta dalla nostra parte. 🚀",
      "Noi lavoriamo, gli altri sperano. 😉",
      "Poche parole, tanti ticket. 💎",
      "Linee pulite, mani ferme. Andiamo. ⚡"
    ]
  }
}

# ------------------------------
# Mappatura file esterni /phrasi
# ------------------------------
_PHRASES_MAPPING = {
  "cassa.txt": ("celebrations.title_pool",),
  "quasi.txt": ("almost_win.title_pool", "almost_win.motivation_pool"),
  "cuori.txt": ("heartbreak.line_pool",),
  "banter.txt": ("banter.pool",),
  "story_title.txt": ("story.title_pool",),
  "story_body.txt": ("story.long_body_pool",)
}

def _file_lines(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return [ln.strip() for ln in f if ln.strip()]
    except Exception:
        return []

def _merge_phrases(data: Dict[str, Any]):
    if not os.path.isdir(_PHRASES_DIR): return
    for fname, targets in _PHRASES_MAPPING.items():
        lines = _file_lines(os.path.join(_PHRASES_DIR, fname))
        if not lines: continue
        for target in targets:
            cur = data
            parts = target.split(".")
            for p in parts[:-1]:
                if p not in cur or not isinstance(cur[p], dict):
                    cur[p] = {}
                cur = cur[p]
            arr = cur.get(parts[-1], [])
            if not isinstance(arr, list): arr = []
            seen = set(arr)
            for ln in lines:
                if ln not in seen:
                    arr.append(ln); seen.add(ln)
            cur[parts[-1]] = arr

def _load():
    try:
        ts = os.path.getmtime(_TPL_PATH)
        if ts != _cache["ts"]:
            with open(_TPL_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            _merge_phrases(data)
            _cache["data"] = data
            _cache["ts"] = ts
    except Exception:
        data = dict(_FALLBACK)
        _merge_phrases(data)
        _cache["data"] = data
        _cache["ts"] = time.time()

def _get(path: str, default=None):
    _load()
    cur = _cache["data"]
    for p in path.split("."):
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            return default
    return cur

def _choice(path: str, fallback_key: str = None):
    arr = _get(path) or (_get(fallback_key) if fallback_key else None) or []
    return random.choice(arr) if arr else ""

def _cta(link: str) -> str:
    return (_get("cta_link") or "👉 {link}").format(link=link)

def _emoji() -> str:
    return random.choice(_get("emojis_gasanti") or _FALLBACK["emojis_gasanti"])

# ------------------------------
# RENDERERS PUBBLICI
# ------------------------------

def render_value_single(home: str, away: str, pick: str, odds: float, kickoff: str, link: str) -> str:
    title = _get("value_single.title") or _FALLBACK["value_single"]["title"]
    outro = _choice("value_single.outro_pool")
    return (
        f"{title} \n\n"
        f"{home} 🆚 {away}\n"
        f"🎯 {pick}\n\n"
        f"💰 Quota: <b>{odds:.2f}</b>\n"
        f"🕒 Calcio d’inizio: {kickoff}\n\n"
        f"{_emoji()} {outro}\n"
        f"{_cta(link)}"
    )

def render_multipla(legs: list, total_odds: float, kickoff: str, link: str) -> str:
    n = len(legs)
    if 8 <= n <= 12:
        title = _get("multipla.title_map.long") or _FALLBACK["multipla"]["title_map"]["long"]
    else:
        title = _get(f"multipla.title_map.{n}") or f"🚀 <b>MULTIPLA x{n}</b> 🚀"
    leg_tpl = _get("multipla.leg_line") or _FALLBACK["multipla"]["leg_line"]
    body = "\n".join([leg_tpl.format(
        home=e["home"], away=e["away"], pick=e["pick"], odds=float(e["odds"])
    ) for e in legs])
    footer = (_get("multipla.footer") or _FALLBACK["multipla"]["footer"]).format(
        total_odds=float(total_odds), kickoff=kickoff
    )
    outro = _choice("multipla.outro_pool")
    return f"{title}\n\n{body}\n\n{footer}\n\n{_emoji()} {outro}\n{_cta(link)}"

def render_live_alert(fav: str, other: str, minute: int, preodd: str, odds_str: str, link: str) -> str:
    title = _get("live_alert.title") or _FALLBACK["live_alert"]["title"]
    body_tpl = _get("live_alert.body") or _FALLBACK["live_alert"]["body"]
    body = body_tpl.format(fav=fav, other=other, minute=int(minute or 0), preodd=preodd, odds_str=odds_str or "n/d")
    outro = _choice("live_alert.outro_pool")
    return f"{title}\n\n{body}\n\n{_emoji()} {outro}\n{_cta(link)}"

def render_live_energy(home: str, away: str, minute: int, line: str, sid: str) -> str:
    fmt = _get("live_energy.format") or _FALLBACK["live_energy"]["format"]
    return fmt.format(home=home, away=away, minute=int(minute or 0), line=line, sid=sid)

def render_progress_bar(taken: int, total: int) -> str:
    bar = "✅" * int(taken) + "⬜" * max(0, int(total) - int(taken))
    return f"Avanzamento schedina: {bar} ({taken}/{total})"

def render_celebration_singola(home: str, away: str, score: str, pick: str, odds: float, link: str) -> str:
    title = _choice("celebrations.title_pool") or "CASSA!"
    e = _emoji()
    tpl = _get("celebrations.singola") or _FALLBACK["celebrations"]["singola"]
    body = tpl.format(home=home, away=away, score=score, pick=pick, odds=float(odds))
    return f"{e} <b>{title}</b> {e}\n\n{body}\n\n{_cta(link)}"

def render_celebration_multipla(selections: list, total_odds: float, link: str) -> str:
    title = _choice("celebrations.title_pool") or "CASSA!"
    e = _emoji()
    leg_tpl = _get("celebrations.multipla_leg_line") or _FALLBACK["celebrations"]["multipla_leg_line"]
    lines = [leg_tpl.format(home=s["home"], away=s["away"], score=s.get("score",""), pick=s["pick"]) for s in selections]
    body = "\n".join(lines)
    footer = (_get("celebrations.multipla_footer") or _FALLBACK["celebrations"]["multipla_footer"]).format(
        total_odds=float(total_odds)
    )
    return f"{e} <b>{title}</b> {e}\n\n{body}\n\n{footer}\n\n{_cta(link)}"

def render_quasi_vincente(missed_leg: str) -> str:
    title = _choice("almost_win.title_pool") or "PER UN SOFFIO"
    body_tpl = _get("almost_win.body") or _FALLBACK["almost_win"]["body"]
    motiv = _choice("almost_win.motivation_pool") or "Non preoccupatevi, la prossima volta sarà nostra. 💪🔥"
    body = body_tpl.format(missed_leg=missed_leg)
    return f"💔 <b>{title}</b>\n\n{body}\n\n{motiv}"

def render_cuori_spezzati() -> str:
    title = _get("heartbreak.title") or _FALLBACK["heartbreak"]["title"]
    line = _choice("heartbreak.line_pool") or _FALLBACK["heartbreak"]["line_pool"][0]
    return f"{title}\n\n{line}"

def render_story_long(home: str, away: str) -> str:
    title = _choice("story.title_pool") or _FALLBACK["story"]["title_pool"][0]
    body  = _choice("story.long_body_pool") or _FALLBACK["story"]["long_body_pool"][0]
    return f"⚔️ <b>{title}</b>\n\n{home}–{away}: {body}"

def render_banter() -> str:
    return _choice("banter.pool") or _FALLBACK["banter"]["pool"][0]
