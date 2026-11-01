from .base import call_agent

SYSTEM = "You are Chief. Final decision after all agents. Reply JSON: {decision: buy|sell|hold, size: float, reason: str}"

def run_chief(all_reports: str) -> str:
    return call_agent(SYSTEM, all_reports)
