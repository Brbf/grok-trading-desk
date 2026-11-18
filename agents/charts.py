SYSTEM = (
    "You are Charts. Comment on the price levels you are given. "
    "Do not invent a different entry. Reply JSON: {entry: float, exit: float, stop: float, side: str}."
)


def review_levels(candidate: dict) -> dict:
    """Levels taken from the closed-bar signal. Exit is a time stop, so there is no target."""
    direction = int(candidate["direction"])
    entry = float(candidate["entry_ref"])
    stop = entry - direction * float(candidate["stop_distance"])
    return {
        "entry": entry,
        "exit": None,
        "stop": stop,
        "side": "long" if direction > 0 else "short",
        "source": "price",
        "symbol": candidate.get("symbol"),
        "time": candidate.get("time"),
    }


def run_charts(ohlcv: str) -> str:
    """Advisory language-model call. The paper order uses review_levels, not this text."""
    from .base import call_agent
    return call_agent(SYSTEM, ohlcv)
