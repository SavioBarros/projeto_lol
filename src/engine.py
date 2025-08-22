import os
import asyncio
from src.providers import MockProvider, PandaScoreProvider
from src.fair_odds import FairOddsEngine
from src.notifier import TelegramNotifier

class OpeningEngine:
    def __init__(self):
        self.provider = (MockProvider() if os.getenv("ODDS_PROVIDER") == "MOCK" 
                         else PandaScoreProvider())
        self.fair = FairOddsEngine()
        self.notifier = TelegramNotifier()
        self.poll_interval = int(os.getenv("POLL_INTERVAL_SECONDS", 60))

    async def run(self):
        while True:
            odds = self.provider.get_odds_for_matches()
            for m in odds:
                msg = f"Match: {m['team1']} vs {m['team2']}\nOdds: {m['odds']}"
                self.notifier.send(msg)
            await asyncio.sleep(self.poll_interval)
