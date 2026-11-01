from .base import call_agent

SYSTEM = "You are Charts. Suggest entry, exit, stop-loss. Reply JSON: {entry: float, exit: float, stop: float, side: str}"

def run_charts(ohlcv: str) -> str:
    return call_agent(SYSTEM, ohlcv)
