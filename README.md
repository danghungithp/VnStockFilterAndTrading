# VnStockFilterAndTrading

## Market data

The app uses Vnstock only to load the HOSE/HNX stock listing, then requests daily price history from Yahoo Finance through `yfinance`. `MARKET_DATA_PROVIDER=yahoo` is the recommended setting; the old value `alphavantage` is accepted as an alias for Yahoo so existing `.env` files keep working. Live mode never substitutes mock prices: listing failures, unsupported symbols, or Yahoo/network errors produce an `unavailable` status and no recommendations. Select `MARKET_DATA_PROVIDER=mock` explicitly to use demo data. Successful snapshots are cached in memory and SQLite for six hours by default; the SQLite database is stored under `instance/market_data.sqlite3` and survives application restarts.

Configure the provider in `.env`:

```bash
MARKET_DATA_PROVIDER=yahoo
YAHOO_TICKER_SUFFIX=VN
YAHOO_MAX_SYMBOLS=5
```

Yahoo symbols default to the `.VN` suffix (for example, `FPT.VN`); set `YAHOO_HNX_SUFFIX=HN` only if the desired HNX listing uses `.HN`. By default, the app tries the first five symbols from the Vnstock listing. Set `YAHOO_SYMBOLS` to restrict the watchlist and `YAHOO_MAX_SYMBOLS` to adjust the request limit. Yahoo may not cover every Vietnamese ticker; the dashboard reports unavailable instead of showing mock prices when no live quotes can be loaded. Set `MARKET_DATA_PROVIDER=mock` to explicitly use demo data.

Use **Cập nhật dữ liệu** to bypass the TTL and fetch new history from Yahoo. If Yahoo is unavailable, the app keeps the last SQLite snapshot and marks it stale; it never presents stale prices as freshly loaded. Set `MARKET_DATA_CACHE_TTL` to change the cache lifetime in seconds or `MARKET_DATA_CACHE_PATH` to move the SQLite file.

Use the stock-symbol search on the dashboard to analyze one listed HOSE/HNX symbol, for example `FPT`. The app validates it against the Vnstock listing, fetches only that Yahoo history, and runs the existing trend, mean-reversion, Kelly, stop-loss, and take-profit analysis. Each symbol has its own SQLite cache entry.

The analysis also reports cup-and-handle, double-bottom, double-top, head-and-shoulders, morning-star, and inverse-head-and-shoulders setups. Cup-and-handle and morning-star signals require a 1.5x 20-session average-volume confirmation; reversal patterns remain watch signals until their neckline breaks, and inverse head-and-shoulders also requires lower right-shoulder volume. These are rule-based technical-pattern heuristics, not fundamental valuation or guaranteed forecasts.

The recommendations page accepts an investment amount and calculates per-symbol amounts from the displayed half-Kelly allocation percentage. Allocation is capped per position and may leave some capital uninvested. Stop and target prices are volatility estimates, not guarantees or a substitute for a personal risk plan.
