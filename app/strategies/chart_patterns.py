import statistics


_PIVOT_WINDOW = 2


def _valid_prices(values):
    prices = []
    for value in values or []:
        try:
            price = float(value)
        except (TypeError, ValueError):
            continue
        if price > 0:
            prices.append(price)
    return prices


def _valid_volumes(values):
    volumes = []
    for value in values or []:
        try:
            volume = float(value)
        except (TypeError, ValueError):
            continue
        if volume >= 0:
            volumes.append(volume)
    return volumes


def _pivots(values, kind):
    pivots = []
    for index in range(_PIVOT_WINDOW, len(values) - _PIVOT_WINDOW):
        value = values[index]
        before = values[index - _PIVOT_WINDOW:index]
        after = values[index + 1:index + _PIVOT_WINDOW + 1]
        if kind == "high" and value >= max(before) and value > max(after):
            pivots.append((index, value))
        elif kind == "low" and value <= min(before) and value < min(after):
            pivots.append((index, value))
    return pivots


def _volume_ratio(volumes):
    if len(volumes) < 21:
        return None
    baseline = statistics.mean(volumes[-21:-1])
    if baseline <= 0:
        return None
    return volumes[-1] / baseline


def _result(
    name,
    signal,
    message,
    neckline=None,
    support=None,
    volume_ratio=None,
    volume_basis="TB20",
):
    return {
        "name": name,
        "signal": signal,
        "message": message,
        "neckline": round(neckline, 2) if neckline is not None else None,
        "support": round(support, 2) if support is not None else None,
        "volume_ratio": round(volume_ratio, 2) if volume_ratio is not None else None,
        "volume_basis": volume_basis,
    }


def _cup_and_handle(prices, volume_ratio):
    name = "Cốc tay cầm"
    if len(prices) < 60:
        return _result(name, "Không đủ dữ liệu", "Cần ít nhất 60 phiên giá.", volume_ratio=volume_ratio)

    window = prices[-60:]
    left_rim = max(window[:15])
    cup_bottom = min(window[15:40])
    right_rim = max(window[40:50])
    handle_low = min(window[50:59])
    depth = (left_rim - cup_bottom) / left_rim if left_rim else 0
    rim_difference = abs(right_rim - left_rim) / left_rim if left_rim else 1
    handle_retracement = (
        (right_rim - handle_low) / (left_rim - cup_bottom)
        if left_rim > cup_bottom
        else 1
    )

    structure_valid = (
        0.12 <= depth <= 0.35
        and rim_difference <= 0.05
        and 0.10 <= handle_retracement <= 0.50
        and handle_low > cup_bottom
    )
    if not structure_valid:
        return _result(name, "Không có mẫu", "Chưa thấy cấu trúc cốc và tay cầm rõ.", volume_ratio=volume_ratio)

    current_price = prices[-1]
    volume_confirmed = volume_ratio is not None and volume_ratio >= 1.5
    if current_price < handle_low and volume_confirmed:
        return _result(
            name,
            "Bán",
            "Giá thủng hỗ trợ tay cầm kèm volume cao.",
            neckline=left_rim,
            support=handle_low,
            volume_ratio=volume_ratio,
        )
    if current_price > max(left_rim, right_rim) and volume_confirmed:
        return _result(
            name,
            "Mua",
            "Breakout khỏi miệng cốc, volume đạt ít nhất 1.5× trung bình 20 phiên.",
            neckline=max(left_rim, right_rim),
            support=handle_low,
            volume_ratio=volume_ratio,
        )
    return _result(
        name,
        "Theo dõi",
        "Mẫu hình đã hình thành; chờ breakout có volume xác nhận hoặc thủng hỗ trợ tay cầm.",
        neckline=max(left_rim, right_rim),
        support=handle_low,
        volume_ratio=volume_ratio,
    )


