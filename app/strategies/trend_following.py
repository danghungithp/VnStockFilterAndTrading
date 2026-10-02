def evaluate_trend_signal(prices):
    if not prices:
        return {"signal": "Neutral", "momentum": 0.0, "score": 0.0}

    first_price = prices[0]
    last_price = prices[-1]
    momentum = ((last_price - first_price) / first_price) * 100

    if momentum >= 5:
        signal = "Bullish"
    elif momentum <= -3:
        signal = "Bearish"
    else:
        signal = "Neutral"

    return {
        "signal": signal,
        "momentum": round(momentum, 2),
        "score": round(momentum * 1.4, 2),
        "last_price": round(last_price, 2),
    }
