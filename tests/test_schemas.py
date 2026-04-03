"""Tests for Pydantic schemas and the parse_gamma_market conversion function."""

from datetime import datetime, timezone

import pytest

from src.data.schemas import GammaMarketResponse, MarketState, parse_gamma_market


class TestParseGammaMarket:
    def test_basic_two_outcome_market(self, sample_gamma_market):
        raw = GammaMarketResponse.model_validate(sample_gamma_market)
        market = parse_gamma_market(raw)

        assert isinstance(market, MarketState)
        assert market.market_id == "12345"
        assert market.question == "Will Bitcoin exceed $100k by June 2026?"
        assert market.outcomes == ["Yes", "No"]
        assert market.prices == {"Yes": 0.65, "No": 0.35}
        assert market.volume == 1500000.50
        assert market.liquidity == 250000.00
        assert market.resolution_time == datetime(2026, 6, 30, 0, 0, 0, tzinfo=timezone.utc)
        assert market.active is True
        assert market.closed is False
        assert market.condition_id == "0xabc123"
        assert market.slug == "will-bitcoin-exceed-100k-by-june-2026"

    def test_null_end_date(self, sample_gamma_market_no_end_date):
        raw = GammaMarketResponse.model_validate(sample_gamma_market_no_end_date)
        market = parse_gamma_market(raw)

        assert market.resolution_time is None

    def test_three_outcome_market(self, sample_gamma_market_three_outcomes):
        raw = GammaMarketResponse.model_validate(sample_gamma_market_three_outcomes)
        market = parse_gamma_market(raw)

        assert market.outcomes == ["Candidate A", "Candidate B", "Candidate C"]
        assert market.prices == {"Candidate A": 0.45, "Candidate B": 0.35, "Candidate C": 0.20}

    def test_malformed_outcomes_json(self, sample_gamma_market):
        sample_gamma_market["outcomes"] = "not valid json"
        raw = GammaMarketResponse.model_validate(sample_gamma_market)

        with pytest.raises(ValueError, match="Failed to parse outcomes JSON"):
            parse_gamma_market(raw)

    def test_malformed_prices_json(self, sample_gamma_market):
        sample_gamma_market["outcomePrices"] = "{bad}"
        raw = GammaMarketResponse.model_validate(sample_gamma_market)

        with pytest.raises(ValueError, match="Failed to parse outcomePrices JSON"):
            parse_gamma_market(raw)

    def test_mismatched_outcomes_and_prices_length(self, sample_gamma_market):
        sample_gamma_market["outcomes"] = '["Yes","No","Maybe"]'
        sample_gamma_market["outcomePrices"] = '["0.5","0.5"]'
        raw = GammaMarketResponse.model_validate(sample_gamma_market)

        with pytest.raises(ValueError, match="Outcomes length .* != prices length"):
            parse_gamma_market(raw)

    def test_extra_fields_ignored(self, sample_gamma_market):
        """API may add new fields — they should not break parsing."""
        sample_gamma_market["newField"] = "surprise"
        sample_gamma_market["anotherNewField"] = 42

        raw = GammaMarketResponse.model_validate(sample_gamma_market)
        market = parse_gamma_market(raw)

        assert market.market_id == "12345"

    def test_null_volume_and_liquidity(self, sample_gamma_market):
        sample_gamma_market["volume"] = None
        sample_gamma_market["liquidity"] = None
        raw = GammaMarketResponse.model_validate(sample_gamma_market)
        market = parse_gamma_market(raw)

        assert market.volume == 0.0
        assert market.liquidity == 0.0
