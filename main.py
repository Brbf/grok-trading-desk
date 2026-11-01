import os
from dotenv import load_dotenv
from agents.orchestrator import run_trading_desk

load_dotenv()

if __name__ == "__main__":
    print("Starting paper trading desk...")
    result = run_trading_desk()
    print(result)
