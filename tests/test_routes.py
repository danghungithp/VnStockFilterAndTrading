from app import create_app
import app.data.mock_market_data as mock_market_data
import app.services.screening_service as screening_service


def _stub_market_data(monkeypatch):
    monkeypatch.setattr(screening_service, "_fetch_vnstock_market_data", lambda: ([], 0))
    monkeypatch.setattr(screening_service, "_market_data_cache", None)
    monkeypatch.setattr(mock_market_data, "_load_vnstock_quote", lambda: None)


def test_health_endpoint():
    app = create_app()
    client = app.test_client()
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"


def test_overview_endpoint_returns_summary(monkeypatch):
    _stub_market_data(monkeypatch)
    app = create_app()
    client = app.test_client()
    response = client.get("/api/overview")
    assert response.status_code == 200
    payload = response.get_json()
    assert "symbols" in payload
    assert "strategy_summary" in payload


def test_recommendations_include_signal_reasons_and_allocations(monkeypatch):
    _stub_market_data(monkeypatch)
    app = create_app()
    client = app.test_client()

    response = client.get("/api/recommendations")

    assert response.status_code == 200
    recommendation = response.get_json()["recommendations"][0]
    assert recommendation["trend_signal"]
    assert recommendation["mean_reversion_signal"]
    assert recommendation["reason"]
    assert recommendation["allocation_percent"] in {0, 10, 20}


def test_strategy_endpoint_returns_rows(monkeypatch):
    _stub_market_data(monkeypatch)
    app = create_app()
    client = app.test_client()

    response = client.get("/api/strategy/trend_following")

    assert response.status_code == 200
    assert response.get_json()["strategy"] == "trend_following"
    assert response.get_json()["rows"]
