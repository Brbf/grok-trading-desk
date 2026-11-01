# Grok Trading Desk

Multi-agent AI trading system (paper trading only).

**WARNING**: High risk of real losses. Use only paper trading. No financial advice.

## Agents
- Scout: market anomalies
- News: news/sentiment
- Charts: technical levels
- Sentiment: social
- Skeptic: risk control
- Chief: final decision

## Setup
```bash
pip install -r requirements.txt
export XAI_API_KEY=your_key
python main.py
```

## Notes
- Mock market data for safety
- Orchestrated with simple sequential flow
- Extend with real exchange APIs at your own risk
