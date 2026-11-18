SYSTEM = "You are Skeptic. Argue against every trade. Reply JSON: {approve: bool, reason: str, action: buy|wait|skip}"


def review_candidate(candidate: dict, limits: dict) -> dict:
    """Deterministic risk-skeptic veto. Paper path only; never returns a live buy."""
    reasons = []
    if candidate.get("spread_atr", 0) > float(limits["spread_atr_max"]):
        reasons.append("spread_vs_atr")
    lo = float(limits["atr_ratio_min"])
    hi = float(limits["atr_ratio_max"])
    if not lo <= float(candidate.get("atr_ratio", 0)) <= hi:
        reasons.append("volatility_not_aligned")
    if not candidate.get("htf_agree"):
        reasons.append("no_mtf_agreement")
    if candidate.get("origin") != "price" or not candidate.get("price_confirmed"):
        reasons.append("external_unconfirmed")
    if candidate.get("news_blackout"):
        reasons.append("news_blackout")
    if float(candidate.get("range_atr", 0)) > float(limits["outlier_range_atr"]):
        reasons.append("outlier_chase")
    if reasons:
        return {"approve": False, "reason": ",".join(reasons), "action": "skip"}
    return {"approve": True, "reason": "ok", "action": "paper"}


def run_skeptic(proposal: str) -> str:
    from .base import call_agent
    return call_agent(SYSTEM, proposal)
