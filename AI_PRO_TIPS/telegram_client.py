import requests

class TelegramClient:
    def __init__(self, token: str, channel_id: int, admin_id: int):
        self.token = token
        self.base = f"https://api.telegram.org/bot{token}"
        self.channel_id = channel_id
        self.admin_id = admin_id

    def send_message(self, text: str, chat_id=None, disable_web_page_preview=True):
        if chat_id is None:
            chat_id = self.channel_id
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": disable_web_page_preview
        }
        r = requests.post(f"{self.base}/sendMessage", json=payload, timeout=20)
        if not r.ok:
            raise RuntimeError(f"Telegram sendMessage error {r.status_code}: {r.text}")
        return r.json()

    def get_updates(self, offset=None, timeout=20):
        params = {"timeout": timeout}
        if offset is not None:
            params["offset"] = offset
        r = requests.get(f"{self.base}/getUpdates", params=params, timeout=timeout+5)
        if not r.ok:
            return []
        js = r.json()
        return js.get("result", []) if js else []

    def notify_admin(self, text: str):
        try:
            self.send_message(text, chat_id=self.admin_id, disable_web_page_preview=True)
        except Exception:
            pass
