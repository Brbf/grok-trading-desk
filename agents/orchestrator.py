from .scout import run_scout
from .news import run_news
from .charts import run_charts
from .sentiment import run_sentiment
from .skeptic import run_skeptic
from .chief import run_chief

def run_trading_desk():
    # Mock data - replace with real feeds carefully
    market = "BTC volume spike +8%, price 65000"
    news = "Partner announcement, mentions up 4x"
    ohlcv = "1h candles: rising, support 64000"
    social = "Twitter bullish, fear greed 72"

    scout_out = run_scout(market)
    news_out = run_news(news)
    charts_out = run_charts(ohlcv)
    sent_out = run_sentiment(social)

    proposal = f"Scout: {scout_out}\nNews: {news_out}\nCharts: {charts_out}\nSentiment: {sent_out}"
    skeptic_out = run_skeptic(proposal)

    all_reports = f"{proposal}\nSkeptic: {skeptic_out}"
    final = run_chief(all_reports)

    return {
        "scout": scout_out,
        "news": news_out,
        "charts": charts_out,
        "sentiment": sent_out,
        "skeptic": skeptic_out,
        "chief": final
    }
