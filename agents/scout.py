from .base import call_agent

SYSTEM = "You are Scout. Detect volume anomalies and big moves in crypto/stocks. Reply with short JSON: {anomaly: bool, symbol: str, reason: str}"

def run_scout(market_data: str) -> str:
    return call_agent(SYSTEM, market_data)
