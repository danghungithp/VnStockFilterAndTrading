def evaluate_mean_reversion_signal(prices):
    if not prices:
        return {"signal": "Neutral", "momentum": 0.0, "score": 0.0}

    first_price = prices[0]
    last_price = prices[-1]
    momentum = ((last_price - first_price) / first_price) * 100

    if len(prices) <= 5 and momentum <= -7:
        signal = "Oversold"
    else:
        recent = prices[-5:]
        baseline = prices[:-5] if len(prices) > 5 else prices
        recent_average = sum(recent) / len(recent)
        baseline_average = sum(baseline) / len(baseline)
        momentum = ((recent_average - baseline_average) / baseline_average) * 100

        if momentum <= -4:
            signal = "Oversold"
        elif momentum >= 4:
            signal = "Extended"
        else:
            signal = "Neutral"

    return {
        "signal": signal,
        "momentum": round(momentum, 2),
        "score": round(momentum * 1.1, 2),
        "last_price": round(prices[-1], 2),
    }
