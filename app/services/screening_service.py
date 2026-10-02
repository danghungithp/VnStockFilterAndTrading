import os
import json
import sqlite3
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from app.data.market_cache import load_market_cache, save_market_cache
import app.data.mock_market_data as mock_market_data
from app.data.vietcap_listing import (
    fetch_vietnam_listings,
    fetch_vietcap_group,
    fetch_vietcap_index_history,
)
from app.data.yahoo_finance import fetch_daily_history, yahoo_ticker
from app.strategies.chart_patterns import analyze_chart_patterns
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
_YAHOO_CACHE_TTL_SECONDS = 21600
_UNIVERSE_CACHE_TTL_SECONDS = 86400
_INDEX_CACHE_TTL_SECONDS = 21600
_MARKET_CACHE_VERSION = 4
_MIN_KELLY_RETURNS = 20
_MIN_KELLY_OUTCOMES = 5
_MAX_POSITION_ALLOCATION_PERCENT = 20
_market_data_cache = None
_market_data_cache_at = 0.0
_market_universe_count = 0
_market_data_source = "unavailable"
_market_data_error = None
_market_data_cache_key = None
_market_data_cache_status = "unavailable"
_market_data_updated_at = None
_market_data_cache_lock = threading.Lock()
_vietcap_listing_cache = None
_vietcap_listing_cache_at = 0.0
_vietcap_listing_cache_lock = threading.Lock()


def _fetch_vietcap_listing(force_refresh=False):
    global _vietcap_listing_cache, _vietcap_listing_cache_at
    ttl_seconds = int(os.getenv("MARKET_UNIVERSE_CACHE_TTL", _UNIVERSE_CACHE_TTL_SECONDS))
    if (
        not force_refresh
        and _vietcap_listing_cache is not None
        and time.monotonic() - _vietcap_listing_cache_at < ttl_seconds
    ):
        return _vietcap_listing_cache

    with _vietcap_listing_cache_lock:
        if (
            not force_refresh
            and _vietcap_listing_cache is not None
            and time.monotonic() - _vietcap_listing_cache_at < ttl_seconds
        ):
            return _vietcap_listing_cache
        _vietcap_listing_cache = fetch_vietnam_listings(
            timeout=float(os.getenv("LISTING_TIMEOUT", "10"))
        )
        _vietcap_listing_cache_at = time.monotonic()
        return _vietcap_listing_cache


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

    normalized = []
    seen = set()
    for item in records:
        if not isinstance(item, dict):
            continue
        exchange = str(item.get("exchange", "")).strip().upper()
        if exchange not in {"HSX", "HOSE", "HNX"}:
            continue
        if item.get("type") and str(item["type"]).upper() != "STOCK":
            continue
        symbol = str(item.get("symbol", "")).strip().upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        normalized.append(
            {
                "symbol": symbol,
                "name": item.get("organ_name") or item.get("organ_short_name") or symbol,
                "exchange": "HOSE" if exchange in {"HSX", "HOSE"} else "HNX",
            }
        )
    return normalized


def _universes_from_cache_rows(rows):
    universes = {"HOSE": [], "HNX": [], "VN30": []}
    for row in rows:
        name = row.get("universe")
        if name in universes:
            universes[name].append(
                {key: value for key, value in row.items() if key != "universe"}
            )
    return universes


