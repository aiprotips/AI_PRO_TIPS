import os, json, random, time

# Path del file template
_TPL_PATH = os.path.join(os.path.dirname(__file__), "data", "templates.json")
_cache = {"ts": 0, "data": {}}

# Fallback minimal (in caso il json non sia presente)
_FALLBACK = {
    "cta_link": "👉 {link}",
    "emojis_gasanti": ["🔥","🚀","⚡","💎","🏆","🎯","💥","🎉","💪","🧨"],
    "value_single": {"title":"🔎 <b>VALUE SCANNER</b>", "outro_pool":["Andiamo a prendercela."]},
    "multipla": {
        "title_map":{"2":"🧩 <b>DOPPIA</b> 🧩","3":"🎻 <b>TRIPLA</b> 🎻","5":"🎬 <b>QUINTUPLA</b> 🎬","long":"💎 <b>SUPER COMBO</b> 💎"},
        "leg_line":"• {home} 🆚 {away}\n   🎯 {pick} — <b>{odds:.2f}</b>",
        "footer":"💰 Quota totale: <b>{total_odds:.2f}</b>\n🕒 Calcio d’inizio: {kickoff}",
        "outro_pool":["Una a una fino alla cassa."]
    },
    "live_alert": {"title":"⚡ <b>LIVE ALERT</b> ⚡","body":"⏱️ {minute}’ — la favorita <b>{fav}</b> è sotto contro {other}.\nQuota live: {odds_str}","outro_pool":["Situazione perfetta per rientrare."]},
    "live_celebration": {"title_pool":["COLPO LIVE!"]},
    "progress": {"format":"Avanzamento schedina: {bar} ({taken}/{total})"},
    "celebrations": {
        "title_pool":["CASSA!"],
        "singola":"{home} 🆚 {away}\nRisultato: <b>{score}</b>\nPick: {pick} ✅ @ <b>{odds:.2f}</b>",
        "multipla_leg_line":"• {home} 🆚 {away}\nRisultato: {score}\nPick: {pick} ✅",
        "multipla_footer":"Quota totale: <b>{total_odds:.2f}</b>"
    },
    "almost_win": {"title_pool":["PER UN SOFFIO"], "body":"Saltata per: {missed_leg}", "motivation_pool":["Non preoccupatevi, la prossima volta sarà nostra. 💪🔥"]},
    "heartbreak": {"title":"💔 <b>CUORI SPEZZATI</b>", "line_pool":["Scivolata a tempo scaduto: testa alta, ripartiamo. 🚀"]},
    "stat_flash": {"wrap":"📊 <b>STATISTICA LAMPO</b>\n\n{line}","phrase_pool":["{HOME} solida, trend Under favorevole vs {AWAY}."]},
    "story": {"title_pool":["Il colpo facile"], "long_body_pool":["La tradizione dice equilibrio, ma i numeri raccontano altro. La nostra scelta è chiara. 🔥"]},
    "banter": {"pool":["La value oggi è tutta dalla nostra parte. 🚀"]}
}

def _load():
    try:
        ts = os.path.getmtime(_TPL_PATH)
        if ts != _cache["ts"]:
            with open(_TPL_PATH, "r", encoding="utf-8") as f:
                _cache["data"] = json.load(f)
            _cache["ts"] = ts
    except Exception:
        _cache["data"] = _FALLBACK
        _cache["ts"] = time.time()

def _get(path, default=None):
    _load()
    cur = _cache["data"]
    for p in path.split("."):
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            return default
    return cur

def _choice(path, fallback_key=None):
    arr = _get(path)
    if not arr and fallback_key:
        arr = _get(fallback_key)
    if not arr:
        arr = _get(path, []) or []
    return random.choice(arr) if arr else ""

def _cta(link: str) -> str:
    return (_get("cta_link") or "👉 {link}").format(link=link)

def _emoji() -> str:
    arr = _get("emojis_gasanti") or _FALLBACK["emojis_gasanti"]
    return random.choice(arr)

# ------------- RENDERERS -------------

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

