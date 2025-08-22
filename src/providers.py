import os
import httpx

class MockProvider:
    def get_odds_for_matches(self):
        return [{
            "match_id": 1,
            "team1": "Team A",
            "team2": "Team B",
            "odds": {"ML": 1.9, "KillsOver28.5": 2.0}
        }]

class PandaScoreProvider:
    def __init__(self):
        self.base_url = os.getenv("PANDASCORE_BASE", "https://api.pandascore.co")
        self.token = os.getenv("PANDASCORE_TOKEN")

    def get_odds_for_matches(self):
        url = f"{self.base_url}/lol/odds?token={self.token}"
        r = httpx.get(url)
        r.raise_for_status()
        return r.json()