def _double_bottom(prices):
    name = "Hai đáy"
    lows = _pivots(prices[-100:], "low")
    for second_index in range(len(lows) - 1, 0, -1):
        second_at, second_price = lows[second_index]
        for first_at, first_price in reversed(lows[:second_index]):
            separation = second_at - first_at
            similar = abs(second_price - first_price) / ((second_price + first_price) / 2)
            if not 7 <= separation <= 50 or similar > 0.03:
                continue
            neckline = max(prices[-100:][first_at + 1:second_at])
            if neckline < max(first_price, second_price) * 1.04:
                continue
            current_price = prices[-1]
            if current_price > neckline:
                return _result(name, "Mua", "Giá đã vượt neckline xác nhận mô hình hai đáy.", neckline, min(first_price, second_price))
            return _result(name, "Theo dõi", "Hai đáy tiềm năng; chờ giá đóng cửa vượt neckline.", neckline, min(first_price, second_price))
    return _result(name, "Không có mẫu", "Chưa thấy hai đáy cân xứng rõ.")


def _double_top(prices):
    name = "Hai đỉnh"
    highs = _pivots(prices[-100:], "high")
    for second_index in range(len(highs) - 1, 0, -1):
        second_at, second_price = highs[second_index]
        for first_at, first_price in reversed(highs[:second_index]):
            separation = second_at - first_at
            similar = abs(second_price - first_price) / ((second_price + first_price) / 2)
            if not 7 <= separation <= 50 or similar > 0.03:
                continue
            neckline = min(prices[-100:][first_at + 1:second_at])
            if neckline > min(first_price, second_price) * 0.96:
                continue
            current_price = prices[-1]
            if current_price < neckline:
                return _result(name, "Bán", "Giá đã thủng neckline xác nhận mô hình hai đỉnh.", neckline, max(first_price, second_price))
            return _result(name, "Theo dõi", "Hai đỉnh tiềm năng; chờ giá đóng cửa thủng neckline.", neckline, max(first_price, second_price))
    return _result(name, "Không có mẫu", "Chưa thấy hai đỉnh cân xứng rõ.")


def _head_and_shoulders(prices):
    name = "Vai đầu vai"
    window = prices[-100:]
    highs = _pivots(window, "high")
    for index in range(len(highs) - 1, 1, -1):
        left = highs[index - 2]
        head = highs[index - 1]
        right = highs[index]
        left_at, left_price = left
        head_at, head_price = head
        right_at, right_price = right
        shoulders_match = abs(left_price - right_price) / ((left_price + right_price) / 2) <= 0.05
        head_prominence = head_price >= max(left_price, right_price) * 1.05
        spaced = head_at - left_at >= 4 and right_at - head_at >= 4
        if not shoulders_match or not head_prominence or not spaced:
            continue

        left_trough = min(window[left_at + 1:head_at])
        right_trough = min(window[head_at + 1:right_at])
        neckline = (left_trough + right_trough) / 2
        if prices[-1] < neckline:
            return _result(name, "Bán", "Giá đóng cửa đã phá neckline mô hình vai đầu vai.", neckline, min(left_price, right_price))
        return _result(name, "Theo dõi", "Vai đầu vai tiềm năng; chờ giá đóng cửa phá neckline.", neckline, min(left_price, right_price))
    return _result(name, "Không có mẫu", "Chưa thấy cấu trúc vai đầu vai rõ.")


def _average_pivot_volume(volumes, index):
    sample = [volume for volume in volumes[max(0, index - 2):index + 3] if volume is not None]
    return statistics.mean(sample) if len(sample) == 5 else None


def _inverse_head_and_shoulders(prices, volumes):
    name = "Vai đầu vai ngược"
    window = prices[-100:]
    offset = len(prices) - len(window)
    lows = _pivots(window, "low")
    for index in range(len(lows) - 1, 1, -1):
        left = lows[index - 2]
        head = lows[index - 1]
        right = lows[index]
        left_at, left_price = left
        head_at, head_price = head
        right_at, right_price = right
        shoulders_match = abs(left_price - right_price) / ((left_price + right_price) / 2) <= 0.05
        head_prominence = head_price <= min(left_price, right_price) * 0.95
        spaced = head_at - left_at >= 4 and right_at - head_at >= 4
        if not shoulders_match or not head_prominence or not spaced:
            continue

        left_peak = max(window[left_at + 1:head_at])
        right_peak = max(window[head_at + 1:right_at])
        neckline = (left_peak + right_peak) / 2
        left_volume = _average_pivot_volume(volumes, offset + left_at)
        head_volume = _average_pivot_volume(volumes, offset + head_at)
        right_volume = _average_pivot_volume(volumes, offset + right_at)
        volume_contraction = (
            left_volume is not None
            and head_volume is not None
            and right_volume is not None
            and right_volume < left_volume
            and right_volume < head_volume
        )
        volume_ratio = (
            right_volume / max(left_volume, head_volume)
            if volume_contraction
            else None
        )
        breakout = prices[-1] > neckline
        if breakout and volume_contraction:
            return _result(
                name,
                "Mua",
                "Giá vượt neckline; volume vai phải thấp hơn vai trái và đầu.",
                neckline,
                head_price,
                volume_ratio,
                "vai phải/vai trái-đầu",
            )
        message = (
            "Đã vượt neckline nhưng volume vai phải chưa xác nhận giảm."
            if breakout
            else "Mẫu hình tiềm năng; chờ vượt neckline và volume vai phải thấp hơn vai trái/đầu."
        )
        return _result(
            name,
            "Theo dõi",
            message,
            neckline,
            head_price,
            volume_ratio,
            "vai phải/vai trái-đầu",
        )
    return _result(name, "Không có mẫu", "Chưa thấy cấu trúc vai đầu vai ngược rõ.")