def render_multipla(legs, total_odds: float, kickoff: str, link: str) -> str:
    """
    legs: List[{'home','away','pick','odds'}]
    """
    n = len(legs)
    if 8 <= n <= 12:
        title = _get("multipla.title_map.long")
    else:
        title = _get(f"multipla.title_map.{n}") or f"🚀 <b>MULTIPLA x{n}</b> 🚀"
    leg_tpl = _get("multipla.leg_line")
    body_lines = []
    for e in legs:
        body_lines.append(leg_tpl.format(home=e['home'], away=e['away'], pick=e['pick'], odds=float(e['odds'])))
    body = "\n".join(body_lines)
    footer = _get("multipla.footer").format(total_odds=float(total_odds), kickoff=kickoff)
    outro = _choice("multipla.outro_pool")
    return (
        f"{title}\n\n"
        f"{body}\n\n"
        f"{footer}\n\n"
        f"{_emoji()} {outro}\n"
        f"{_cta(link)}"
    )

def render_live_alert(fav: str, other: str, minute: int, odds_str: str, link: str) -> str:
    title = _get("live_alert.title")
    body = _get("live_alert.body").format(fav=fav, other=other, minute=minute, odds_str=odds_str or "n/d")
    outro = _choice("live_alert.outro_pool")
    return f"{title}\n\n{body}\n\n{_emoji()} {outro}\n{_cta(link)}"

def render_live_celebration(fav: str, other: str, score: str, odds: float, link: str) -> str:
    title = _choice("live_celebration.title_pool") or "COLPO LIVE!"
    e = _emoji()
    return (
        f"{e} <b>{title}</b> {e}\n\n"
        f"{fav} 🆚 {other}\n"
        f"Risultato: <b>{score}</b>\n"
        f"Pick live ✅ @ <b>{odds:.2f}</b>\n\n"
        f"{_cta(link)}"
    )

def render_progress_bar(taken: int, total: int) -> str:
    bar = "✅"*int(taken) + "⬜"*max(0, int(total)-int(taken))
    fmt = _get("progress.format") or _FALLBACK["progress"]["format"]
    return fmt.format(bar=bar, taken=int(taken), total=int(total))

def render_celebration_singola(home: str, away: str, score: str, pick: str, odds: float, link: str) -> str:
    title = _choice("celebrations.title_pool") or "CASSA!"
    e = _emoji()
    body = (_get("celebrations.singola") or _FALLBACK["celebrations"]["singola"]).format(
        home=home, away=away, score=score, pick=pick, odds=float(odds)
    )
    return f"{e} <b>{title}</b> {e}\n\n{body}\n\n{_cta(link)}"

def render_celebration_multipla(selections, total_odds: float, link: str) -> str:
    title = _choice("celebrations.title_pool") or "CASSA!"
    e = _emoji()
    leg_tpl = _get("celebrations.multipla_leg_line")
    lines = []
    for s in selections:
        lines.append(leg_tpl.format(home=s['home'], away=s['away'], score=s.get('score',''), pick=s['pick']))
    body = "\n".join(lines)
    footer = (_get("celebrations.multipla_footer") or _FALLBACK["celebrations"]["multipla_footer"]).format(total_odds=float(total_odds))
    return f"{e} <b>{title}</b> {e}\n\n{body}\n\n{footer}\n\n{_cta(link)}"

def render_quasi_vincente(missed_leg: str) -> str:
    title = _choice("almost_win.title_pool") or "PER UN SOFFIO"
    body = (_get("almost_win.body") or "Saltata per: {missed_leg}").format(missed_leg=missed_leg)
    motiv = _choice("almost_win.motivation_pool") or "Non preoccupatevi, la prossima volta sarà nostra. 💪🔥"
    return f"💔 <b>{title}</b>\n\n{body}\n\n{motiv}"

def render_cuori_spezzati() -> str:
    title = _get("heartbreak.title") or "💔 <b>CUORI SPEZZATI</b>"
    line = _choice("heartbreak.line_pool") or "Scivolata a tempo scaduto: testa alta, ripartiamo. 🚀"
    return f"{title}\n\n{line}"

def render_stat_flash(home: str, away: str, line_override: str = None) -> str:
    if line_override:
      line = line_override
    else:
      phrase = _choice("stat_flash.phrase_pool")
      line = (phrase or "").replace("{HOME}", home).replace("{AWAY}", away)
    wrap = _get("stat_flash.wrap") or _FALLBACK["stat_flash"]["wrap"]
    return wrap.format(line=line)

def render_story_long(home: str, away: str) -> str:
    title = _choice("story.title_pool") or "Il colpo facile"
    body = _choice("story.long_body_pool") or "La tradizione dice equilibrio, ma i numeri raccontano altro. La nostra scelta è chiara. 🔥"
    return f"⚔️ <b>{title}</b>\n\n{home}–{away}: {body}"

def render_banter() -> str:
    return _choice("banter.pool") or "La value oggi è tutta dalla nostra parte. 🚀"
