# app/scheduler.py
import time
from .repo_sched import due_now, mark_sent

class ScheduledPublisher:
    def __init__(self, cfg, tg):
        self.cfg = cfg
        self.tg = tg

    def tick(self):
        rows = due_now(limit=10)
        for r in rows:
            try:
                # invio sul canale
                self.tg.send_message(r["payload"], chat_id=self.cfg.CHANNEL_ID, disable_web_page_preview=True)
                mark_sent(int(r["id"]))
            except Exception as e:
                # lascio in coda; riproverà al prossimo giro
                print(f"[publisher] send failed id={r['id']}: {e}")

    def run_forever(self):
        while True:
            try:
                self.tick()
            except Exception as e:
                print(f"[publisher] loop error: {e}")
            time.sleep(20)
