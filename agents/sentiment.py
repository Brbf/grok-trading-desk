from .base import call_agent

SYSTEM = "You are Sentiment. Read crowd mood. Reply JSON: {score: -1 to 1, summary: str}"

def run_sentiment(social_data: str) -> str:
    return call_agent(SYSTEM, social_data)
