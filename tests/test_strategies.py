from app.strategies.trend_following import evaluate_trend_signal
from app.strategies.mean_reversion import evaluate_mean_reversion_signal


def test_trend_following_detects_bullish_trend():
    result = evaluate_trend_signal([100, 104, 107, 110, 113])
    assert result["signal"] == "Bullish"
    assert result["momentum"] > 0


def test_mean_reversion_detects_oversold_condition():
    result = evaluate_mean_reversion_signal([98, 95, 93, 90, 89])
    assert result["signal"] == "Oversold"
    assert result["momentum"] < 0
