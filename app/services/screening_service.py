import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import app.data.mock_market_data as mock_market_data
from app.strategies.mean_reversion import evaluate_mean_reversion_signal
from app.strategies.trend_following import evaluate_trend_signal


SCORES = {
    "Bullish": 1,
    "Oversold": 1,
    "Neutral": 0,
    "Bearish": -1,
    "Extended": -1,
}

_CACHE_TTL_SECONDS = 900
_market_data_cache = None
_market_data_cache_at = 0.0
_market_universe_count = 0
_market_data_cache_lock = threading.Lock()


def _fetch_vnstock_listing():
    from vnstock import Listing

    return Listing(source="VCI", show_log=False).symbols_by_exchange()


def _normalize_market_symbols(listing):
    if hasattr(listing, "to_dict"):
        records = listing.to_dict("records")
    elif isinstance(listing, dict):
        records = [
            {"symbol": symbol, "exchange": exchange}
            for exchange, symbols in listing.items()
            for symbol in symbols
        ]
    else:
        records = listing or []

    symbols = []
    seen = set()
    for item in records:
        if not isinstance(item, dict):
            continue
        exchange = str(item.get("exchange", "")).upper()
        if exchange not in {"HSX", "HOSE", "HNX"}:
            continue
        if item.get("type") and str(item["type"]).upper() != "STOCK":
            continue
        symbol = str(item.get("symbol", "")).strip().upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        symbols.append(
            {
                "symbol": symbol,
                "name": item.get("organ_name") or item.get("organ_short_name") or symbol,
                "exchange": "HOSE" if exchange in {"HSX", "HOSE"} else "HNX",
            }
        )
    return symbols


def _fetch_vnstock_history(stock):
    try:
        quote_class = mock_market_data._load_vnstock_quote()
        prices = mock_market_data._fetch_vnstock_close_prices(quote_class, stock["symbol"])
    except Exception:
        return None
    if not prices:
        return None
    return {**stock, "close_prices": prices, "source": "vnstock"}


def _fetch_vnstock_market_data():
    try:
        symbols = _normalize_market_symbols(_fetch_vnstock_listing())
    except Exception:
        return [], 0

    if not symbols:
        return [], 0

    with ThreadPoolExecutor(max_workers=min(8, len(symbols))) as executor:
        results = list(executor.map(_fetch_vnstock_history, symbols))
    return [row for row in results if row], len(symbols)


def get_market_data():
    global _market_data_cache, _market_data_cache_at, _market_universe_count
    ttl_seconds = int(os.getenv("MARKET_DATA_CACHE_TTL", _CACHE_TTL_SECONDS))
    now = time.monotonic()
    if _market_data_cache is not None and now - _market_data_cache_at < ttl_seconds:
        return _market_data_cache

    with _market_data_cache_lock:
        now = time.monotonic()
        if _market_data_cache is not None and now - _market_data_cache_at < ttl_seconds:
            return _market_data_cache

        if os.getenv("MARKET_DATA_PROVIDER", "vnstock").lower() == "mock":
            market_rows = mock_market_data.build_mock_market_data(use_vnstock=False)
            _market_universe_count = len(market_rows)
        else:
            market_rows, _market_universe_count = _fetch_vnstock_market_data()
            if not market_rows:
                market_rows = mock_market_data.build_mock_market_data(use_vnstock=False)
                _market_universe_count = len(market_rows)

        _market_data_cache = market_rows
        _market_data_cache_at = time.monotonic()
        return market_rows


def _evaluate_stock(item):
    trend = evaluate_trend_signal(item["close_prices"])
    mean_reversion = evaluate_mean_reversion_signal(item["close_prices"])
    score = (SCORES[trend["signal"]] + SCORES[mean_reversion["signal"]]) / 2
    recommendation = "Buy" if score >= 0.5 else "Sell" if score <= -0.5 else "Watch"
    allocation = 20 if score == 1 else 10 if score == 0.5 else 0

    trend_reason = {
        "Bullish": f"Giá tăng {trend['momentum']}%, đạt ngưỡng xu hướng từ 5%.",
        "Bearish": f"Giá giảm {trend['momentum']}%, chạm ngưỡng xu hướng từ -3%.",
        "Neutral": f"Biến động giá {trend['momentum']}%, chưa đạt ngưỡng tăng 5% hoặc giảm 3%.",
    }[trend["signal"]]
    mean_reversion_reason = {
        "Oversold": f"Độ lệch ngắn hạn {mean_reversion['momentum']}%, thuộc vùng quá bán.",
        "Extended": f"Độ lệch ngắn hạn {mean_reversion['momentum']}%, thuộc vùng tăng nóng.",
        "Neutral": f"Độ lệch ngắn hạn {mean_reversion['momentum']}%, chưa vào vùng quá bán hoặc tăng nóng.",
    }[mean_reversion["signal"]]

    if recommendation == "Buy":
        reason = f"Tín hiệu ủng hộ mua: {trend_reason} {mean_reversion_reason}"
    elif recommendation == "Sell":
        reason = f"Tín hiệu rủi ro: {trend_reason} {mean_reversion_reason}"
    else:
        reason = f"Chưa đồng thuận để giải ngân: {trend_reason} {mean_reversion_reason}"

    return {
        **item,
        "trend_signal": trend["signal"],
        "trend_momentum": trend["momentum"],
        "mean_reversion_signal": mean_reversion["signal"],
        "mean_reversion_momentum": mean_reversion["momentum"],
        "last_price": trend.get("last_price", 0),
        "recommendation": recommendation,
        "score": score,
        "allocation_percent": allocation,
        "trend_reason": trend_reason,
        "mean_reversion_reason": mean_reversion_reason,
        "reason": reason,
        "criteria": [
            "Xu hướng: biến động từ phiên cũ nhất đến mới nhất; Bullish >= 5%, Bearish <= -3%.",
            "Mean Reversion: so sánh trung bình 5 phiên gần nhất với lịch sử trước đó; Oversold <= -4%, Extended >= 4%.",
            "Giải ngân: tối đa 20% khi cả hai chiến lược tích cực, 10% khi một chiến lược tích cực và chiến lược còn lại trung tính; chỉ áp dụng cho Top 5 mã mua, tổng tối đa 100%.",
        ],
    }