def get_stock_universes(force_refresh=False):
    cache_key = f"v{_MARKET_CACHE_VERSION}:vietcap-stock-universes"
    ttl_seconds = int(os.getenv("MARKET_UNIVERSE_CACHE_TTL", _UNIVERSE_CACHE_TTL_SECONDS))
    disk_cache = load_market_cache(cache_key)
    if not force_refresh and disk_cache:
        age = max(0, time.time() - disk_cache["fetched_at"])
        if age < ttl_seconds:
            return {
                "universes": _universes_from_cache_rows(disk_cache["rows"]),
                "source": "vietcap",
                "cache_status": "disk",
                "data_updated_at": disk_cache["fetched_at"],
                "data_status": None,
            }

    listing_error = None
    try:
        stocks = _normalize_market_symbols(_fetch_vietcap_listing(force_refresh=force_refresh))
        stocks_by_symbol = {stock["symbol"]: stock for stock in stocks}
        try:
            vn30_symbols = fetch_vietcap_group(
                "VN30", timeout=float(os.getenv("LISTING_TIMEOUT", "10"))
            )
            vn30 = [
                stocks_by_symbol.get(
                    item["symbol"],
                    {"symbol": item["symbol"], "name": item["symbol"], "exchange": "HOSE"},
                )
                for item in vn30_symbols
            ]
        except Exception:
            vn30 = []
            listing_error = "Không tải được thành phần VN30 từ Vietcap."

        universes = {
            "HOSE": [stock for stock in stocks if stock["exchange"] == "HOSE"],
            "HNX": [stock for stock in stocks if stock["exchange"] == "HNX"],
            "VN30": vn30,
        }
        cache_rows = [
            {**stock, "universe": name}
            for name, members in universes.items()
            for stock in members
        ]
        fetched_at = time.time()
        save_market_cache(cache_key, cache_rows, "vietcap", len(stocks), fetched_at)
        return {
            "universes": universes,
            "source": "vietcap",
            "cache_status": "live",
            "data_updated_at": fetched_at,
            "data_status": listing_error,
        }
    except Exception as exc:
        if disk_cache:
            return {
                "universes": _universes_from_cache_rows(disk_cache["rows"]),
                "source": "vietcap",
                "cache_status": "stale",
                "data_updated_at": disk_cache["fetched_at"],
                "data_status": f"Không làm mới được danh sách Vietcap: {exc}",
            }
        return {
            "universes": {"HOSE": [], "HNX": [], "VN30": []},
            "source": "unavailable",
            "cache_status": "unavailable",
            "data_updated_at": None,
            "data_status": f"Không tải được danh sách cổ phiếu Vietcap: {exc}",
        }


def _fetch_yahoo_history(stock):
    ticker = yahoo_ticker(stock["symbol"], stock.get("exchange"))
    try:
        history = fetch_daily_history(
            ticker,
            timeout=float(os.getenv("YAHOO_TIMEOUT", "10")),
        )
    except Exception:
        return None
    if not history["close_prices"]:
        return None
    return {**stock, **history, "source": "yahoo", "provider_symbol": ticker}


def _fetch_yahoo_market_data(requested_symbols=None):
    try:
        symbols = _normalize_market_symbols(_fetch_vietcap_listing())
    except Exception:
        return [], 0
    if not symbols:
        return [], 0

    universe_count = len(symbols)
    configured_symbols = os.getenv(
        "YAHOO_SYMBOLS", os.getenv("ALPHA_VANTAGE_SYMBOLS", "")
    ).strip()
    if requested_symbols:
        requested = {symbol.strip().upper() for symbol in requested_symbols}
        symbols = [item for item in symbols if item["symbol"] in requested]
    elif configured_symbols:
        configured = {symbol.strip().upper() for symbol in configured_symbols.split(",") if symbol.strip()}
        symbols = [item for item in symbols if item["symbol"] in configured]
    max_symbols = max(
        1,
        int(os.getenv("YAHOO_MAX_SYMBOLS", os.getenv("ALPHA_VANTAGE_MAX_SYMBOLS", "5"))),
    )
    symbols = symbols[:max_symbols]
    if not symbols:
        return [], universe_count

    max_workers = max(1, min(int(os.getenv("YAHOO_MAX_WORKERS", "5")), len(symbols)))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(
            executor.map(
                _fetch_yahoo_history,
                symbols,
            )
        )
    return [row for row in results if row], universe_count


def _calculate_risk_metrics(prices):
    valid_prices = []
    for price in prices:
        try:
            value = float(price)
        except (TypeError, ValueError):
            continue
        if value > 0 and value < float("inf"):
            valid_prices.append(value)

    returns = [
        (current - previous) / previous
        for previous, current in zip(valid_prices, valid_prices[1:])
    ]
    metrics = {
        "win_probability_percent": None,
        "payoff_ratio": None,
        "daily_volatility_percent": None,
        "kelly_allocation_percent": 0.0,
        "stop_loss_price": None,
        "take_profit_price": None,
    }
    if len(returns) < _MIN_KELLY_RETURNS:
        return metrics

    daily_volatility = statistics.stdev(returns)
    entry_price = valid_prices[-1]
    risk_per_share = entry_price * 2 * daily_volatility
    if risk_per_share > 0:
        metrics["stop_loss_price"] = round(max(0, entry_price - risk_per_share), 2)
        metrics["take_profit_price"] = round(entry_price + 2 * risk_per_share, 2)
    metrics["daily_volatility_percent"] = round(daily_volatility * 100, 2)

    winning_returns = [daily_return for daily_return in returns if daily_return > 0]
    losing_returns = [abs(daily_return) for daily_return in returns if daily_return < 0]
    if len(winning_returns) < _MIN_KELLY_OUTCOMES or len(losing_returns) < _MIN_KELLY_OUTCOMES:
        return metrics

    win_probability = len(winning_returns) / (len(winning_returns) + len(losing_returns))
    average_win = statistics.mean(winning_returns)
    average_loss = statistics.mean(losing_returns)
    payoff_ratio = average_win / average_loss if average_loss else 0
    kelly_fraction = win_probability - (1 - win_probability) / payoff_ratio if payoff_ratio else 0
    half_kelly_percent = max(0, kelly_fraction) * 50

    metrics.update(
        {
            "win_probability_percent": round(win_probability * 100, 2),
            "payoff_ratio": round(payoff_ratio, 2),
            "kelly_allocation_percent": round(
                min(half_kelly_percent, _MAX_POSITION_ALLOCATION_PERCENT), 2
            ),
        }
    )
    return metrics


