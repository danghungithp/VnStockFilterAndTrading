from app.strategies.trend_following import evaluate_trend_signal
from app.strategies.mean_reversion import evaluate_mean_reversion_signal
from app.strategies.chart_patterns import analyze_chart_patterns


def _cup_handle_prices():
    return (
        [100, 101, 100, 99, 98, 96, 94, 91, 88, 85, 82, 80, 82, 85, 90]
        + [95, 98, 100, 99, 97, 94, 90, 86, 82, 80, 82, 85, 89, 93, 97, 99, 100, 99, 98, 97, 96, 95, 97, 99, 100]
        + [99, 100, 99, 98, 99, 100, 99, 98, 99, 100]
        + [99, 98, 97, 96, 97, 98, 99, 98, 97]
        + [103]
    )


def test_trend_following_detects_bullish_trend():
    result = evaluate_trend_signal([100, 104, 107, 110, 113])
    assert result["signal"] == "Bullish"
    assert result["momentum"] > 0


def test_mean_reversion_detects_oversold_condition():
    result = evaluate_mean_reversion_signal([98, 95, 93, 90, 89])
    assert result["signal"] == "Oversold"
    assert result["momentum"] < 0


def test_cup_and_handle_requires_breakout_and_volume_confirmation():
    prices = _cup_handle_prices()
    volumes = [100] * (len(prices) - 1) + [200]

    patterns = analyze_chart_patterns(prices, volumes)
    cup = patterns[0]

    assert cup["name"] == "Cốc tay cầm"
    assert cup["signal"] == "Mua"
    assert cup["volume_ratio"] == 2


def test_cup_and_handle_without_volume_confirmation_is_watch():
    prices = _cup_handle_prices()
    volumes = [100] * len(prices)

    assert analyze_chart_patterns(prices, volumes)[0]["signal"] == "Theo dõi"


def test_cup_and_handle_sells_on_high_volume_handle_support_break():
    prices = _cup_handle_prices()
    prices[-1] = 95
    volumes = [100] * (len(prices) - 1) + [200]

    pattern = analyze_chart_patterns(prices, volumes)[0]

    assert pattern["signal"] == "Bán"
    assert pattern["support"] == 96


def test_double_bottom_and_top_confirm_on_neckline_breaks():
    double_bottom = [100, 101, 103, 101, 98, 94, 90, 86, 82, 80, 82, 86, 92, 100, 106, 110, 106, 100, 94, 90, 86, 82, 80, 82, 86, 92, 100, 106, 112]
    double_top = [80, 79, 77, 79, 82, 88, 94, 100, 108, 120, 118, 112, 106, 100, 94, 90, 94, 100, 106, 112, 118, 120, 118, 112, 106, 100, 94, 88, 85]

    bottom_patterns = analyze_chart_patterns(double_bottom)
    top_patterns = analyze_chart_patterns(double_top)

    assert bottom_patterns[1]["signal"] == "Mua"
    assert bottom_patterns[1]["neckline"] == 110
    assert top_patterns[2]["signal"] == "Bán"
    assert top_patterns[2]["neckline"] == 90


def test_head_and_shoulders_confirms_bearish_neckline_break():
    prices = [100, 105, 110, 108, 102, 95, 100, 110, 125, 120, 110, 100, 95, 102, 110, 108, 102, 95, 90, 88]

    pattern = analyze_chart_patterns(prices)[3]

    assert pattern["name"] == "Vai đầu vai"
    assert pattern["signal"] == "Bán"
    assert pattern["neckline"] == 95


def test_morning_star_requires_bullish_third_candle_and_volume():
    candles = [{"open": 99, "close": 100, "high": 101, "low": 98} for _ in range(20)]
    candles += [
        {"open": 100, "close": 90, "high": 101, "low": 89},
        {"open": 87, "close": 87.2, "high": 90, "low": 86},
        {"open": 88, "close": 99, "high": 100, "low": 87},
    ]
    prices = [candle["close"] for candle in candles]
    volumes = [100] * (len(candles) - 1) + [200]

    morning_star = analyze_chart_patterns(prices, volumes, candles)[4]

    assert morning_star["name"] == "Sao Mai"
    assert morning_star["signal"] == "Mua"
    assert morning_star["volume_ratio"] == 2


def test_morning_star_without_volume_confirmation_is_watch():
    candles = [{"open": 99, "close": 100, "high": 101, "low": 98} for _ in range(20)]
    candles += [
        {"open": 100, "close": 90, "high": 101, "low": 89},
        {"open": 87, "close": 87.2, "high": 90, "low": 86},
        {"open": 88, "close": 99, "high": 100, "low": 87},
    ]
    prices = [candle["close"] for candle in candles]

    assert analyze_chart_patterns(prices, [100] * len(prices), candles)[4]["signal"] == "Theo dõi"


def test_inverse_head_and_shoulders_requires_neckline_and_lower_right_shoulder_volume():
    prices = [100, 95, 90, 94, 100, 105, 100, 90, 80, 85, 95, 103, 100, 95, 92, 96, 102, 105, 102, 108, 112]
    volumes = [100] * len(prices)
    volumes[0:5] = [300] * 5
    volumes[6:11] = [500] * 5
    pattern = analyze_chart_patterns(prices, volumes)[5]

    assert pattern["name"] == "Vai đầu vai ngược"
    assert pattern["signal"] == "Mua"
    assert pattern["neckline"] == 104
    assert pattern["volume_ratio"] < 1


def test_inverse_head_and_shoulders_without_volume_contraction_stays_watch():
    prices = [100, 95, 90, 94, 100, 105, 100, 90, 80, 85, 95, 103, 100, 95, 92, 96, 102, 105, 102, 108, 112]

    assert analyze_chart_patterns(prices, [100] * len(prices))[5]["signal"] == "Theo dõi"
