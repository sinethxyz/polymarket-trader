"""Pydantic models for Polymarket API responses and domain objects."""

import json
import logging
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)


class GammaMarketResponse(BaseModel):
    """Raw response from the Polymarket Gamma API /markets endpoint.

    Maps 1:1 to the API JSON. Uses extra="ignore" so new fields
    added by Polymarket don't break parsing.
    """

    model_config = ConfigDict(extra="ignore")

    id: str
    question: str
    outcomes: str  # JSON-encoded string, e.g. '["Yes","No"]'
    outcomePrices: str  # JSON-encoded string, e.g. '["0.95","0.05"]'
    active: bool
    closed: bool
    volume: Optional[str] = None
    liquidity: Optional[str] = None
    endDate: Optional[str] = None
    conditionId: str
    slug: str
    description: Optional[str] = None


class MarketState(BaseModel):
    """Domain model representing a Polymarket market.

    This is what the rest of the system consumes. Downstream modules
    (market store, carry signal, etc.) should depend on this, not on
    the raw API response.
    """

    market_id: str
    question: str
    outcomes: list[str]
    prices: dict[str, float]  # outcome name -> mid price
    volume: float
    liquidity: float
    resolution_time: Optional[datetime] = None
    active: bool
    closed: bool
    condition_id: str
    slug: str


def parse_gamma_market(raw: GammaMarketResponse) -> MarketState:
    """Convert a raw Gamma API response into a MarketState domain object.

    Raises:
        ValueError: If outcomes/prices JSON is malformed or lengths don't match.
    """
    try:
        outcomes = json.loads(raw.outcomes)
    except (json.JSONDecodeError, TypeError) as e:
        raise ValueError(f"Failed to parse outcomes JSON: {raw.outcomes!r}") from e

    try:
        price_strings = json.loads(raw.outcomePrices)
    except (json.JSONDecodeError, TypeError) as e:
        raise ValueError(
            f"Failed to parse outcomePrices JSON: {raw.outcomePrices!r}"
        ) from e

    if len(outcomes) != len(price_strings):
        raise ValueError(
            f"Outcomes length ({len(outcomes)}) != prices length ({len(price_strings)})"
        )

    prices = {}
    for outcome, price_str in zip(outcomes, price_strings):
        try:
            prices[outcome] = float(price_str)
        except (ValueError, TypeError) as e:
            raise ValueError(
                f"Failed to parse price {price_str!r} for outcome {outcome!r}"
            ) from e

    resolution_time = None
    if raw.endDate:
        try:
            resolution_time = datetime.fromisoformat(raw.endDate)
        except ValueError:
            logger.warning("Could not parse endDate %r, setting resolution_time=None", raw.endDate)

    volume = float(raw.volume) if raw.volume else 0.0
    liquidity = float(raw.liquidity) if raw.liquidity else 0.0

    return MarketState(
        market_id=raw.id,
        question=raw.question,
        outcomes=outcomes,
        prices=prices,
        volume=volume,
        liquidity=liquidity,
        resolution_time=resolution_time,
        active=raw.active,
        closed=raw.closed,
        condition_id=raw.conditionId,
        slug=raw.slug,
    )
