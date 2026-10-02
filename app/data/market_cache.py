import json
import os
import sqlite3
from pathlib import Path


_DEFAULT_CACHE_PATH = Path(__file__).resolve().parents[2] / "instance" / "market_data.sqlite3"


def _cache_path():
    configured = os.getenv("MARKET_DATA_CACHE_PATH", "").strip()
    if configured:
        return Path(configured).expanduser()
    if os.getenv("VERCEL"):
        return Path("/tmp/vnstock-market-data.sqlite3")
    return _DEFAULT_CACHE_PATH


def load_market_cache(cache_key):
    path = _cache_path()
    if not path.exists():
        return None

    try:
        with sqlite3.connect(path, timeout=5) as connection:
            row = connection.execute(
                """
                SELECT rows_json, source, universe_count, fetched_at
                FROM market_data_cache
                WHERE cache_key = ?
                """,
                (cache_key,),
            ).fetchone()
    except sqlite3.Error:
        return None

    if row is None:
        return None
    try:
        rows = json.loads(row[0])
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(rows, list):
        return None
    return {
        "rows": rows,
        "source": row[1],
        "universe_count": row[2],
        "fetched_at": row[3],
    }


def save_market_cache(cache_key, rows, source, universe_count, fetched_at):
    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(rows, ensure_ascii=False, allow_nan=False)

    with sqlite3.connect(path, timeout=10) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS market_data_cache (
                cache_key TEXT PRIMARY KEY,
                rows_json TEXT NOT NULL,
                source TEXT NOT NULL,
                universe_count INTEGER NOT NULL,
                fetched_at REAL NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO market_data_cache (
                cache_key, rows_json, source, universe_count, fetched_at
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                rows_json = excluded.rows_json,
                source = excluded.source,
                universe_count = excluded.universe_count,
                fetched_at = excluded.fetched_at
            """,
            (cache_key, payload, source, universe_count, fetched_at),
        )
