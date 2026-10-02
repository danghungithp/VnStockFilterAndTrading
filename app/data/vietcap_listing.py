import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen


_LISTING_URL = "https://trading.vietcap.com.vn/api/price/symbols/getAll"
_GROUP_URL = "https://trading.vietcap.com.vn/api/price/symbols/getByGroup"
_INDEX_HISTORY_URL = "https://trading.vietcap.com.vn/api/chart/OHLCChart/gap-chart"
_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9,vi-VN;q=0.8,vi;q=0.7",
    "Content-Type": "application/json",
    "Cache-Control": "no-cache",
    "Referer": "https://trading.vietcap.com.vn/",
    "Origin": "https://trading.vietcap.com.vn",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36",
}


def fetch_vietnam_listings(timeout=10):
    request = Request(_LISTING_URL, headers=_HEADERS)
    with urlopen(request, timeout=timeout) as response:
        payload = json.load(response)

    if isinstance(payload, dict):
        payload = payload.get("data")
    if not isinstance(payload, list):
        raise ValueError("Vietcap listing API returned an unexpected response")

    records = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        records.append(
            {
                "symbol": item.get("symbol"),
                "exchange": item.get("board"),
                "type": item.get("type"),
                "organ_name": item.get("organName"),
                "organ_short_name": item.get("organShortName"),
            }
        )
    return records


def fetch_vietcap_group(group, timeout=10):
    query = urlencode({"group": group})
    request = Request(f"{_GROUP_URL}?{query}", headers=_HEADERS)
    with urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    if isinstance(payload, dict):
        payload = payload.get("data")
    if not isinstance(payload, list):
        raise ValueError("Vietcap group API returned an unexpected response")
    return [
        {"symbol": str(item["symbol"]).strip().upper()}
        for item in payload
        if isinstance(item, dict) and item.get("symbol")
    ]


def fetch_vietcap_index_history(symbol, count=100, timeout=15):
    normalized_symbol = str(symbol).strip().upper()
    if normalized_symbol not in {"VNINDEX", "VN30"}:
        raise ValueError("Only VNINDEX and VN30 index history is supported")

    payload = json.dumps(
        {
            "timeFrame": "ONE_DAY",
            "symbols": [normalized_symbol],
            "to": int(__import__("time").time()),
            "countBack": max(1, int(count)),
        }
    ).encode("utf-8")
    request = Request(
        _INDEX_HISTORY_URL,
        data=payload,
        headers=_HEADERS,
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        data = json.load(response)
    if isinstance(data, dict):
        data = data.get("data")
    if not isinstance(data, list) or not data:
        return {"close_prices": [], "volumes": [], "candles": []}

    entry = data[0]
    if not isinstance(entry, dict):
        return {"close_prices": [], "volumes": [], "candles": []}

    columns = ("o", "h", "l", "c", "v")
    if all(isinstance(entry.get(column), list) for column in columns):
        values = zip(*(entry[column][-count:] for column in columns))
        candles = [
            {
                "open": float(open_price),
                "high": float(high),
                "low": float(low),
                "close": float(close),
                "volume": float(volume),
            }
            for open_price, high, low, close, volume in values
        ]
    else:
        candles = [
            {
                "open": float(row["o"]),
                "high": float(row["h"]),
                "low": float(row["l"]),
                "close": float(row["c"]),
                "volume": float(row["v"]),
            }
            for row in data
            if isinstance(row, dict)
        ]

    return {
        "close_prices": [candle["close"] for candle in candles],
        "volumes": [candle["volume"] for candle in candles],
        "candles": candles,
    }