def _evaluate_market(market_data):
    rows = [_evaluate_stock(item) for item in market_data]
    buy_candidates = sorted(
        (row for row in rows if row["score"] > 0),
        key=lambda row: (row["score"], row["trend_momentum"]),
        reverse=True,
    )[:5]
    allocated_symbols = {row["symbol"] for row in buy_candidates}

    for row in rows:
        if row["symbol"] not in allocated_symbols:
            row["allocation_percent"] = 0
            if row["score"] > 0:
                row["allocation_reason"] = "Ngoài Top 5 mã mua được xếp hạng."
        else:
            row["allocation_reason"] = "Tỷ trọng theo mức đồng thuận của hai chiến lược."
    return rows


def get_screening_summary():
    market_data = get_market_data()
    rows = []
    strategy_summary = {
        "trend_following": {"bullish": 0, "neutral": 0, "bearish": 0},
        "mean_reversion": {"oversold": 0, "neutral": 0, "extended": 0},
    }

    for row in _evaluate_market(market_data):
        strategy_summary["trend_following"]["bullish" if row["trend_signal"] == "Bullish" else "neutral" if row["trend_signal"] == "Neutral" else "bearish"] += 1
        strategy_summary["mean_reversion"]["oversold" if row["mean_reversion_signal"] == "Oversold" else "neutral" if row["mean_reversion_signal"] == "Neutral" else "extended"] += 1
        rows.append(row)

    data_sources = {item.get("source", "mock") for item in market_data}
    source = (
        next(iter(data_sources))
        if len(data_sources) == 1
        else "mixed" if data_sources else "mock"
    )

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": source,
        "exchanges": ["HOSE", "HNX"] if source == "vnstock" else [],
        "universe_count": _market_universe_count,
        "priced_count": len(rows),
        "symbols": [row["symbol"] for row in rows],
        "strategy_summary": strategy_summary,
        "total_positions": len(rows),
        "stocks": rows,
    }


def get_recommendations():
    stock_rows = _evaluate_market(get_market_data())
    ranked = sorted(
        stock_rows,
        key=lambda entry: (entry["score"], entry["trend_momentum"]),
        reverse=True,
    )[:5]
    for idx, entry in enumerate(ranked, start=1):
        entry["rank"] = idx
        entry["thesis"] = entry["reason"]

    return {
        "recommendations": ranked,
        "fixed_allocation": 20.0,
    }


def get_strategy_rows(strategy):
    market_data = get_market_data()
    rows = []
    for item in market_data:
        evaluated = _evaluate_stock(item)
        if strategy == "trend_following":
            rows.append(
                {
                    "symbol": item["symbol"],
                    "name": item["name"],
                    "exchange": item.get("exchange", ""),
                    "strategy": "Trend Following",
                    "signal": evaluated["trend_signal"],
                    "momentum": evaluated["trend_momentum"],
                    "recommendation": evaluated["recommendation"],
                    "allocation_percent": evaluated["allocation_percent"],
                    "reason": evaluated["reason"],
                    "status": "Strong" if evaluated["trend_signal"] == "Bullish" else "Watch" if evaluated["trend_signal"] == "Neutral" else "Monitor",
                }
            )
        elif strategy == "mean_reversion":
            rows.append(
                {
                    "symbol": item["symbol"],
                    "name": item["name"],
                    "exchange": item.get("exchange", ""),
                    "strategy": "Mean Reversion",
                    "signal": evaluated["mean_reversion_signal"],
                    "momentum": evaluated["mean_reversion_momentum"],
                    "recommendation": evaluated["recommendation"],
                    "allocation_percent": evaluated["allocation_percent"],
                    "reason": evaluated["reason"],
                    "status": "Candidate" if evaluated["mean_reversion_signal"] == "Oversold" else "Monitor" if evaluated["mean_reversion_signal"] == "Neutral" else "Watch",
                }
            )
    return rows
