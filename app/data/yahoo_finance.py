import math
import os

import yfinance


def yahoo_ticker(symbol, exchange=None):
    symbol = str(symbol).strip().upper()
    if "." in symbol or symbol.startswith("^"):
        return symbol

    exchange = str(exchange or "").strip().upper()
    exchange_setting = f"YAHOO_{exchange}_SUFFIX" if exchange in {"HOSE", "HNX"} else ""
    suffix = os.getenv(exchange_setting, os.getenv("YAHOO_TICKER_SUFFIX", "VN"))
    suffix = suffix.strip().lstrip(".")
    return f"{symbol}.{suffix}" if suffix else symbol


def fetch_daily_history(ticker, timeout=10):
    history = yfinance.Ticker(ticker).history(
        period="6mo",
        interval="1d",
        auto_adjust=True,
        timeout=timeout,
    )
    if history is None or history.empty or "Close" not in history.columns:
        return {"close_prices": [], "volumes": [], "candles": []}

    prices = []
    volumes = []
    candles = []
    for _, row in history.tail(100).iterrows():
        try:
            price = float(row["Close"])
        except (TypeError, ValueError):
            continue
        if math.isfinite(price) and price > 0:
            prices.append(price)
            try:
                volume = float(row["Volume"])
            except (KeyError, TypeError, ValueError):
                volume = None
            volume = volume if volume is not None and math.isfinite(volume) and volume >= 0 else None
            volumes.append(volume)
            candle = {"close": price, "volume": volume}
            for source, target in (("Open", "open"), ("High", "high"), ("Low", "low")):
                try:
                    value = float(row[source])
                except (KeyError, TypeError, ValueError):
                    value = None
                candle[target] = value if value is not None and math.isfinite(value) else None
            candles.append(candle)
    return {"close_prices": prices, "volumes": volumes, "candles": candles}


def fetch_daily_close_prices(ticker, timeout=10):
    return fetch_daily_history(ticker, timeout=timeout)["close_prices"]