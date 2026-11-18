SYSTEM = "You are Chief. Final decision after all agents. Reply JSON: {decision: buy|sell|hold, size: float, reason: str}. The scanner chief is paper-only."


def coordinate(candidate: dict, scout: dict, skeptic: dict, risk: dict) -> dict:
    """Coordinator. Decisions are paper_buy, paper_sell or hold. Never a live order."""
    agreed = (
        bool(scout.get("anomaly"))
        and bool(skeptic.get("approve"))
        and bool(risk.get("approve"))
        and bool(candidate.get("htf_agree"))
        and candidate.get("origin") == "price"
        and bool(candidate.get("price_confirmed"))
        and int(candidate.get("direction") or 0) in (1, -1)
    )
    if not agreed:
        if not scout.get("anomaly"):
            reason = "scout:" + str(scout.get("reason", ""))
        elif not skeptic.get("approve"):
            reason = "skeptic:" + str(skeptic.get("reason", ""))
        elif not risk.get("approve"):
            reason = "risk:" + str(risk.get("reason", ""))
        elif not candidate.get("htf_agree"):
            reason = "no_mtf_agreement"
        else:
            reason = "unverified_source"
        return {"decision": "hold", "size": 0.0, "reason": reason, "mode": "PAPER_ONLY", "live_order": False}
    decision = "paper_buy" if int(candidate["direction"]) > 0 else "paper_sell"
    return {
        "decision": decision,
        "size": float(risk.get("units") or 0.0),
        "reason": "paper_only_scout_risk_coordinator",
        "mode": "PAPER_ONLY",
        "live_order": False,
    }


def run_chief(all_reports: str) -> str:
    from .base import call_agent
    return call_agent(SYSTEM, all_reports)
