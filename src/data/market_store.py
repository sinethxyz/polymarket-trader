"""SQLite-backed market state store for V1 carry logic.

Persists MarketState snapshots so the carry signal module can query
markets near resolution without re-fetching from the Gamma API.

No ORM — uses stdlib sqlite3 directly.
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.data.schemas import MarketState

logger = logging.getLogger(__name__)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS markets (
    market_id       TEXT PRIMARY KEY,
    question        TEXT NOT NULL,
    outcomes        TEXT NOT NULL,
    prices          TEXT NOT NULL,
    volume          REAL NOT NULL DEFAULT 0.0,
    liquidity       REAL NOT NULL DEFAULT 0.0,
    resolution_time TEXT,
    active          INTEGER NOT NULL,
    closed          INTEGER NOT NULL,
    condition_id    TEXT NOT NULL,
    slug            TEXT NOT NULL,
    last_fetched_at TEXT NOT NULL
);
"""

_CREATE_INDEX_RESOLUTION = """
CREATE INDEX IF NOT EXISTS idx_markets_resolution_time
    ON markets (resolution_time)
    WHERE resolution_time IS NOT NULL AND active = 1 AND closed = 0;
"""

_UPSERT_SQL = """
INSERT INTO markets (
    market_id, question, outcomes, prices, volume, liquidity,
    resolution_time, active, closed, condition_id, slug, last_fetched_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(market_id) DO UPDATE SET
    question        = excluded.question,
    outcomes        = excluded.outcomes,
    prices          = excluded.prices,
    volume          = excluded.volume,
    liquidity       = excluded.liquidity,
    resolution_time = excluded.resolution_time,
    active          = excluded.active,
    closed          = excluded.closed,
    condition_id    = excluded.condition_id,
    slug            = excluded.slug,
    last_fetched_at = excluded.last_fetched_at;
"""

_SELECT_BY_ID = "SELECT * FROM markets WHERE market_id = ?;"

_SELECT_NEAR_RESOLUTION = """
SELECT * FROM markets
WHERE active = 1
  AND closed = 0
  AND resolution_time IS NOT NULL
  AND resolution_time > strftime('%Y-%m-%dT%H:%M:%S', 'now')
  AND resolution_time <= strftime('%Y-%m-%dT%H:%M:%S', 'now', ? || ' hours')
ORDER BY resolution_time ASC;
"""

_SELECT_ALL_ACTIVE = """
SELECT * FROM markets
WHERE active = 1 AND closed = 0
ORDER BY resolution_time ASC;
"""

_COUNT = "SELECT COUNT(*) FROM markets;"

_DELETE = "DELETE FROM markets WHERE market_id = ?;"


def _normalize_resolution_time(dt: Optional[datetime]) -> Optional[str]:
    """Convert datetime to naive UTC ISO-8601 string for SQLite storage."""
    if dt is None:
        return None
    utc_dt = dt.astimezone(timezone.utc) if dt.tzinfo else dt
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%S")


def _row_to_market_state(row: sqlite3.Row) -> MarketState:
    """Reconstruct a MarketState from a database row."""
    resolution_time = None
    if row["resolution_time"] is not None:
        resolution_time = datetime.fromisoformat(row["resolution_time"])

    return MarketState(
        market_id=row["market_id"],
        question=row["question"],
        outcomes=json.loads(row["outcomes"]),
        prices=json.loads(row["prices"]),
        volume=row["volume"],
        liquidity=row["liquidity"],
        resolution_time=resolution_time,
        active=bool(row["active"]),
        closed=bool(row["closed"]),
        condition_id=row["condition_id"],
        slug=row["slug"],
    )


def _market_to_params(market: MarketState, now_utc: str) -> tuple:
    """Convert a MarketState to a tuple of SQL parameters for upsert."""
    return (
        market.market_id,
        market.question,
        json.dumps(market.outcomes),
        json.dumps(market.prices),
        market.volume,
        market.liquidity,
        _normalize_resolution_time(market.resolution_time),
        int(market.active),
        int(market.closed),
        market.condition_id,
        market.slug,
        now_utc,
    )


class MarketStore:
    """SQLite-backed store for MarketState snapshots."""

    def __init__(self, db_path: str | Path = "data/markets.db") -> None:
        """Open or create the SQLite database and initialize schema.

        Args:
            db_path: Path to the SQLite database file.
                     Use ":memory:" for in-memory databases (tests).
        """
        db_path_str = str(db_path)
        if db_path_str != ":memory:":
            Path(db_path_str).parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(db_path_str)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute(_CREATE_TABLE)
        self._conn.execute(_CREATE_INDEX_RESOLUTION)
        self._conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    def __enter__(self) -> "MarketStore":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def upsert(self, market: MarketState) -> None:
        """Insert or update a single market. Sets last_fetched_at to UTC now."""
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        self._conn.execute(_UPSERT_SQL, _market_to_params(market, now_utc))
        self._conn.commit()

    def upsert_many(self, markets: list[MarketState]) -> None:
        """Upsert a batch of markets in a single transaction."""
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        params = [_market_to_params(m, now_utc) for m in markets]
        self._conn.executemany(_UPSERT_SQL, params)
        self._conn.commit()

    def get(self, market_id: str) -> Optional[MarketState]:
        """Fetch a single market by ID. Returns None if not found."""
        row = self._conn.execute(_SELECT_BY_ID, (market_id,)).fetchone()
        if row is None:
            return None
        return _row_to_market_state(row)

    def get_near_resolution(self, within_hours: float = 48.0) -> list[MarketState]:
        """Return active, non-closed markets resolving within the given window.

        Markets with no resolution_time or resolution_time in the past
        are excluded.
        """
        hours_str = f"+{within_hours}"
        rows = self._conn.execute(_SELECT_NEAR_RESOLUTION, (hours_str,)).fetchall()
        return [_row_to_market_state(row) for row in rows]

    def get_all_active(self) -> list[MarketState]:
        """Return all markets where active=True and closed=False."""
        rows = self._conn.execute(_SELECT_ALL_ACTIVE).fetchall()
        return [_row_to_market_state(row) for row in rows]

    def count(self) -> int:
        """Total number of rows in the markets table."""
        row = self._conn.execute(_COUNT).fetchone()
        return row[0]

    def delete(self, market_id: str) -> bool:
        """Remove a market by ID. Returns True if a row was deleted."""
        cursor = self._conn.execute(_DELETE, (market_id,))
        self._conn.commit()
        return cursor.rowcount > 0
