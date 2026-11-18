SYSTEM = "You are Scout. Detect volume anomalies and big moves. Reply with short JSON: {anomaly: bool, symbol: str, reason: str}"


def evaluate_volume_anomaly(
    symbol: str,
    volume_ratio: float,
    range_atr: float,
    volume_ratio_min: float = 1.5,
    range_atr_min: float = 0.6,
) -> dict:
    """Deterministic Scout used by the scanner. No network call."""
    if volume_ratio >= volume_ratio_min and range_atr >= range_atr_min:
        return {"anomaly": True, "symbol": symbol, "reason": "volume_and_range"}
    if volume_ratio < volume_ratio_min:
        reason = "volume_below_threshold"
    else:
        reason = "range_below_threshold"
    return {"anomaly": False, "symbol": symbol, "reason": reason, "volume_ratio": volume_ratio}


def run_scout(market_data: str) -> str:
    from .base import call_agent
    return call_agent(SYSTEM, market_data)
