"""Standalone exploratory 11-day pattern ablation. Offline research only.

No trades, API keys, network, file writes, model selection or changes to
FabioQuant's immutable 84-day protocol. Future labels are used only for
retrospective scoring after causal features have been produced.
"""
import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path

from agents.geometry_features import geometric_candidates
from agents.pattern_features import decode_hourly_asof, patterns_from_closed_candles

PAIRS = ("BTC-EUR", "ETH-EUR")
DAYS = tuple(f"2024-07-{d:02d}" for d in range(10, 21))


def records(root):
    samples = []
    for day in DAYS:
        data = json.loads((root / (day + "-derived.json")).read_bytes())
        if (data.get("schema") != "FabioQuant-GDELT-PriceNews-PIT-Derived-v1"
                or data.get("day") != day or len(data.get("rows", [])) != 4
                or data.get("source_day_complete") is not True):
            raise ValueError("Unexpected historical report day or schema")
        pages = {}
        for pair in PAIRS:
            raw = (root / (day + "-" + pair.lower() + ".json")).read_bytes()
            if hashlib.sha256(raw).hexdigest() != data["raw_price_pages"][pair]["sha256"]:
                raise ValueError("Historical Coinbase SHA mismatch")
            pages[pair] = raw
        for entry in data["rows"]:
            pair, origin = entry["pair"], entry["origin"]
            if (pair not in PAIRS or not origin.startswith(day)
                    or origin[11:13] not in ("12", "18")):
                raise ValueError("Unexpected observation")
            bars = decode_hourly_asof(pages[pair], origin, lookback=25)
            candle = patterns_from_closed_candles(bars)
            geo = geometric_candidates(bars)
            if (entry.get("eligible_batches") != 23 or
                    entry.get("source_proxy_not_proven_original_publication") is not True):
                raise ValueError("Invalid time-availability contract")
            price, news = entry["price"], entry["news"]
            if (len(price) != 4 or len(news) != 2 or
                    not all(math.isfinite(v) for v in price + news)):
                raise ValueError("Invalid feature vector")
            if type(entry["label"]) is not int or entry["label"] not in (0, 1):
                raise ValueError("Invalid retrospective outcome")
            samples.append({
                "day": day, "pair": pair, "origin": origin,
                "price": price, "news": news,
                "pattern": [sum(candle["flags"].values()),
                            sum(geo["flags"].values())],
                "label": entry["label"],
            })
    samples.sort(key=lambda x: (x["origin"], x["pair"]))
    if len(samples) != 44 or len({(x["origin"], x["pair"]) for x in samples}) != 44:
        raise ValueError("Expected 44 unique observations")
    return samples


def vector(sample, with_patterns):
    return sample["price"] + sample["news"] + (
        sample["pattern"] if with_patterns else [])


def train_predict(train, test, with_patterns):
    if max(x["day"] for x in train) >= min(x["day"] for x in test):
        raise ValueError("Chronology violated")
    matrix = [vector(x, with_patterns) for x in train]
    center = [statistics.median(col) for col in zip(*matrix)]
    mad = [statistics.median(abs(v-c) for v in col)
           for c, col in zip(center, zip(*matrix))]
    scale = [x if x > 1e-12 else 1.0 for x in mad]

    def scaled(x):
        return [max(-10., min(10., (v-c)/s))
                for v, c, s in zip(x, center, scale)]

    X = [scaled(row) for row in matrix]
    n = len(X)
    b = [0.0] * (len(center) + 1)

    def sigmoid(z):
        return 1 / (1 + math.exp(-max(-50., min(50., z))))

    for _ in range(1000):
        grad = [0.0] * len(b)
        for row, sample in zip(X, train):
            e = sigmoid(b[0] + sum(a*v for a,v in zip(b[1:], row))) - sample["label"]
            grad[0] += e/n
            for i, v in enumerate(row, 1):
                grad[i] += e*v/n
        for i in range(1, len(b)):
            grad[i] += b[i]/n
        b = [v - 0.05*g for v, g in zip(b, grad)]
    return [sigmoid(b[0] + sum(a*v for a,v in zip(
        b[1:], scaled(vector(x, with_patterns))))) for x in test]


def metrics(samples, pred):
    ys = [x["label"] for x in samples]
    return {
        "n": len(ys),
        "brier": round(statistics.mean((y-p)**2 for y,p in zip(ys,pred)), 6),
        "log_loss": round(statistics.mean(
            -y*math.log(max(p,1e-12))-(1-y)*math.log(max(1-p,1e-12))
            for y,p in zip(ys,pred)), 6),
        "direction_accuracy": round(sum((p>=.5)==bool(y)
            for p,y in zip(pred,ys))/len(ys), 6),
    }


def run(root):
    samples = records(root)
    train = [x for x in samples if x["day"] <= "2024-07-16"]
    # Jul 17-18 kept unused. Jul 19-20 have been seen in previous studies.
    check = [x for x in samples if x["day"] >= "2024-07-19"]
    hold = {name: metrics(check, train_predict(train,check,enabled))
            for name,enabled in (("baseline",False),("with_patterns",True))}
    rolling,p0,p1 = [],[],[]
    for day in DAYS[5:]:
        old = [x for x in samples if x["day"] < day]
        cur = [x for x in samples if x["day"] == day]
        rolling.extend(cur)
        p0.extend(train_predict(old,cur,False))
        p1.extend(train_predict(old,cur,True))
    f0,f1 = metrics(rolling,p0),metrics(rolling,p1)
    return {
        "scope": "EXPLORATORY_RETROSPECTIVE_11_DAYS_ONLY",
        "days": len(DAYS), "observations": len(samples),
        "pattern_features": "two fixed nondirectional counts: 9 candle flags and 18 geometric candidates",
        "model": "regularized logistic penalty=1; train-only median/MAD; no tuning or calibration",
        "n_with_candle_flags": sum(x["pattern"][0]>0 for x in samples),
        "n_with_geometric_candidates": sum(x["pattern"][1]>0 for x in samples),
        "holdout_last_2_days_PREVIOUSLY_OBSERVED": hold,
        "expanding_walkforward_last_6_days": {"baseline":f0,"with_patterns":f1},
        "brier_improvement_baseline_minus_pattern":
            round(f0["brier"]-f1["brier"],6),
        "market_orders":0,
        "notes": [
            "No genuinely untouched holdout; 11-day records were previously studied.",
            "44 correlated observations do not constitute 44 independent days.",
            "Future labels are not presented to agent features.",
            "No profitability or directional-trading edge established.",
            "The original FabioQuant 84-day protocol remains unmodified.",
        ],
    }


def main():
    ap = argparse.ArgumentParser(description="Offline historical pattern ablation")
    ap.add_argument("--data-dir", required=True, type=Path)
    args = ap.parse_args()
    print(json.dumps(run(args.data_dir), indent=2))


if __name__ == "__main__":
    main()