def _market_cache_key(provider, requested_symbols=None):
    settings = {
        name: os.getenv(name, "")
        for name in (
            "YAHOO_SYMBOLS",
            "ALPHA_VANTAGE_SYMBOLS",
            "YAHOO_MAX_SYMBOLS",
            "ALPHA_VANTAGE_MAX_SYMBOLS",
            "YAHOO_TICKER_SUFFIX",
            "YAHOO_HOSE_SUFFIX",
            "YAHOO_HNX_SUFFIX",
        )
    }
    selected = ",".join(requested_symbols or ())
    return f"v{_MARKET_CACHE_VERSION}:{provider}:{selected}:{json.dumps(settings, sort_keys=True)}"


def get_market_data(force_refresh=False, symbols=None):
    global _market_data_cache, _market_data_cache_at, _market_universe_count
    global _market_data_source, _market_data_error
    global _market_data_cache_key, _market_data_cache_status, _market_data_updated_at
    provider = os.getenv("MARKET_DATA_PROVIDER", "yahoo").lower()
    if provider == "alphavantage":
        provider = "yahoo"
    default_ttl = (
        _YAHOO_CACHE_TTL_SECONDS if provider == "yahoo" else _CACHE_TTL_SECONDS
    )
    ttl_seconds = int(os.getenv("MARKET_DATA_CACHE_TTL", default_ttl))
    requested_symbols = tuple(sorted({str(symbol).strip().upper() for symbol in symbols or () if str(symbol).strip()}))
    cache_key = _market_cache_key(provider, requested_symbols)
    now = time.monotonic()
    if (
        not force_refresh
        and _market_data_cache is not None
        and _market_data_cache_key == cache_key
        and now - _market_data_cache_at < ttl_seconds
    ):
        return _market_data_cache

    disk_cache = load_market_cache(cache_key)
    if not force_refresh and disk_cache:
        age = max(0, time.time() - disk_cache["fetched_at"])
        if age < ttl_seconds:
            with _market_data_cache_lock:
                _market_data_cache = disk_cache["rows"]
                _market_data_cache_at = time.monotonic() - age
                _market_data_cache_key = cache_key
                _market_data_cache_status = "disk"
                _market_data_updated_at = disk_cache["fetched_at"]
                _market_data_source = disk_cache["source"]
                _market_universe_count = disk_cache["universe_count"]
                _market_data_error = None
                return _market_data_cache

    with _market_data_cache_lock:
        now = time.monotonic()
        if (
            not force_refresh
            and _market_data_cache is not None
            and _market_data_cache_key == cache_key
            and now - _market_data_cache_at < ttl_seconds
        ):
            return _market_data_cache

        if provider == "mock":
            market_rows = mock_market_data.build_mock_market_data()
            if requested_symbols:
                requested = set(requested_symbols)
                market_rows = [row for row in market_rows if row["symbol"] in requested]
            _market_universe_count = len(market_rows)
            _market_data_source = "mock"
            _market_data_error = None
            cache_status = "demo"
        else:
            if provider == "yahoo":
                if requested_symbols:
                    market_rows, _market_universe_count = _fetch_yahoo_market_data(requested_symbols)
                else:
                    market_rows, _market_universe_count = _fetch_yahoo_market_data()
                _market_data_source = "yahoo" if market_rows else "unavailable"
                _market_data_error = (
                    None
                    if market_rows
                    else (
                        f"Không có giá Yahoo cho {', '.join(requested_symbols)}. Kiểm tra mã HOSE/HNX và độ phủ Yahoo."
                        if requested_symbols
                        else "Không nhận được giá mới từ Yahoo Finance. Kiểm tra độ phủ mã Yahoo (.VN), kết nối mạng và danh sách Vnstock."
                    )
                )
                cache_status = "live" if market_rows else "unavailable"
            else:
                market_rows = []
                _market_universe_count = 0
                _market_data_source = "unavailable"
                _market_data_error = "MARKET_DATA_PROVIDER không được hỗ trợ."
                cache_status = "unavailable"

        fetched_at = time.time()
        if market_rows:
            try:
                save_market_cache(
                    cache_key,
                    market_rows,
                    _market_data_source,
                    _market_universe_count,
                    fetched_at,
                )
            except (OSError, ValueError, sqlite3.Error):
                pass
            _market_data_cache_status = cache_status
            _market_data_updated_at = fetched_at
        elif disk_cache:
            market_rows = disk_cache["rows"]
            _market_universe_count = disk_cache["universe_count"]
            _market_data_source = disk_cache["source"]
            _market_data_cache_status = "stale"
            _market_data_updated_at = disk_cache["fetched_at"]
        else:
            _market_data_cache_status = "unavailable"
            _market_data_updated_at = None
        _market_data_cache = market_rows
        _market_data_cache_at = time.monotonic()
        _market_data_cache_key = cache_key
        return market_rows


