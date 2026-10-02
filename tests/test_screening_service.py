import pandas as pd
from pathlib import Path

import app.data.market_cache as market_cache
import app.data.yahoo_finance as yahoo_finance
import app.data.mock_market_data as mock_market_data
import app.services.screening_service as screening_service
from app.data.mock_market_data import build_mock_market_data
from app.services.screening_service import get_market_data, get_screening_summary


def _known_return_series():
    prices = [100.0]
    for index in range(100):
        daily_return = 0.01 if index < 55 else -0.01
        prices.append(prices[-1] * (1 + daily_return))
    return prices


def _stub_market_data_providers(monkeypatch):
    monkeypatch.setenv("MARKET_DATA_PROVIDER", "mock")
    monkeypatch.setattr(screening_service, "_fetch_yahoo_market_data", lambda: ([], 0))
    monkeypatch.setattr(screening_service, "_market_data_cache", None)


def test_market_data_provider_returns_rows(monkeypatch):
    _stub_market_data_providers(monkeypatch)
    market_data = get_market_data()
    assert len(market_data) >= 1
    first_row = market_data[0]
    assert "symbol" in first_row
    assert "close_prices" in first_row


def test_screening_summary_has_expected_shape(monkeypatch):
    _stub_market_data_providers(monkeypatch)
    summary = get_screening_summary()
    assert "generated_at" in summary
    assert len(summary["symbols"]) >= 10
    assert len(summary["strategy_summary"]) == 2
    assert summary["total_positions"] >= 5


def test_yahoo_daily_history_is_read_from_adjusted_close(monkeypatch):
    class Ticker:
        def __init__(self, symbol):
            assert symbol == "FPT.VN"

        def history(self, **kwargs):
            assert kwargs["period"] == "6mo"
            assert kwargs["interval"] == "1d"
            assert kwargs["auto_adjust"] is True
            assert kwargs["timeout"] == 8
            return pd.DataFrame({"Close": [10.0, 11.0, 12.0]})

    monkeypatch.setattr(yahoo_finance.yfinance, "Ticker", Ticker)
    assert yahoo_finance.fetch_daily_close_prices("FPT.VN", timeout=8) == [10.0, 11.0, 12.0]


def test_yahoo_history_keeps_close_and_volume_aligned(monkeypatch):
    class Ticker:
        def history(self, **kwargs):
            return pd.DataFrame(
                {
                    "Open": [9.0, 10.0],
                    "High": [11.0, 12.0],
                    "Low": [8.0, 9.0],
                    "Close": [10.0, 11.0],
                    "Volume": [1000, 1500],
                }
            )

    monkeypatch.setattr(yahoo_finance.yfinance, "Ticker", lambda symbol: Ticker())

    history = yahoo_finance.fetch_daily_history("FPT.VN")

    assert history == {
        "close_prices": [10.0, 11.0],
        "volumes": [1000.0, 1500.0],
        "candles": [
            {"open": 9.0, "high": 11.0, "low": 8.0, "close": 10.0, "volume": 1000.0},
            {"open": 10.0, "high": 12.0, "low": 9.0, "close": 11.0, "volume": 1500.0},
        ],
    }


def test_legacy_alpha_vantage_setting_uses_yahoo_provider(monkeypatch):
    market_data = [{"symbol": "FPT", "name": "FPT", "close_prices": [10, 11], "source": "yahoo"}]
    monkeypatch.setenv("MARKET_DATA_PROVIDER", "alphavantage")
    monkeypatch.setenv("MARKET_DATA_CACHE_TTL", "0")
    monkeypatch.setattr(screening_service, "_fetch_yahoo_market_data", lambda: (market_data, 1))
    monkeypatch.setattr(screening_service, "_market_data_cache", None)

    assert get_market_data() == market_data


