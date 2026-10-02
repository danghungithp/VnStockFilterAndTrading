from app import create_app
import app.services.screening_service as screening_service
from app.data.mock_market_data import build_mock_market_data


def _stub_market_data(monkeypatch):
    monkeypatch.setenv("MARKET_DATA_PROVIDER", "mock")
    monkeypatch.setattr(screening_service, "_fetch_yahoo_market_data", lambda: ([], 0))
    monkeypatch.setattr(screening_service, "_market_data_cache", None)
    monkeypatch.setattr(screening_service, "_market_data_source", "unavailable")
    monkeypatch.setattr(screening_service, "load_market_cache", lambda cache_key: None)
    monkeypatch.setattr(screening_service, "save_market_cache", lambda *args: None)


def test_health_endpoint():
    app = create_app()
    client = app.test_client()
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"


def test_robots_and_sitemap_endpoints():
    client = create_app().test_client()

    robots = client.get("/robots.txt")
    sitemap = client.get("/sitemap.xml")

    assert robots.status_code == 200
    assert b"Sitemap: https://localhost/sitemap.xml" in robots.data
    assert b"Disallow: /market-data/refresh" in robots.data
    assert sitemap.status_code == 200
    assert b"<loc>https://localhost/</loc>" in sitemap.data
    assert b"<loc>https://localhost/recommendations</loc>" in sitemap.data


def test_dashboard_includes_seo_metadata_and_noindexes_codespaces_preview(monkeypatch):
    _stub_market_data(monkeypatch)
    client = create_app().test_client()

    response = client.get("/", headers={"Host": "cuddly-spork-5000.app.github.dev"})

    assert response.status_code == 200
    assert "lọc cổ phiếu tăng trưởng".encode() in response.data.lower()
    assert b"name=\"robots\" content=\"noindex,nofollow\"" in response.data
    assert b"property=\"og:type\" content=\"website\"" in response.data
    assert b"application/ld+json" in response.data


def test_dashboard_labels_yahoo_live_data(monkeypatch):
    market_data = build_mock_market_data()
    for row in market_data:
        row["source"] = "yahoo"
    monkeypatch.setenv("MARKET_DATA_PROVIDER", "yahoo")
    monkeypatch.setenv("MARKET_DATA_CACHE_TTL", "0")
    monkeypatch.setattr(screening_service, "_fetch_yahoo_market_data", lambda: (market_data, len(market_data)))
    monkeypatch.setattr(screening_service, "_market_data_cache", None)
    monkeypatch.setattr(screening_service, "load_market_cache", lambda cache_key: None)
    monkeypatch.setattr(screening_service, "save_market_cache", lambda *args: None)
    client = create_app().test_client()

    response = client.get("/")

    assert response.status_code == 200
    assert b"LIVE" in response.data
    assert b"Yahoo Finance" in response.data
    assert "Cổ phiếu Trend Following".encode() in response.data
    assert "Cốc tay cầm".encode() in response.data
    assert "Sao Mai".encode() in response.data
    assert "Vai đầu vai ngược".encode() in response.data
    assert "Chốt lời".encode() in response.data


def test_dashboard_identifies_demo_fallback(monkeypatch):
    _stub_market_data(monkeypatch)
    response = create_app().test_client().get("/")

    assert response.status_code == 200
    assert "DEMO · dữ liệu mô phỏng".encode() in response.data


def test_dashboard_reports_live_data_unavailable_without_demo(monkeypatch):
    monkeypatch.setenv("MARKET_DATA_PROVIDER", "yahoo")
    monkeypatch.setattr(screening_service, "_fetch_yahoo_market_data", lambda: ([], 3))
    monkeypatch.setattr(screening_service, "_market_data_cache", None)
    monkeypatch.setattr(screening_service, "_market_data_source", "unavailable")
    monkeypatch.setattr(screening_service, "load_market_cache", lambda cache_key: None)
    monkeypatch.setattr(screening_service, "save_market_cache", lambda *args: None)
    response = create_app().test_client().get("/")

    assert response.status_code == 200
    assert b"YAHOO UNAVAILABLE" in response.data
    assert "DEMO · dữ liệu mô phỏng".encode() not in response.data


def test_recommendations_page_shows_source_and_risk_levels(monkeypatch):
    _stub_market_data(monkeypatch)
    response = create_app().test_client().get("/recommendations")

    assert response.status_code == 200
    assert b"DEMO" in response.data
    assert "Cắt lỗ".encode() in response.data
    assert "Chốt lời".encode() in response.data
    assert b"capital-input" in response.data
    assert b'type="text" inputmode="numeric"' in response.data
    assert b'Intl.NumberFormat("en-US"' in response.data
    assert b"data-kelly-percent" in response.data
    assert b"currency: \"VND\"" in response.data


def test_stock_symbol_search_uses_existing_analysis(monkeypatch):
    market_data = [
        {
            **next(row for row in build_mock_market_data() if row["symbol"] == "FPT"),
            "source": "yahoo",
            "exchange": "HOSE",
        }
    ]
    monkeypatch.setenv("MARKET_DATA_PROVIDER", "yahoo")
    monkeypatch.setenv("MARKET_DATA_CACHE_TTL", "3600")
    monkeypatch.setattr(
        screening_service,
        "_fetch_yahoo_market_data",
        lambda symbols: (market_data, 705) if symbols == ("FPT",) else ([], 705),
    )
    monkeypatch.setattr(screening_service, "_market_data_cache", None)
    monkeypatch.setattr(screening_service, "_market_data_cache_key", None)
    monkeypatch.setattr(screening_service, "load_market_cache", lambda cache_key: None)
    monkeypatch.setattr(screening_service, "save_market_cache", lambda *args: None)

    response = create_app().test_client().get("/recommendations?symbol=fpt")

    assert response.status_code == 200
    assert "Phân tích mã FPT".encode() in response.data
    assert b"Yahoo Finance" in response.data
    assert "Cốc tay cầm".encode() in response.data
    assert "FPT".encode() in response.data


def test_stock_symbol_search_rejects_invalid_ticker():
    response = create_app().test_client().get("/recommendations?symbol=FPT.VN")

    assert response.status_code == 400


def test_refresh_route_fetches_and_redirects_to_requested_page(monkeypatch, tmp_path):
    market_data = [{"symbol": "FPT", "name": "FPT", "close_prices": [10.0, 11.0], "source": "yahoo"}]
    monkeypatch.setenv("MARKET_DATA_PROVIDER", "yahoo")
    monkeypatch.setenv("MARKET_DATA_CACHE_PATH", str(tmp_path / "refresh.sqlite3"))
    monkeypatch.setenv("MARKET_DATA_CACHE_TTL", "3600")
    monkeypatch.setattr(screening_service, "_fetch_yahoo_market_data", lambda: (market_data, 1))
    monkeypatch.setattr(screening_service, "_market_data_cache", None)
    monkeypatch.setattr(screening_service, "_market_data_cache_key", None)

    response = create_app().test_client().post(
        "/market-data/refresh",
        data={"return_to": "recommendations_page"},
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/recommendations?refresh_result=success")


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
    assert 0 <= recommendation["allocation_percent"] <= 20


def test_strategy_endpoint_returns_rows(monkeypatch):
    _stub_market_data(monkeypatch)
    app = create_app()
    client = app.test_client()

    response = client.get("/api/strategy/trend_following")

    assert response.status_code == 200
    assert response.get_json()["strategy"] == "trend_following"
    assert response.get_json()["rows"]
