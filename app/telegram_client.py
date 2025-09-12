import requests

class TelegramClient:
    def __init__(self, token: str):
        self.base = f"https://api.telegram.org/bot{token}"

    def send_message(self, chat_id: int, text: str, disable_web_page_preview: bool = True, parse_mode: str = "HTML"):
        r = requests.post(f"{self.base}/sendMessage", json={
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": disable_web_page_preview,
            "parse_mode": parse_mode
        }, timeout=25)
        r.raise_for_status()
        return r.json()

    def get_updates(self, offset: int = None, timeout: int = 25):
        params = {"timeout": timeout}
        if offset is not None:
            params["offset"] = offset
        r = requests.get(f"{self.base}/getUpdates", params=params, timeout=timeout+5)
        r.raise_for_status()
        js = r.json()
        if not js.get("ok"):
            return []
        return js.get("result", [])
