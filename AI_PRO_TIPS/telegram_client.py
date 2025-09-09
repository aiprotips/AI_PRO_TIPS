import requests
from typing import Optional

class TelegramClient:
    def __init__(self, token: str, channel_id: int, admin_id: int = 0):
        self.base = f"https://api.telegram.org/bot{token}"
        self.channel_id = channel_id
        self.admin_id = admin_id

    def send_message(self, text: str, chat_id: Optional[int] = None, disable_web_page_preview: bool=True):
        payload = {
            "chat_id": chat_id or self.channel_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": disable_web_page_preview
        }
        try:
            r = requests.post(f"{self.base}/sendMessage", json=payload, timeout=15)
            if not r.ok:
                print("[TG] sendMessage failed:", r.status_code, r.text)
            return r.json() if r.headers.get("content-type","").startswith("application/json") else None
        except Exception as e:
            print("[TG] Error:", e)

    def notify_admin(self, text: str):
        if self.admin_id:
            self.send_message(text, chat_id=self.admin_id)

    def get_updates(self, offset: int = None, timeout: int = 20):
        params = {"timeout": timeout}
        if offset is not None:
            params["offset"] = offset
        try:
            r = requests.get(f"{self.base}/getUpdates", params=params, timeout=timeout+5)
            if r.ok:
                return r.json().get("result", [])
            print("[TG] getUpdates failed:", r.status_code, r.text)
        except Exception as e:
            print("[TG] getUpdates error:", e)
        return []
#l
