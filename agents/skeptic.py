from .base import call_agent

SYSTEM = "You are Skeptic. Argue against every trade. Reply JSON: {approve: bool, reason: str, action: buy|wait|skip}"

def run_skeptic(proposal: str) -> str:
    return call_agent(SYSTEM, proposal)