def refresh_market_data(symbols=None):
    return get_market_data(force_refresh=True, symbols=symbols)


def _evaluate_stock(item):
    trend = evaluate_trend_signal(item["close_prices"])
    mean_reversion = evaluate_mean_reversion_signal(item["close_prices"])
    chart_patterns = analyze_chart_patterns(
        item["close_prices"], item.get("volumes"), item.get("candles")
    )
    score = (SCORES[trend["signal"]] + SCORES[mean_reversion["signal"]]) / 2
    recommendation = "Buy" if score >= 0.5 else "Sell" if score <= -0.5 else "Watch"
    risk_metrics = _calculate_risk_metrics(item["close_prices"])
    allocation = (
        risk_metrics["kelly_allocation_percent"] if recommendation == "Buy" else 0
    )

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
        "chart_patterns": chart_patterns,
        "last_price": trend.get("last_price", 0),
        "recommendation": recommendation,
        "score": score,
        "allocation_percent": allocation,
        **risk_metrics,
        "trend_reason": trend_reason,
        "mean_reversion_reason": mean_reversion_reason,
        "reason": reason,
        "criteria": [
            "Xu hướng: biến động từ phiên cũ nhất đến mới nhất; Bullish >= 5%, Bearish <= -3%.",
            "Mean Reversion: so sánh trung bình 5 phiên gần nhất với lịch sử trước đó; Oversold <= -4%, Extended >= 4%.",
            "Giải ngân: ½ Kelly từ tỷ lệ phiên tăng và payoff ratio lịch sử; cần tối thiểu 20 phiên, ít nhất 5 phiên tăng và 5 phiên giảm; tối đa 20% mỗi mã và chỉ áp dụng cho Top 5 mã mua.",
            "Cắt lỗ tham khảo: 2 độ lệch chuẩn ngày dưới giá đóng cửa gần nhất; chốt lời tại 2R. Đây là quy tắc biến động của ứng dụng, không phải mức giá do Edward Thorp quy định.",
            "Mô hình kỹ thuật: cốc tay cầm và Sao Mai cần volume >= 1.5x trung bình 20 phiên; hai đáy/hai đỉnh, vai đầu vai và vai đầu vai ngược chờ xác nhận neckline/volume.",
        ],
    }


