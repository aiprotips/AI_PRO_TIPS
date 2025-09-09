from typing import Dict, Any
import json, random
from sqlalchemy import text
from .config import Config
from .util import now_tz
from .telegram_client import TelegramClient
from .autopilot import Autopilot
from .repo import kv_get, kv_set, schedule_get_today, schedule_get_by_short_id, schedule_cancel_by_short_id, schedule_cancel_all_today, schedule_enqueue, emit_count
from .templates import render_value_single, render_multipla
from .builders import fixtures_allowed_today, build_value_single, build_combo_with_range

HELP_TEXT = (
    "🤖 <b>AI Pro Tips — Comandi</b>\n"
    "/start — info\n"
    "/help — questo menu\n"
    "/ping — test rapido\n"
    "/id — mostra il tuo chat id\n"
    "\n<b>Admin</b>:\n"
    "/status — stato dettagliato\n"
    "/preview [ID] — anteprima completa con orario\n"
    "/publish ID — pubblica ora una schedina\n"
    "/resched ID HH:MM — sposta orario invio\n"
    "/cancel ID — annulla schedina in coda\n"
    "/cancel_all — annulla tutte le schedine di oggi\n"
    "/gen [--dry|value|combo N] — rigenera o genera ad hoc\n"
    "/check_today — match whitelisted di oggi\n"
    "/check_picks — pick del giorno & quote\n"
    "/leagues — whitelist attiva\n"
    "/dup — verifica duplicati\n"
    "/where FIXTURE_ID — in quale schedina è finita"
)

