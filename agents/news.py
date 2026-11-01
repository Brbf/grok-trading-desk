from .base import call_agent

SYSTEM = "You are News. Analyze why price is moving from headlines/social. Reply short JSON: {reason: str, bullish: bool}"

def run_news(news_data: str) -> str:
    return call_agent(SYSTEM, news_data)