def _morning_star(prices, volumes, candles, volume_ratio):
    name = "Sao Mai"
    if len(candles) != len(prices) or len(candles) < 3:
        return _result(name, "Không đủ dữ liệu", "Cần OHLC của ít nhất 3 phiên.", volume_ratio=volume_ratio)

    first, middle, third = candles[-3:]
    try:
        first_open, first_close, first_high, first_low = (
            float(first[key]) for key in ("open", "close", "high", "low")
        )
        middle_open, middle_close, middle_high, middle_low = (
            float(middle[key]) for key in ("open", "close", "high", "low")
        )
        third_open, third_close, third_high, third_low = (
            float(third[key]) for key in ("open", "close", "high", "low")
        )
    except (KeyError, TypeError, ValueError):
        return _result(name, "Không đủ dữ liệu", "Yahoo không trả đủ OHLC cho ba nến.", volume_ratio=volume_ratio)

    first_range = first_high - first_low
    middle_range = middle_high - middle_low
    third_range = third_high - third_low
    if min(first_range, middle_range, third_range) <= 0:
        return _result(name, "Không có mẫu", "Biên độ nến không hợp lệ.", volume_ratio=volume_ratio)

    first_body = first_open - first_close
    middle_body = abs(middle_close - middle_open)
    third_body = third_close - third_open
    first_midpoint = (first_open + first_close) / 2
    structure_valid = (
        first_body / first_range >= 0.55
        and middle_body / middle_range <= 0.30
        and third_body / third_range >= 0.55
        and third_close > first_midpoint
        and third_close > middle_high
    )
    if not structure_valid:
        return _result(name, "Không có mẫu", "Ba nến cuối chưa tạo cấu trúc Sao Mai rõ.", volume_ratio=volume_ratio)

    if volume_ratio is not None and volume_ratio >= 1.5:
        return _result(
            name,
            "Mua",
            "Ba nến đảo chiều tăng; volume nến thứ ba đạt ít nhất 1.5× trung bình 20 phiên.",
            first_midpoint,
            first_low,
            volume_ratio,
        )
    return _result(
        name,
        "Theo dõi",
        "Có cấu trúc Sao Mai; chờ volume nến thứ ba đạt ít nhất 1.5× trung bình 20 phiên.",
        first_midpoint,
        first_low,
        volume_ratio,
    )


def analyze_chart_patterns(prices, volumes=None, candles=None):
    valid_prices = _valid_prices(prices)
    valid_volumes = _valid_volumes(volumes)
    aligned_volumes = []
    for volume in volumes or []:
        try:
            value = float(volume)
        except (TypeError, ValueError):
            value = None
        aligned_volumes.append(value if value is not None and value >= 0 else None)
    volume_ratio = _volume_ratio(valid_volumes)
    if len(valid_volumes) != len(valid_prices):
        volume_ratio = None

    return [
        _cup_and_handle(valid_prices, volume_ratio),
        _double_bottom(valid_prices),
        _double_top(valid_prices),
        _head_and_shoulders(valid_prices),
        _morning_star(valid_prices, aligned_volumes, candles or [], volume_ratio),
        _inverse_head_and_shoulders(valid_prices, aligned_volumes),
    ]
