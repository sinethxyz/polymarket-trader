"""Tests for Gamma API response shape validation."""

import pytest

from src.data.gamma_validator import validate_gamma_batch, validate_gamma_response_shape


class TestValidateGammaResponseShape:
    """Tests for validate_gamma_response_shape."""

    def test_valid_market_returns_no_warnings(self, sample_gamma_market):
        warnings = validate_gamma_response_shape(sample_gamma_market)
        assert warnings == []

    @pytest.mark.parametrize("field", [
        "id", "question", "outcomes", "outcomePrices",
        "active", "closed", "conditionId", "slug",
    ])
    def test_missing_required_field(self, sample_gamma_market, field):
        market = {**sample_gamma_market}
        del market[field]
        warnings = validate_gamma_response_shape(market)
        assert any(field in w for w in warnings)

    @pytest.mark.parametrize("field", [
        "id", "question", "outcomes", "outcomePrices",
        "active", "closed", "conditionId", "slug",
    ])
    def test_null_required_field(self, sample_gamma_market, field):
        market = {**sample_gamma_market, field: None}
        warnings = validate_gamma_response_shape(market)
        assert any(field in w for w in warnings)

    def test_wrong_type_active(self, sample_gamma_market):
        market = {**sample_gamma_market, "active": "true"}
        warnings = validate_gamma_response_shape(market)
        assert any("active" in w and "bool" in w for w in warnings)

    def test_wrong_type_closed(self, sample_gamma_market):
        market = {**sample_gamma_market, "closed": 0}
        warnings = validate_gamma_response_shape(market)
        assert any("closed" in w and "bool" in w for w in warnings)

    def test_unparseable_outcomes_json(self, sample_gamma_market):
        market = {**sample_gamma_market, "outcomes": "not json"}
        warnings = validate_gamma_response_shape(market)
        assert any("outcomes" in w and "JSON" in w for w in warnings)

    def test_unparseable_prices_json(self, sample_gamma_market):
        market = {**sample_gamma_market, "outcomePrices": "{bad}"}
        warnings = validate_gamma_response_shape(market)
        assert any("outcomePrices" in w and "JSON" in w for w in warnings)

    def test_mismatched_lengths(self, sample_gamma_market):
        market = {**sample_gamma_market, "outcomePrices": '["0.65"]'}
        warnings = validate_gamma_response_shape(market)
        assert any("length" in w for w in warnings)

    def test_non_numeric_price(self, sample_gamma_market):
        market = {**sample_gamma_market, "outcomePrices": '["0.65","abc"]'}
        warnings = validate_gamma_response_shape(market)
        assert any("not numeric" in w for w in warnings)

    def test_invalid_end_date_format(self, sample_gamma_market):
        market = {**sample_gamma_market, "endDate": "not-a-date"}
        warnings = validate_gamma_response_shape(market)
        assert any("endDate" in w for w in warnings)

    def test_null_optional_fields_ok(self, sample_gamma_market):
        market = {**sample_gamma_market, "endDate": None, "volume": None, "liquidity": None}
        warnings = validate_gamma_response_shape(market)
        assert warnings == []

    def test_non_numeric_volume(self, sample_gamma_market):
        market = {**sample_gamma_market, "volume": "lots"}
        warnings = validate_gamma_response_shape(market)
        assert any("volume" in w and "not numeric" in w for w in warnings)

    def test_three_outcome_market_valid(self, sample_gamma_market_three_outcomes):
        warnings = validate_gamma_response_shape(sample_gamma_market_three_outcomes)
        assert warnings == []


class TestValidateGammaBatch:
    """Tests for validate_gamma_batch."""

    def test_all_clean_returns_empty_dict(self, sample_gamma_market):
        result = validate_gamma_batch([sample_gamma_market])
        assert result == {}

    def test_mixed_batch_returns_only_bad_markets(self, sample_gamma_market):
        bad_market = {**sample_gamma_market, "id": "bad-1", "outcomes": "not json"}
        result = validate_gamma_batch([sample_gamma_market, bad_market])
        assert "bad-1" in result
        assert "12345" not in result

    def test_empty_batch(self):
        result = validate_gamma_batch([])
        assert result == {}
