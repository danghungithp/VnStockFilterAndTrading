import json
from urllib.request import Request, urlopen


_LISTING_URL = "https://trading.vietcap.com.vn/api/price/symbols/getAll"
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
