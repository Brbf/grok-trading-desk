"""Paper desk entry point. Does not require an API key and never sends an order."""

import json

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from agents.orchestrator import run_trading_desk


def main() -> None:
    print("Paper desk. No live orders. The language model stays off without a real XAI_API_KEY.")
    result = run_trading_desk()
    view = {
        "mode": result.get("mode"),
        "live_order": result.get("live_order"),
        "status": result.get("status"),
        "llm": {k: result.get("llm", {}).get(k) for k in ("enabled", "model")},
        "scan": result.get("scan"),
        "paper_orders": result.get("paper_orders"),
        "decisions": result.get("decisions"),
        "account": result.get("account"),
        "detail": result.get("detail"),
    }
    print(json.dumps(view, indent=2, default=str))


if __name__ == "__main__":
    main()