def get_market_indices(force_refresh=False):
    cache_key = f"v{_MARKET_CACHE_VERSION}:vietcap-market-indices"
    ttl_seconds = int(os.getenv("MARKET_INDEX_CACHE_TTL", _INDEX_CACHE_TTL_SECONDS))
    disk_cache = load_market_cache(cache_key)
    cache_status = "live"
    data_status = None
    updated_at = None

    if not force_refresh and disk_cache:
        age = max(0, time.time() - disk_cache["fetched_at"])
        if age < ttl_seconds:
            raw_indices = disk_cache["rows"]
            cache_status = "disk"
            updated_at = disk_cache["fetched_at"]
        else:
            raw_indices = None
    else:
        raw_indices = None

    if raw_indices is None:
        def fetch_index(symbol):
            try:
                history = fetch_vietcap_index_history(
                    symbol,
                    count=100,
                    timeout=float(os.getenv("MARKET_INDEX_TIMEOUT", "15")),
                )
            except Exception:
                return None
            if not history["close_prices"]:
                return None
            return {
                "symbol": symbol,
                "name": "VN-Index" if symbol == "VNINDEX" else "VN30 Index",
                "exchange": "INDEX",
                **history,
                "source": "vietcap",
            }

        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                fetched = list(executor.map(fetch_index, ("VNINDEX", "VN30")))
            raw_indices = [item for item in fetched if item]
            if len(raw_indices) != 2:
                data_status = "Một hoặc nhiều chỉ số chưa có dữ liệu OHLCV từ Vietcap."
        except Exception as exc:
            raw_indices = []
            data_status = f"Không tải được dữ liệu chỉ số từ Vietcap: {exc}"

        updated_at = time.time() if raw_indices else None
        if raw_indices:
            try:
                save_market_cache(cache_key, raw_indices, "vietcap", len(raw_indices), updated_at)
            except (OSError, ValueError, sqlite3.Error):
                pass
        elif disk_cache:
            raw_indices = disk_cache["rows"]
            updated_at = disk_cache["fetched_at"]
            cache_status = "stale"
            data_status = data_status or "Vietcap chưa phản hồi; đang dùng cache chỉ số cũ."
        else:
            cache_status = "unavailable"
            data_status = data_status or "Chưa có dữ liệu chỉ số từ Vietcap."

    indices = []
    for item in raw_indices or []:
        analysis = _evaluate_stock(item)
        indices.append(
            {
                "symbol": item["symbol"],
                "name": item["name"],
                "last_price": analysis["last_price"],
                "volume": item.get("volumes", [None])[-1] if item.get("volumes") else None,
                "trend_signal": analysis["trend_signal"],
                "trend_momentum": analysis["trend_momentum"],
                "mean_reversion_signal": analysis["mean_reversion_signal"],
                "mean_reversion_momentum": analysis["mean_reversion_momentum"],
                "recommendation": analysis["recommendation"],
                "chart_patterns": analysis["chart_patterns"],
                "source": "vietcap",
            }
        )

    return {
        "indices": indices,
        "source": "vietcap" if indices else "unavailable",
        "cache_status": cache_status,
        "data_updated_at": updated_at,
        "data_status": data_status,
    }


def _evaluate_market(market_data):
    rows = [_evaluate_stock(item) for item in market_data]
    buy_candidates = sorted(
        (
            row
            for row in rows
            if row["recommendation"] == "Buy" and row["kelly_allocation_percent"] > 0
        ),
        key=lambda row: (row["score"], row["trend_momentum"]),
        reverse=True,
    )[:5]
    allocated_symbols = {row["symbol"] for row in buy_candidates}

    for row in rows:
        if row["symbol"] not in allocated_symbols:
            row["allocation_percent"] = 0
            if row["recommendation"] != "Buy":
                row["allocation_reason"] = "Chưa đủ đồng thuận để giải ngân."
            elif row["kelly_allocation_percent"] <= 0:
                row["allocation_reason"] = "½ Kelly không có edge dương hoặc chưa đủ mẫu lịch sử."
            else:
                row["allocation_reason"] = "Ngoài Top 5 mã mua được xếp hạng."
        else:
            row["allocation_reason"] = "Tỷ trọng theo ½ Kelly, sau giới hạn rủi ro của danh mục."
    return rows


def get_screening_summary(symbols=None):
    market_data = get_market_data(symbols=symbols)
    stock_universes = get_stock_universes()
    market_indices = get_market_indices()
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
        else "mixed" if data_sources else _market_data_source
    )

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data_updated_at": (
            datetime.fromtimestamp(_market_data_updated_at, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            if _market_data_updated_at
            else None
        ),
        "source": source,
        "data_status": _market_data_error,
        "cache_status": _market_data_cache_status,
        "cache_age_seconds": (
            max(0, int(time.time() - _market_data_updated_at))
            if _market_data_updated_at
            else None
        ),
        "exchanges": sorted({item["exchange"] for item in market_data if item.get("exchange")}),
        "universe_count": _market_universe_count,
        "priced_count": len(rows),
        "symbols": [row["symbol"] for row in rows],
        "strategy_summary": strategy_summary,
        "total_positions": len(rows),
        "stocks": rows,
        "stock_universes": stock_universes["universes"],
        "universe_source": stock_universes["source"],
        "universe_cache_status": stock_universes["cache_status"],
        "universe_data_status": stock_universes["data_status"],
        "market_indices": market_indices["indices"],
        "index_source": market_indices["source"],
        "index_cache_status": market_indices["cache_status"],
        "index_data_updated_at": market_indices["data_updated_at"],
        "index_data_status": market_indices["data_status"],
    }


def get_recommendations(symbols=None):
    stock_rows = _evaluate_market(get_market_data(symbols=symbols))
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
