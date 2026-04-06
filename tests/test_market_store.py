"""Tests for the SQLite-backed market state store."""

from datetime import datetime, timedelta, timezone

import pytest

from src.data.market_store import MarketStore
from src.data.schemas import MarketState


@pytest.fixture
def store():
    """In-memory MarketStore for tests."""
    with MarketStore(":memory:") as s:
        yield s


def _make_market(
    market_id: str = "12345",
    resolution_time: datetime | None = datetime(2026, 6, 30, 0, 0, 0, tzinfo=timezone.utc),
    active: bool = True,
    closed: bool = False,
    **overrides,
) -> MarketState:
    """Helper to build MarketState with sensible defaults."""
    fields = dict(
        market_id=market_id,
        question="Will Bitcoin exceed $100k by June 2026?",
        outcomes=["Yes", "No"],
        prices={"Yes": 0.65, "No": 0.35},
        volume=1500000.50,
        liquidity=250000.00,
        resolution_time=resolution_time,
        active=active,
        closed=closed,
        condition_id="0xabc123",
        slug="will-bitcoin-exceed-100k-by-june-2026",
    )
    fields.update(overrides)
    return MarketState(**fields)


class TestMarketStoreInit:
    """Tests for store initialization."""

    def test_creates_table_on_init(self, store):
        row = store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='markets';"
        ).fetchone()
        assert row is not None

    def test_creates_index(self, store):
        row = store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_markets_resolution_time';"
        ).fetchone()
        assert row is not None

    def test_idempotent_init(self):
        """Creating a store twice on the same DB does not error."""
        with MarketStore(":memory:") as s1:
            # Re-run DDL manually to simulate double init
            s1._conn.execute(
                "CREATE TABLE IF NOT EXISTS markets ("
                "market_id TEXT PRIMARY KEY, question TEXT NOT NULL, "
                "outcomes TEXT NOT NULL, prices TEXT NOT NULL, "
                "volume REAL NOT NULL DEFAULT 0.0, liquidity REAL NOT NULL DEFAULT 0.0, "
                "resolution_time TEXT, active INTEGER NOT NULL, closed INTEGER NOT NULL, "
                "condition_id TEXT NOT NULL, slug TEXT NOT NULL, last_fetched_at TEXT NOT NULL);"
            )
            assert s1.count() == 0


class TestUpsert:
    """Tests for single market upsert."""

    def test_insert_new_market(self, store, market_state):
        store.upsert(market_state)
        result = store.get(market_state.market_id)
        assert result is not None
        assert result.market_id == market_state.market_id

    def test_update_existing_market(self, store, market_state):
        store.upsert(market_state)

        updated = market_state.model_copy(update={"prices": {"Yes": 0.90, "No": 0.10}})
        store.upsert(updated)

        result = store.get(market_state.market_id)
        assert result.prices == {"Yes": 0.90, "No": 0.10}
        assert store.count() == 1

    def test_upsert_sets_last_fetched_at(self, store, market_state):
        store.upsert(market_state)
        row = store._conn.execute(
            "SELECT last_fetched_at FROM markets WHERE market_id = ?;",
            (market_state.market_id,),
        ).fetchone()
        assert row["last_fetched_at"] is not None
        # Should be a valid ISO-8601 string
        datetime.fromisoformat(row["last_fetched_at"])

    def test_round_trips_all_fields(self, store, market_state):
        store.upsert(market_state)
        result = store.get(market_state.market_id)

        assert result.market_id == market_state.market_id
        assert result.question == market_state.question
        assert result.outcomes == market_state.outcomes
        assert result.prices == market_state.prices
        assert result.volume == market_state.volume
        assert result.liquidity == market_state.liquidity
        assert result.active == market_state.active
        assert result.closed == market_state.closed
        assert result.condition_id == market_state.condition_id
        assert result.slug == market_state.slug

    def test_round_trips_resolution_time(self, store, market_state):
        """resolution_time survives write/read (normalized to naive UTC)."""
        store.upsert(market_state)
        result = store.get(market_state.market_id)
        # Stored as naive UTC, so compare without tzinfo
        expected = market_state.resolution_time.replace(tzinfo=None)
        assert result.resolution_time == expected

    def test_null_resolution_time(self, store):
        market = _make_market(resolution_time=None)
        store.upsert(market)
        result = store.get(market.market_id)
        assert result.resolution_time is None


