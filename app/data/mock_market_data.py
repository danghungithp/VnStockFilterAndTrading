from __future__ import annotations

from datetime import datetime, timezone


def build_mock_market_data():
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
        market_data.append({
            "symbol": stock["symbol"],
            "name": stock["name"],
            "base": stock["base"],
            "close_prices": prices,
            "source": "mock",
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
    return market_data
