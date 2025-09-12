from .config import Config
from .telegram_client import TelegramClient
from .api_football import APIFootball
from .commands import CommandsLoop

def main():
    cfg = Config()
    tg = TelegramClient(cfg.TELEGRAM_TOKEN)
    api = APIFootball(cfg.APIFOOTBALL_KEY, tz=cfg.TZ)
    print("[BOOT] Odds bot pronto. Comandi: /quote [today|tomorrow]")
    CommandsLoop(cfg, tg, api).run_forever()

if __name__ == "__main__":
    main()