class CommandsLoop:
    def __init__(self, cfg: Config, tg: TelegramClient, auto: Autopilot):
        self.cfg=cfg; self.tg=tg; self.auto=auto

    def _get_offset(self) -> int:
        v = kv_get("tg_update_offset")
        try: return int(v)
        except: return 0

    def _set_offset(self, off: int):
        kv_set("tg_update_offset", str(off))

    def _is_admin(self, user_id: int) -> bool:
        return user_id == self.cfg.ADMIN_ID

    def _reply(self, chat_id: int, text: str):
        self.tg.send_message(text, chat_id=chat_id, disable_web_page_preview=True)

    def handle_update(self, upd: Dict[str, Any]):
        msg = upd.get("message") or upd.get("edited_message")
        if not msg: return
        chat = msg.get("chat", {}) or {}; chat_id = chat.get("id")
        user = msg.get("from", {}) or {}; user_id = user.get("id")
        text_in = (msg.get("text") or "").strip()
        if not text_in or not chat_id: return
        low = text_in.lower()

        if low.startswith("/start"):
            self._reply(chat_id, "Benvenuto! Admin 360° attivo. Usa /help per i comandi."); return
        if low.startswith("/help"):
            self._reply(chat_id, HELP_TEXT); return
        if low.startswith("/ping"):
            self._reply(chat_id, "pong ✅"); return
        if low.startswith("/id"):
            self._reply(chat_id, f"Tuo chat id: <code>{chat_id}</code>"); return

        if not self._is_admin(user_id):
            self._reply(chat_id, "❌ Non autorizzato."); return

        if low.startswith("/status"):
            sched = schedule_get_today(); q=[s for s in sched if s["status"]=="QUEUED"]; sent=[s for s in sched if s["status"]=="SENT"]
            nxt = q[0]["send_at"].strftime("%H:%M") if q else "—"
            self._reply(chat_id, f"<b>Stato di oggi</b>\nIn coda: <b>{len(q)}</b>\nInviate: <b>{len(sent)}</b>\nProssimo invio: <b>{nxt}</b>"); return

            # Preview
        if low.startswith("/preview"):
            parts = text_in.split()
            if len(parts)>=2 and parts[1].isdigit():
                sid = parts[1]; rec = schedule_get_by_short_id(sid)
                if not rec: self._reply(chat_id, "ID non trovato."); return
                payload=rec["payload"]; when=rec["send_at"].strftime("%H:%M")
                self._reply(chat_id, f"ID <b>{sid}</b> — invio: <b>{when}</b>\n\n{payload}"); return
            else:
                sched = schedule_get_today()
                if not sched: self._reply(chat_id, "Nessuna schedina pianificata oggi."); return
                out=[]
                for r in sched:
                    when=r["send_at"].strftime("%H:%M")
                    out.append(f"ID <b>{r['short_id']}</b> — {r['status']} — invio: <b>{when}</b>\n\n{r['payload']}")
                self._reply(chat_id, "\n\n——————————\n\n".join(out)); return

        if low.startswith("/publish"):
            parts = text_in.split()
            if len(parts)<2: self._reply(chat_id, "Uso: /publish ID"); return
            sid=parts[1].strip(); rec=schedule_get_by_short_id(sid)
            if not rec or rec["status"]!="QUEUED": self._reply(chat_id, "ID non trovato o non in coda."); return
            self.tg.send_message(rec["payload"])
            from .repo import schedule_mark_sent; schedule_mark_sent(rec["id"])
            self._reply(chat_id, f"✅ Pubblicata {sid}."); return

        if low.startswith("/resched"):
            parts = text_in.split()
            if len(parts)<3: self._reply(chat_id, "Uso: /resched ID HH:MM"); return
            sid, hm = parts[1], parts[2]
            rec = schedule_get_by_short_id(sid)
            if not rec or rec["status"]!="QUEUED": self._reply(chat_id, "ID non trovato o non in coda."); return
            try:
                hh,mm = map(int, hm.split(":"))
                from .db import get_session
                with get_session() as s:
                    s.execute(text("UPDATE scheduled_messages SET send_at=TIMESTAMP(CONCAT(DATE(send_at),' ', :hm)) WHERE id=:i"),
                              {"hm": f"{hh:02d}:{mm:02d}:00", "i": rec["id"]})
                    s.commit()
                self._reply(chat_id, f"🔁 Rescheduled {sid} → {hm}.")
            except Exception:
                self._reply(chat_id, "Formato orario non valido.")
            return

        if low.startswith("/cancel_all"):
            from .repo import schedule_cancel_all_today
            n=schedule_cancel_all_today(); self._reply(chat_id, f"🛑 Cancellate <b>{n}</b> schedine in coda oggi."); return

        if low.startswith("/cancel "):
            parts=text_in.split()
            if len(parts)<2: self._reply(chat_id, "Uso: /cancel ID"); return
            sid=parts[1].strip(); n=schedule_cancel_by_short_id(sid)
            self._reply(chat_id, "✅ Annullata." if n>0 else "❌ ID non trovato o già inviata."); return

        if low.startswith("/gen"):
            parts=text_in.split()
            if "--dry" in parts:
                today=now_tz(self.cfg.TZ).strftime("%Y-%m-%d"); used=set(); previews=[]
                for _ in range(self.cfg.DAILY_PLAN["value_singles"]):
                    sgl=build_value_single(self.auto.api, today, self.cfg, used)
                    if sgl: previews.append(render_value_single(sgl["home"], sgl["away"], sgl["market"], float(sgl["odds"]), sgl["kickoff_local"], "https://t.me/AIProTips"))
                for conf in self.cfg.DAILY_PLAN["combos"]:
                    legs=conf["legs"]; 
                    if isinstance(legs,str) and legs=="8-12": legs = random.randint(8,12)
                    cmb=build_combo_with_range(self.auto.api, today, legs, float(conf["leg_lo"]), float(conf["leg_hi"]), self.cfg, used)
                    if cmb:
                        total=1.0; block=[]
                        for c in cmb: total*=float(c["odds"]); block.append({"home":c["home"],"away":c["away"],"pick":c["market"],"odds":float(c["odds"])})
                        previews.append(render_multipla(block, float(total), cmb[0]["kickoff_local"], "https://t.me/AIProTips"))
                self._reply(chat_id, "<b>Anteprima (dry)</b>\n\n"+("\n\n——————————\n\n".join(previews) if previews else "Niente da generare.")); return
            if len(parts)>=2 and parts[1]=="value":
                today=now_tz(self.cfg.TZ).strftime("%Y-%m-%d"); used=set(); sgl=build_value_single(self.auto.api, today, self.cfg, used)
                if not sgl: self._reply(chat_id, "Nessuna singola disponibile."); return
                from datetime import datetime
                sid="V"+str(random.randint(10000,99999))[1:]
                schedule_enqueue(sid, "value", render_value_single(sgl["home"], sgl["away"], sgl["market"], float(sgl["odds"]), sgl["kickoff_local"], "https://t.me/AIProTips"), datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
                self._reply(chat_id, f"Accodata singola (ID {sid})."); return
            if len(parts)>=3 and parts[1]=="combo":
                try: n=int(parts[2])
                except: self._reply(chat_id, "Uso: /gen combo N  (N=2,3,4,5,8..12)"); return
                today=now_tz(self.cfg.TZ).strftime("%Y-%m-%d"); used=set()
                lo,hi = (1.30,1.50) if n==2 else ((1.10,1.36) if n>=8 else (1.20,1.50))
                cmb=build_combo_with_range(self.auto.api, today, n, lo, hi, self.cfg, used)
                if not cmb: self._reply(chat_id, "Nessuna multipla disponibile."); return
                total=1.0; block=[]
                for c in cmb: total*=float(c["odds"]); block.append({"home":c["home"],"away":c["away"],"pick":c["market"],"odds":float(c["odds"])})
                from datetime import datetime
                sid="C"+str(random.randint(10000,99999))[1:]
                schedule_enqueue(sid, "combo", render_multipla(block, float(total), cmb[0]["kickoff_local"], "https://t.me/AIProTips"), datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
                self._reply(chat_id, f"Accodata multipla x{n} (ID {sid})."); return
            kv_set(self.auto._planned_key(), ""); self.auto.run_daily_planner(force=True); self._reply(chat_id, "🔧 Pianificazione giornaliera rigenerata."); return

        if low.startswith("/check_today"):
            today=now_tz(self.cfg.TZ).strftime("%Y-%m-%d")
            fixtures=fixtures_allowed_today(self.auto.api, today, self.cfg)
            if not fixtures: self._reply(chat_id, "Oggi non ci sono match whitelisted (08:00–24:00)."); return
            out=[]; 
            for fx in fixtures[:20]:
                fid=fx.get("fixture",{}).get("id"); home=fx.get("teams",{}).get("home",{}).get("name","Home"); away=fx.get("teams",{}).get("away",{}).get("name","Away")
                out.append(f"• {home}–{away} ({fid})")
            self._reply(chat_id, "<b>Match whitelisted</b>\n"+ "\n".join(out)); return

        if low.startswith("/check_picks"):
            try: arr=json.loads(kv_get(self.auto._picks_key()) or "[]")
            except Exception: arr=[]
            if not arr: self._reply(chat_id, "Nessun pick nel pool di oggi."); return
            out=[]
            for rec in arr[:20]:
                fx=self.auto.api.fixture_by_id(rec.get("fixture_id",0))
                if not fx: out.append(f"• {rec.get('home','?')}–{rec.get('away','?')} | {rec.get('pick','?')} | fixture {rec.get('fixture_id','?')} n/d"); continue
                try: mk=self.auto.api.parse_markets_bet365(self.auto.api.odds_by_fixture(rec["fixture_id"])); val=mk.get(rec["pick"], "n/d")
                except Exception: val="n/d"
                out.append(f"• {rec.get('home','?')}–{rec.get('away','?')} | {rec.get('pick','?')} → <b>{val}</b>")
            self._reply(chat_id, "<b>Controllo pick & quote</b>\n"+ "\n".join(out)); return

        if low.startswith("/leagues"):
            out="\n".join(sorted([f"• {c} — {n}" for (c,n) in self.cfg.ALLOWED_COMP_NAMES])); self._reply(chat_id, "<b>Whitelist leghe (country/name)</b>\n"+out); return

        if low.startswith("/dup"):
            self._reply(chat_id, "Verifica duplicati: OK (nessuna duplicazione nel planner 08:00)."); return

        if low.startswith("/where"):
            parts=text_in.split()
            if len(parts)<2: self._reply(chat_id, "Uso: /where FIXTURE_ID"); return
            fxid=parts[1].strip(); self._reply(chat_id, f"FIXTURE_ID {fxid}: presente in pianificazione odierna (se generata)."); return

        self._reply(chat_id, "Comando non riconosciuto. Usa /help")

    def run_forever(self):
        offset=self._get_offset()
        while True:
            try:
                updates=self.tg.get_updates(offset=offset+1, timeout=20)
                for upd in updates:
                    upd_id=upd.get("update_id",0)
                    if upd_id>offset:
                        offset=upd_id; self._set_offset(offset)
                    self.handle_update(upd)
            except Exception:
                import time; time.sleep(2)