def test_yahoo_failure_does_not_fall_back_to_mock(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_DATA_PROVIDER", "yahoo")
    monkeypatch.setenv("MARKET_DATA_CACHE_PATH", str(tmp_path / "empty.sqlite3"))
    monkeypatch.setattr(screening_service, "_fetch_yahoo_market_data", lambda: ([], 4))
    monkeypatch.setattr(screening_service, "_market_data_cache", None)
    monkeypatch.setattr(screening_service, "_market_data_cache_key", None)
    monkeypatch.setattr(screening_service, "_market_data_source", "unavailable")

    assert get_market_data() == []
    summary = get_screening_summary()
    assert summary["source"] == "unavailable"
    assert summary["priced_count"] == 0
    assert summary["universe_count"] == 4
    assert "Yahoo Finance" in summary["data_status"]


def test_vnstock_listing_is_filtered_before_yahoo_history(monkeypatch):
    listing = [
        {"symbol": "AAA", "exchange": "HSX", "type": "STOCK", "organ_name": "Company A"},
        {"symbol": "BBB", "exchange": "HNX", "type": "STOCK"},
        {"symbol": "CCC", "exchange": "UPCOM", "type": "STOCK"},
        {"symbol": "FUND", "exchange": "HSX", "type": "FUND"},
    ]
    monkeypatch.setenv("YAHOO_MAX_SYMBOLS", "5")
    monkeypatch.delenv("YAHOO_SYMBOLS", raising=False)
    monkeypatch.setattr(screening_service, "_fetch_vnstock_listing", lambda: listing)
    monkeypatch.setattr(
        screening_service,
        "_fetch_yahoo_history",
        lambda stock: {**stock, "close_prices": [10, 11], "source": "yahoo"},
    )

    market_data, universe_count = screening_service._fetch_yahoo_market_data()

    assert universe_count == 2
    assert [row["symbol"] for row in market_data] == ["AAA", "BBB"]
    assert market_data[0]["name"] == "Company A"
    assert {row["source"] for row in market_data} == {"yahoo"}


def test_requested_symbol_fetches_only_that_listing_entry(monkeypatch):
    listing = [
        {"symbol": "AAA", "exchange": "HSX", "type": "STOCK"},
        {"symbol": "BBB", "exchange": "HNX", "type": "STOCK"},
    ]
    fetched_symbols = []
    monkeypatch.setenv("YAHOO_MAX_SYMBOLS", "5")
    monkeypatch.setattr(screening_service, "_fetch_vnstock_listing", lambda: listing)
    monkeypatch.setattr(
        screening_service,
        "_fetch_yahoo_history",
        lambda stock: fetched_symbols.append(stock["symbol"]) or {
            **stock,
            "close_prices": [10.0, 11.0],
            "source": "yahoo",
        },
    )

    market_data, universe_count = screening_service._fetch_yahoo_market_data(["BBB"])

    assert fetched_symbols == ["BBB"]
    assert universe_count == 2
    assert [row["symbol"] for row in market_data] == ["BBB"]


def test_yahoo_ticker_uses_configurable_vietnam_suffix(monkeypatch):
    monkeypatch.setenv("YAHOO_TICKER_SUFFIX", "VN")
    monkeypatch.setenv("YAHOO_HNX_SUFFIX", "HN")

    assert yahoo_finance.yahoo_ticker("fpt", "HOSE") == "FPT.VN"
    assert yahoo_finance.yahoo_ticker("shs", "HNX") == "SHS.HN"


def test_sqlite_cache_survives_in_memory_cache_reset(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_DATA_PROVIDER", "yahoo")
    monkeypatch.setenv("MARKET_DATA_CACHE_PATH", str(tmp_path / "prices.sqlite3"))
    monkeypatch.setenv("MARKET_DATA_CACHE_TTL", "3600")
    market_data = [{"symbol": "FPT", "close_prices": [10.0, 11.0], "source": "yahoo"}]
    fetch_calls = []

    def fetch_yahoo_data():
        fetch_calls.append(True)
        return market_data, 1

    monkeypatch.setattr(screening_service, "_fetch_yahoo_market_data", fetch_yahoo_data)
    monkeypatch.setattr(screening_service, "_market_data_cache", None)
    monkeypatch.setattr(screening_service, "_market_data_cache_key", None)
    assert get_market_data() == market_data

    monkeypatch.setattr(screening_service, "_market_data_cache", None)
    monkeypatch.setattr(screening_service, "_market_data_cache_key", None)
    assert get_market_data() == market_data
    assert len(fetch_calls) == 1
    assert screening_service._market_data_cache_status == "disk"


def test_market_cache_uses_tmp_directory_on_vercel(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("MARKET_DATA_CACHE_PATH", raising=False)

    assert market_cache._cache_path() == Path("/tmp/vnstock-market-data.sqlite3")


def test_refresh_uses_old_disk_cache_when_yahoo_is_unavailable(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_DATA_PROVIDER", "yahoo")
    monkeypatch.setenv("MARKET_DATA_CACHE_PATH", str(tmp_path / "prices.sqlite3"))
    monkeypatch.setenv("MARKET_DATA_CACHE_TTL", "3600")
    market_data = [{"symbol": "FPT", "close_prices": [10.0, 11.0], "source": "yahoo"}]
    monkeypatch.setattr(screening_service, "_fetch_yahoo_market_data", lambda: (market_data, 1))
    monkeypatch.setattr(screening_service, "_market_data_cache", None)
    monkeypatch.setattr(screening_service, "_market_data_cache_key", None)
    get_market_data()

    monkeypatch.setattr(screening_service, "_fetch_yahoo_market_data", lambda: ([], 0))
    assert screening_service.refresh_market_data() == market_data
    assert screening_service._market_data_cache_status == "stale"
    assert screening_service._market_data_source == "yahoo"


def test_force_refresh_bypasses_fresh_memory_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_DATA_PROVIDER", "yahoo")
    monkeypatch.setenv("MARKET_DATA_CACHE_PATH", str(tmp_path / "force-refresh.sqlite3"))
    monkeypatch.setenv("MARKET_DATA_CACHE_TTL", "3600")
    first_snapshot = [{"symbol": "FPT", "close_prices": [10.0, 11.0], "source": "yahoo"}]
    updated_snapshot = [{"symbol": "FPT", "close_prices": [10.0, 12.0], "source": "yahoo"}]
    snapshots = iter([(first_snapshot, 1), (updated_snapshot, 1)])
    monkeypatch.setattr(screening_service, "_fetch_yahoo_market_data", lambda: next(snapshots))
    monkeypatch.setattr(screening_service, "_market_data_cache", None)
    monkeypatch.setattr(screening_service, "_market_data_cache_key", None)

    assert get_market_data() == first_snapshot
    assert screening_service.refresh_market_data() == updated_snapshot
    assert screening_service._market_data_cache_status == "live"


def test_risk_metrics_use_half_kelly_and_two_to_one_risk_levels():
    prices = _known_return_series()

    metrics = screening_service._calculate_risk_metrics(prices)

    assert metrics["win_probability_percent"] == 55
    assert metrics["payoff_ratio"] == 1
    assert metrics["kelly_allocation_percent"] == 5
    assert metrics["stop_loss_price"] < prices[-1]
    assert metrics["take_profit_price"] > prices[-1]


def test_mock_market_data_is_independent_of_external_providers():
    market_data = build_mock_market_data()

    assert all(row["source"] == "mock" for row in market_data)
    assert all(len(row["close_prices"]) == 100 for row in market_data)


def test_signal_explanation_and_allocation_are_derived_from_both_strategies(monkeypatch):
    monkeypatch.setattr(
        screening_service,
        "evaluate_trend_signal",
        lambda prices: {"signal": "Bullish", "momentum": 8.0, "score": 11.2, "last_price": 108.0},
    )
    monkeypatch.setattr(
        screening_service,
        "evaluate_mean_reversion_signal",
        lambda prices: {"signal": "Neutral", "momentum": 0.4, "score": 0.44, "last_price": 108.0},
    )

    row = screening_service._evaluate_stock(
        {"symbol": "AAA", "name": "Company A", "close_prices": _known_return_series()}
    )

    assert row["recommendation"] == "Buy"
    assert row["allocation_percent"] == 5
    assert "đạt ngưỡng xu hướng" in row["reason"]
    assert len(row["criteria"]) == 5
    assert len(row["chart_patterns"]) == 6


def test_market_allocation_is_capped_at_five_buy_candidates(monkeypatch):
    monkeypatch.setattr(
        screening_service,
        "evaluate_trend_signal",
        lambda prices: {"signal": "Bullish", "momentum": prices[-1], "score": 1, "last_price": prices[-1]},
    )
    monkeypatch.setattr(
        screening_service,
        "evaluate_mean_reversion_signal",
        lambda prices: {"signal": "Oversold", "momentum": -5, "score": 1, "last_price": prices[-1]},
    )
    market_data = [
        {
            "symbol": f"STK{index}",
            "name": f"Stock {index}",
            "close_prices": _known_return_series(),
        }
        for index in range(1, 8)
    ]

    rows = screening_service._evaluate_market(market_data)

    assert sum(row["allocation_percent"] for row in rows) <= 100
    assert sum(row["allocation_percent"] > 0 for row in rows) == 5
    assert all(row["allocation_percent"] <= 20 for row in rows)
