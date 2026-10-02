from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math


def _load_vnstock_quote():
    from vnstock.api.quote import Quote

    return Quote


def _fetch_vnstock_close_prices(quote_class, symbol):
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=180)
    history = quote_class(symbol=symbol, source="VCI").history(
        start=start.isoformat(),
        end=end.isoformat(),
        interval="1D",
    )
    if history is None or history.empty or "close" not in history.columns:
        return []

    close_prices = []
    for price in history["close"].dropna().tolist()[-100:]:
        value = float(price)
        if math.isfinite(value):
            close_prices.append(value)
    return close_prices


def build_mock_market_data(use_vnstock=True):
    quote_class = None
    if use_vnstock:
        try:
            quote_class = _load_vnstock_quote()
        except Exception:
            quote_class = None

    symbols = [
        {"symbol": "VIC", "name": "Vingroup", "base": 56.4, "trend": 0.014, "volatility": 0.022},
        {"symbol": "FPT", "name": "FPT", "base": 88.3, "trend": 0.011, "volatility": 0.018},
        {"symbol": "HPG", "name": "Hoa Phat", "base": 24.6, "trend": 0.016, "volatility": 0.024},
        {"symbol": "MWG", "name": "Mobile World", "base": 39.7, "trend": 0.008, "volatility": 0.02},
        {"symbol": "TCB", "name": "Techcombank", "base": 27.9, "trend": 0.01, "volatility": 0.019},
        {"symbol": "BVH", "name": "Babylon Holdings", "base": 32.8, "trend": 0.012, "volatility": 0.021},
        {"symbol": "GAS", "name": "PetroVietnam Gas", "base": 61.2, "trend": 0.006, "volatility": 0.015},
        {"symbol": "STB", "name": "Sacombank", "base": 19.2, "trend": 0.009, "volatility": 0.018},
        {"symbol": "MBB", "name": "MBBank", "base": 21.5, "trend": 0.012, "volatility": 0.017},
        {"symbol": "VHM", "name": "Vinhomes", "base": 42.3, "trend": 0.009, "volatility": 0.02},
        {"symbol": "VNM", "name": "Vinamilk", "base": 74.8, "trend": 0.007, "volatility": 0.016},
        {"symbol": "CTG", "name": "Cong Ty Co Phan VietinBank", "base": 22.1, "trend": 0.008, "volatility": 0.018},
        {"symbol": "SSI", "name": "SSI Securities", "base": 18.7, "trend": 0.013, "volatility": 0.022},
        {"symbol": "PNJ", "name": "Phu Nhuan Jewelry", "base": 67.3, "trend": 0.005, "volatility": 0.014},
        {"symbol": "HDB", "name": "HDBank", "base": 26.4, "trend": 0.011, "volatility": 0.019},
    ]

    market_data = []
    for idx, stock in enumerate(symbols):
        prices = []
        current = stock["base"]
        for session in range(100):
            drift = (stock["trend"] * current) / 100
            swing = ((session % 7) - 3) * stock["volatility"] * current * 0.4
            current = max(8.0, current + drift + swing + (idx % 3) * 0.22)
            prices.append(round(current, 2))
        source = "mock"
        if quote_class is not None:
            try:
                vnstock_prices = _fetch_vnstock_close_prices(quote_class, stock["symbol"])
                if vnstock_prices:
                    prices = vnstock_prices
                    source = "vnstock"
            except Exception:
                pass
        market_data.append({
            "symbol": stock["symbol"],
            "name": stock["name"],
            "base": stock["base"],
            "close_prices": prices,
            "source": source,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
    return market_data
