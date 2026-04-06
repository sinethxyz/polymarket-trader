"""Validate Gamma API response shape against V1 field assumptions.

This is a diagnostic tool for catching API drift early. It operates on
raw dicts (before Pydantic parsing) and returns warnings instead of raising.
parse_gamma_market() remains the runtime gate for bad data.
"""

import json
from datetime import datetime


# Fields that must be present and non-None in every Gamma market response.
_REQUIRED_FIELDS = ("id", "question", "outcomes", "outcomePrices", "active", "closed", "conditionId", "slug")


def validate_gamma_response_shape(raw: dict) -> list[str]:
    """Check a raw Gamma API market dict against V1 field assumptions.

    Returns a list of warnings. Empty list means all checks passed.
    Does not raise.
    """
    warnings: list[str] = []

    # 1. Required fields present
    for field in _REQUIRED_FIELDS:
        if field not in raw or raw[field] is None:
            warnings.append(f"missing or null required field: {field}")

    # Short-circuit if critical fields are missing — further checks would fail
    if warnings:
        return warnings

    # 2. Type checks
    if not isinstance(raw["active"], bool):
        warnings.append(f"expected 'active' to be bool, got {type(raw['active']).__name__}")
    if not isinstance(raw["closed"], bool):
        warnings.append(f"expected 'closed' to be bool, got {type(raw['closed']).__name__}")
    if not isinstance(raw["outcomes"], str):
        warnings.append(f"expected 'outcomes' to be str, got {type(raw['outcomes']).__name__}")
    if not isinstance(raw["outcomePrices"], str):
        warnings.append(f"expected 'outcomePrices' to be str, got {type(raw['outcomePrices']).__name__}")

    # 3. JSON-parseable outcomes and prices
    parsed_outcomes = None
    parsed_prices = None

    if isinstance(raw["outcomes"], str):
        try:
            parsed_outcomes = json.loads(raw["outcomes"])
            if not isinstance(parsed_outcomes, list):
                warnings.append(f"expected 'outcomes' JSON to be a list, got {type(parsed_outcomes).__name__}")
                parsed_outcomes = None
        except (json.JSONDecodeError, TypeError):
            warnings.append(f"'outcomes' is not valid JSON: {raw['outcomes']!r}")

    if isinstance(raw["outcomePrices"], str):
        try:
            parsed_prices = json.loads(raw["outcomePrices"])
            if not isinstance(parsed_prices, list):
                warnings.append(f"expected 'outcomePrices' JSON to be a list, got {type(parsed_prices).__name__}")
                parsed_prices = None
        except (json.JSONDecodeError, TypeError):
            warnings.append(f"'outcomePrices' is not valid JSON: {raw['outcomePrices']!r}")

    # 4. Length match
    if parsed_outcomes is not None and parsed_prices is not None:
        if len(parsed_outcomes) != len(parsed_prices):
            warnings.append(
                f"outcomes length ({len(parsed_outcomes)}) != outcomePrices length ({len(parsed_prices)})"
            )

    # 5. Prices are numeric strings
    if parsed_prices is not None:
        for i, p in enumerate(parsed_prices):
            try:
                float(p)
            except (ValueError, TypeError):
                warnings.append(f"outcomePrices[{i}] is not numeric: {p!r}")

    # 6. endDate parseable as ISO-8601 if present
    end_date = raw.get("endDate")
    if end_date is not None:
        if not isinstance(end_date, str):
            warnings.append(f"expected 'endDate' to be str, got {type(end_date).__name__}")
        else:
            try:
                datetime.fromisoformat(end_date)
            except ValueError:
                warnings.append(f"'endDate' is not valid ISO-8601: {end_date!r}")

    # 7. volume/liquidity castable to float if present
    for field in ("volume", "liquidity"):
        val = raw.get(field)
        if val is not None:
            try:
                float(val)
            except (ValueError, TypeError):
                warnings.append(f"'{field}' is not numeric: {val!r}")

    return warnings


def validate_gamma_batch(markets: list[dict]) -> dict[str, list[str]]:
    """Run shape validation on a batch of raw Gamma API dicts.

    Returns {market_id: [warnings]} for markets with any warnings.
    Empty dict means all markets passed validation.
    """
    results: dict[str, list[str]] = {}
    for market in markets:
        market_id = market.get("id", f"unknown-{id(market)}")
        warnings = validate_gamma_response_shape(market)
        if warnings:
            results[str(market_id)] = warnings
    return results
