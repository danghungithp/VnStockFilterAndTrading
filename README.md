# VnStockFilterAndTrading

## Live market data

The app now includes a live market-data adapter for public quote APIs. The implementation will try to fetch live prices from a configured provider and automatically fall back to the bundled mock dataset if the provider is unavailable or an API key has not been configured.

Example environment configuration:

```bash
export ALPHA_VANTAGE_API_KEY="your_key_here"
export MARKET_DATA_PROVIDER="alphavantage"
```

If no live provider is configured, the app keeps working with the built-in mock market dataset so local development remains stable.
