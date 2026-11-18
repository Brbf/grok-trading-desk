SYSTEM = (
    "You are News. You only comment on the calendar facts you are given. "
    "You do not invent headlines. Reply short JSON: {reason: str, bullish: bool}."
)


def review_news(candidate: dict, calendar_loaded: bool) -> dict:
    """Deterministic news check. No feed, no invented direction."""
    if candidate.get("news_blackout"):
        return {
            "reason": "high_impact_calendar_blackout",
            "bullish": None,
            "used_for_decision": True,
            "source": "calendar",
        }
    if not calendar_loaded:
        return {
            "reason": "no_verified_calendar",
            "bullish": None,
            "used_for_decision": False,
            "source": "none",
        }
    return {
        "reason": "calendar_loaded_no_blackout",
        "bullish": None,
        "used_for_decision": False,
        "source": "calendar",
    }


def run_news(news_data: str) -> str:
    """Advisory language-model call. Not used by the paper decision."""
    from .base import call_agent
    return call_agent(SYSTEM, news_data)
