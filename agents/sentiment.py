SYSTEM = (
    "You are Sentiment. If the brief says there is no verified social feed, "
    "say so and do not invent a score. Reply JSON: {score: number|null, summary: str}."
)


def review_sentiment(brief: dict | None = None) -> dict:
    """There is no social feed on this desk. The score stays empty and is not a vote."""
    return {
        "score": None,
        "summary": "no verified social feed; ignored",
        "ignored": True,
        "source": "none",
    }


def run_sentiment(social_data: str) -> str:
    """Advisory language-model call. review_sentiment is what the paper desk records."""
    from .base import call_agent
    return call_agent(SYSTEM, social_data)
