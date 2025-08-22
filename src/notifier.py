import os
import httpx

class TelegramNotifier:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")

    def send(self, message: str):
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        httpx.post(url, data={"chat_id": self.chat_id, "text": message})
