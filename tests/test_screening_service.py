import sys
from types import SimpleNamespace

import app.data.mock_market_data as mock_market_data
import app.services.screening_service as screening_service
from app.data.mock_market_data import build_mock_market_data
from app.services.screening_service import get_market_data, get_screening_summary


def _stub_market_data_providers(monkeypatch):
    monkeypatch.setattr(screening_service, "_fetch_vnstock_market_data", lambda: ([], 0))
    monkeypatch.setattr(screening_service, "_market_data_cache", None)
    monkeypatch.setattr(mock_market_data, "_load_vnstock_quote", lambda: None)
    monkeypatch.setattr(mock_market_data, "_fetch_vnstock_close_prices", lambda client, symbol: [])


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


def test_mock_market_data_uses_vnstock_and_reports_source(monkeypatch):
    class ClosePrices:
        def dropna(self):
            return self

        def tolist(self):
            return [10.0, 11.0, 12.0]

    class History:
        empty = False
        columns = ["close"]

        def __getitem__(self, column):
            assert column == "close"
            return ClosePrices()

    class VnstockQuote:
        def __init__(self, symbol, source):
            assert source == "VCI"

        def history(self, **kwargs):
            assert kwargs["interval"] == "1D"
            return History()

    monkeypatch.setattr(mock_market_data, "_load_vnstock_quote", lambda: VnstockQuote)
    market_data = build_mock_market_data()

    assert market_data[0]["close_prices"] == [10.0, 11.0, 12.0]
    assert all(row["source"] == "vnstock" for row in market_data)

    monkeypatch.setattr("app.services.screening_service.get_market_data", lambda: market_data)
    assert get_screening_summary()["source"] == "vnstock"


def test_mock_market_data_falls_back_when_vnstock_fails(monkeypatch):
    class VnstockQuote:
        def __init__(self, symbol, source):
            pass

        def history(self, **kwargs):
            raise ConnectionError("provider unavailable")

    monkeypatch.setattr(mock_market_data, "_load_vnstock_quote", lambda: VnstockQuote)
    market_data = build_mock_market_data()

    assert all(row["source"] == "mock" for row in market_data)
    assert all(len(row["close_prices"]) == 100 for row in market_data)


def test_market_symbol_normalization_keeps_only_hose_and_hnx_stocks():
    symbols = screening_service._normalize_market_symbols(
        [
            {"symbol": "AAA", "exchange": "HSX", "type": "STOCK", "organ_name": "Company A"},
            {"symbol": "BBB", "exchange": "HNX", "type": "STOCK"},
            {"symbol": "CCC", "exchange": "UPCOM", "type": "STOCK"},
            {"symbol": "FUND", "exchange": "HSX", "type": "FUND"},
        ]
    )

    assert symbols == [
        {"symbol": "AAA", "name": "Company A", "exchange": "HOSE"},
        {"symbol": "BBB", "name": "BBB", "exchange": "HNX"},
    ]


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
        {"symbol": "AAA", "name": "Company A", "close_prices": [100, 108]}
    )

    assert row["recommendation"] == "Buy"
    assert row["allocation_percent"] == 10
    assert "đạt ngưỡng xu hướng" in row["reason"]
    assert len(row["criteria"]) == 3


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
        {"symbol": f"STK{index}", "name": f"Stock {index}", "close_prices": [100, index]}
        for index in range(1, 8)
    ]

    rows = screening_service._evaluate_market(market_data)

    assert sum(row["allocation_percent"] for row in rows) == 100
    assert sum(row["allocation_percent"] > 0 for row in rows) == 5