class TestUpsertMany:
    """Tests for batch upsert."""

    def test_batch_insert(self, store):
        markets = [_make_market(market_id=f"m{i}") for i in range(3)]
        store.upsert_many(markets)
        assert store.count() == 3

    def test_batch_upsert_updates_existing(self, store):
        m1 = _make_market(market_id="m1")
        store.upsert(m1)

        m1_updated = _make_market(market_id="m1", volume=999.0)
        m2 = _make_market(market_id="m2")
        store.upsert_many([m1_updated, m2])

        assert store.count() == 2
        assert store.get("m1").volume == 999.0

    def test_empty_batch(self, store):
        store.upsert_many([])
        assert store.count() == 0


class TestGet:
    """Tests for single market retrieval."""

    def test_get_existing(self, store, market_state):
        store.upsert(market_state)
        result = store.get(market_state.market_id)
        assert result is not None
        assert isinstance(result, MarketState)

    def test_get_nonexistent(self, store):
        assert store.get("nonexistent") is None

    def test_json_fields_survive_round_trip(self, store):
        market = _make_market(
            outcomes=["Candidate A", "Candidate B", "Candidate C"],
            prices={"Candidate A": 0.45, "Candidate B": 0.35, "Candidate C": 0.20},
        )
        store.upsert(market)
        result = store.get(market.market_id)
        assert result.outcomes == ["Candidate A", "Candidate B", "Candidate C"]
        assert result.prices == {"Candidate A": 0.45, "Candidate B": 0.35, "Candidate C": 0.20}


class TestGetNearResolution:
    """Tests for querying markets near resolution."""

    def _insert_market_at_offset(self, store, market_id, hours_from_now, **kwargs):
        """Insert a market resolving `hours_from_now` hours in the future."""
        resolution = datetime.now(timezone.utc) + timedelta(hours=hours_from_now)
        market = _make_market(market_id=market_id, resolution_time=resolution, **kwargs)
        store.upsert(market)
        return market

    def test_returns_markets_within_48h(self, store):
        self._insert_market_at_offset(store, "near", 24)
        results = store.get_near_resolution(within_hours=48.0)
        assert len(results) == 1
        assert results[0].market_id == "near"

    def test_excludes_markets_beyond_window(self, store):
        self._insert_market_at_offset(store, "far", 72)
        results = store.get_near_resolution(within_hours=48.0)
        assert len(results) == 0

    def test_excludes_markets_with_no_resolution_time(self, store):
        market = _make_market(market_id="no-time", resolution_time=None)
        store.upsert(market)
        results = store.get_near_resolution()
        assert len(results) == 0

    def test_excludes_closed_markets(self, store):
        self._insert_market_at_offset(store, "closed", 24, closed=True)
        results = store.get_near_resolution()
        assert len(results) == 0

    def test_excludes_inactive_markets(self, store):
        self._insert_market_at_offset(store, "inactive", 24, active=False)
        results = store.get_near_resolution()
        assert len(results) == 0

    def test_excludes_past_resolution_time(self, store):
        self._insert_market_at_offset(store, "past", -2)
        results = store.get_near_resolution()
        assert len(results) == 0

    def test_custom_within_hours(self, store):
        self._insert_market_at_offset(store, "m1", 12)
        self._insert_market_at_offset(store, "m2", 36)

        results_24h = store.get_near_resolution(within_hours=24.0)
        assert len(results_24h) == 1
        assert results_24h[0].market_id == "m1"

        results_48h = store.get_near_resolution(within_hours=48.0)
        assert len(results_48h) == 2

    def test_ordered_by_resolution_time(self, store):
        self._insert_market_at_offset(store, "later", 36)
        self._insert_market_at_offset(store, "sooner", 12)
        results = store.get_near_resolution(within_hours=48.0)
        assert results[0].market_id == "sooner"
        assert results[1].market_id == "later"


class TestGetAllActive:
    """Tests for get_all_active."""

    def test_returns_active_non_closed(self, store):
        store.upsert(_make_market(market_id="active"))
        store.upsert(_make_market(market_id="closed", closed=True))
        store.upsert(_make_market(market_id="inactive", active=False))

        results = store.get_all_active()
        ids = [m.market_id for m in results]
        assert "active" in ids
        assert "closed" not in ids
        assert "inactive" not in ids


class TestDelete:
    """Tests for market deletion."""

    def test_delete_existing(self, store, market_state):
        store.upsert(market_state)
        assert store.delete(market_state.market_id) is True
        assert store.get(market_state.market_id) is None

    def test_delete_nonexistent(self, store):
        assert store.delete("nonexistent") is False


class TestContextManager:
    """Tests for context manager usage."""

    def test_context_manager_opens_and_closes(self):
        with MarketStore(":memory:") as store:
            store.upsert(_make_market())
            assert store.count() == 1
        # Connection is closed after exiting context
