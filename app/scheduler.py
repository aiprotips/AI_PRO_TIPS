# app/scheduler.py — publisher robusto (firma corretta + guardie)
import time
from .repo_sched import due_now, mark_sent, ensure_table
from .telegram_client import TelegramClient

def _send(tg: TelegramClient, chat_id: int, text: str):
    try:
        return tg.send_message(chat_id, text)  # firma corretta
    except TypeError:
        return tg.send_message(text, chat_id=chat_id)
    except Exception:
        try:
            return tg.send_message(chat_id, text)
        except Exception:
            pass

class ScheduledPublisher:
    def __init__(self, cfg, tg: TelegramClient):
        self.cfg = cfg
        self.tg = tg
        ensure_table()

    def run_forever(self):
        while True:
            try:
                ch = getattr(self.cfg, "CHANNEL_ID", None)
                if not ch:
                    time.sleep(10); continue

                rows = due_now(limit=10)
                for r in rows:
                    try:
                        _send(self.tg, int(ch), r["payload"])
                        mark_sent(int(r["id"]))
                    except Exception as e:
                        # non segniamo SENT se fallisce l'invio
                        print(f"[publisher] send failed id={r.get('id')}: {e}")
                        continue
            except Exception as e:
                print(f"[publisher] loop error: {e}")
                time.sleep(5)
            time.sleep(5)
