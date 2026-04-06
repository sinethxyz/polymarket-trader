"""Shared test fixtures for Polymarket trading system tests."""

from datetime import datetime, timezone

import pytest

from src.data.schemas import MarketState


@pytest.fixture
def sample_gamma_market() -> dict:
    """A realistic single market response from the Gamma API."""
    return {
        "id": "12345",
        "question": "Will Bitcoin exceed $100k by June 2026?",
        "outcomes": '["Yes","No"]',
        "outcomePrices": '["0.65","0.35"]',
        "active": True,
        "closed": False,
        "volume": "1500000.50",
        "liquidity": "250000.00",
        "endDate": "2026-06-30T00:00:00Z",
        "conditionId": "0xabc123",
        "slug": "will-bitcoin-exceed-100k-by-june-2026",
        "description": "Resolves Yes if BTC/USD exceeds $100,000.",
    }


@pytest.fixture
def sample_gamma_market_no_end_date(sample_gamma_market) -> dict:
    """Market with no resolution date."""
    return {**sample_gamma_market, "endDate": None}


@pytest.fixture
def sample_gamma_market_three_outcomes() -> dict:
    """A market with three outcomes (e.g., multi-choice)."""
    return {
        "id": "67890",
        "question": "Who will win the 2026 election?",
        "outcomes": '["Candidate A","Candidate B","Candidate C"]',
        "outcomePrices": '["0.45","0.35","0.20"]',
        "active": True,
        "closed": False,
        "volume": "5000000",
        "liquidity": "800000",
        "endDate": "2026-11-03T00:00:00Z",
        "conditionId": "0xdef456",
        "slug": "who-will-win-2026-election",
        "description": None,
    }


@pytest.fixture
def sample_markets_page(sample_gamma_market, sample_gamma_market_three_outcomes) -> list:
    """A page of market results (Gamma API returns a list)."""
    return [sample_gamma_market, sample_gamma_market_three_outcomes]


@pytest.fixture
def market_state() -> MarketState:
    """A MarketState domain object for store tests."""
    return MarketState(
        market_id="12345",
        question="Will Bitcoin exceed $100k by June 2026?",
        outcomes=["Yes", "No"],
        prices={"Yes": 0.65, "No": 0.35},
        volume=1500000.50,
        liquidity=250000.00,
        resolution_time=datetime(2026, 6, 30, 0, 0, 0, tzinfo=timezone.utc),
        active=True,
        closed=False,
        condition_id="0xabc123",
        slug="will-bitcoin-exceed-100k-by-june-2026",
    )
