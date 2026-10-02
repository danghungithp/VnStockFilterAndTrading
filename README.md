---
title: VnStockFilterAndTrading
sdk: docker
app_port: 7860
---

# VnStockFilterAndTrading

## Market data

The app loads the HOSE/HNX listing from the same public Vietcap VCI endpoint used by Vnstock, then requests daily price history from Yahoo Finance through `yfinance`. This avoids requiring Vnstock's non-public `vnai` dependency in deployment images. `MARKET_DATA_PROVIDER=yahoo` is the recommended setting; the old value `alphavantage` is accepted as an alias for Yahoo so existing `.env` files keep working. Live mode never substitutes mock prices: listing failures, unsupported symbols, or Yahoo/network errors produce an `unavailable` status and no recommendations. Select `MARKET_DATA_PROVIDER=mock` explicitly to use demo data. Successful snapshots are cached in memory and SQLite for six hours by default; the SQLite database is stored under `instance/market_data.sqlite3` and survives application restarts.

Configure the provider in `.env`:

```bash
MARKET_DATA_PROVIDER=yahoo
YAHOO_TICKER_SUFFIX=VN
YAHOO_MAX_SYMBOLS=5
```

Yahoo symbols default to the `.VN` suffix (for example, `FPT.VN`); set `YAHOO_HNX_SUFFIX=HN` only if the desired HNX listing uses `.HN`. By default, the app tries the first five symbols from the Vnstock listing. Set `YAHOO_SYMBOLS` to restrict the watchlist and `YAHOO_MAX_SYMBOLS` to adjust the request limit. Yahoo may not cover every Vietnamese ticker; the dashboard reports unavailable instead of showing mock prices when no live quotes can be loaded. Set `MARKET_DATA_PROVIDER=mock` to explicitly use demo data.

Use **Cập nhật dữ liệu** to bypass the TTL and fetch new history from Yahoo. If Yahoo is unavailable, the app keeps the last SQLite snapshot and marks it stale; it never presents stale prices as freshly loaded. Set `MARKET_DATA_CACHE_TTL` to change the cache lifetime in seconds or `MARKET_DATA_CACHE_PATH` to move the SQLite file.

Use the stock-symbol search on the dashboard to analyze one listed HOSE/HNX symbol, for example `FPT`. The app validates it against the Vietcap listing, fetches only that Yahoo history, and runs the existing trend, mean-reversion, Kelly, stop-loss, and take-profit analysis. Each symbol has its own SQLite cache entry.

The analysis also reports cup-and-handle, double-bottom, double-top, head-and-shoulders, morning-star, and inverse-head-and-shoulders setups. Cup-and-handle and morning-star signals require a 1.5x 20-session average-volume confirmation; reversal patterns remain watch signals until their neckline breaks, and inverse head-and-shoulders also requires lower right-shoulder volume. These are rule-based technical-pattern heuristics, not fundamental valuation or guaranteed forecasts.

The recommendations page accepts an investment amount and calculates per-symbol amounts from the displayed half-Kelly allocation percentage. Allocation is capped per position and may leave some capital uninvested. Stop and target prices are volatility estimates, not guarantees or a substitute for a personal risk plan.

## Deploy to Vercel

The Flask application is exposed as a Python serverless function from `api/index.py`; `vercel.json` rewrites page and API routes to that function. Deploy from the repository root with the Vercel CLI (`vercel` for preview or `vercel --prod` for production).

Set these project environment variables in Vercel before production use:

```text
MARKET_DATA_PROVIDER=yahoo
YAHOO_TICKER_SUFFIX=VN
YAHOO_MAX_SYMBOLS=5
MARKET_DATA_CACHE_TTL=21600
```

Yahoo Finance does not require an API key. Vercel's `/tmp` SQLite cache is ephemeral and local to a serverless instance; it can speed warm requests but is not durable or shared between instances. Use external persistent storage if a shared cache across cold starts/instances is required. Yahoo/Vnstock network availability and the Vercel plan's function timeout/rate limits still apply.

## Deploy to Hugging Face Spaces

This repository includes a Docker Space configuration. Create a new Space with the **Docker** SDK, then push this repository to that Space's Git remote. Spaces builds `Dockerfile` and serves Flask on port `7860` with debug disabled.

In Space Settings, add variables:

```text
MARKET_DATA_PROVIDER=yahoo
YAHOO_TICKER_SUFFIX=VN
YAHOO_MAX_SYMBOLS=5
MARKET_DATA_CACHE_TTL=21600
```

Yahoo Finance needs no API key. The default SQLite cache is inside the container and may be lost when the Space restarts. If persistent storage is enabled and mounted at `/data`, set `MARKET_DATA_CACHE_PATH=/data/market_data.sqlite3` in the Space variables.
