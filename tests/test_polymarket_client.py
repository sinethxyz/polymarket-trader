"""Tests for the PolymarketClient REST client."""

import httpx
import pytest
import respx

from src.data.polymarket_client import PolymarketAPIError, PolymarketClient


BASE_URL = "https://gamma-api.polymarket.com"


@pytest.fixture
def client():
    """Create a PolymarketClient with no retry delays for fast tests."""
    c = PolymarketClient(base_url=BASE_URL, max_retries=3, request_delay=0.0)
    yield c
    c.close()


class TestGetActiveMarkets:
    @respx.mock
    def test_success(self, client, sample_markets_page):
        respx.get(f"{BASE_URL}/markets").mock(
            return_value=httpx.Response(200, json=sample_markets_page)
        )

        markets, cursor = client.get_active_markets(limit=10)

        assert len(markets) == 2
        assert markets[0].market_id == "12345"
        assert markets[1].market_id == "67890"
        assert cursor is None  # List response has no cursor

    @respx.mock
    def test_pagination(self, client, sample_gamma_market, sample_gamma_market_three_outcomes):
        """Test get_all_active_markets paginates through multiple pages."""
        page1_response = {
            "data": [sample_gamma_market],
            "next_cursor": "cursor_page2",
        }
        page2_response = {
            "data": [sample_gamma_market_three_outcomes],
        }

        route = respx.get(f"{BASE_URL}/markets")
        route.side_effect = [
            httpx.Response(200, json=page1_response),
            httpx.Response(200, json=page2_response),
        ]

        markets = client.get_all_active_markets()

        assert len(markets) == 2
        assert markets[0].market_id == "12345"
        assert markets[1].market_id == "67890"

    @respx.mock
    def test_skips_unparseable_markets(self, client, sample_gamma_market):
        """Markets with bad data are skipped, not fatal."""
        bad_market = {**sample_gamma_market, "id": "bad", "outcomes": "not json"}
        respx.get(f"{BASE_URL}/markets").mock(
            return_value=httpx.Response(200, json=[sample_gamma_market, bad_market])
        )

        markets, _ = client.get_active_markets()

        assert len(markets) == 1
        assert markets[0].market_id == "12345"


class TestGetMarket:
    @respx.mock
    def test_success(self, client, sample_gamma_market):
        respx.get(f"{BASE_URL}/markets/12345").mock(
            return_value=httpx.Response(200, json=sample_gamma_market)
        )

        market = client.get_market("12345")

        assert market.market_id == "12345"
        assert market.question == "Will Bitcoin exceed $100k by June 2026?"

    @respx.mock
    def test_not_found(self, client):
        respx.get(f"{BASE_URL}/markets/nonexistent").mock(
            return_value=httpx.Response(404, text="Not Found")
        )

        with pytest.raises(PolymarketAPIError) as exc_info:
            client.get_market("nonexistent")

        assert exc_info.value.status_code == 404


class TestRetryBehavior:
    @respx.mock
    def test_retry_on_500_then_succeed(self, client, sample_gamma_market):
        route = respx.get(f"{BASE_URL}/markets/12345")
        route.side_effect = [
            httpx.Response(500, text="Internal Server Error"),
            httpx.Response(200, json=sample_gamma_market),
        ]

        market = client.get_market("12345")
        assert market.market_id == "12345"

    @respx.mock
    def test_retry_on_timeout_then_succeed(self, client, sample_gamma_market):
        route = respx.get(f"{BASE_URL}/markets/12345")
        route.side_effect = [
            httpx.ReadTimeout("timed out"),
            httpx.Response(200, json=sample_gamma_market),
        ]

        market = client.get_market("12345")
        assert market.market_id == "12345"

    @respx.mock
    def test_no_retry_on_400(self, client):
        route = respx.get(f"{BASE_URL}/markets/bad")
        route.mock(return_value=httpx.Response(400, text="Bad Request"))

        with pytest.raises(PolymarketAPIError) as exc_info:
            client.get_market("bad")

        assert exc_info.value.status_code == 400
        assert route.call_count == 1  # No retries

    @respx.mock
    def test_retry_exhausted(self, client):
        route = respx.get(f"{BASE_URL}/markets/12345")
        route.side_effect = [
            httpx.Response(500, text="error"),
            httpx.Response(500, text="error"),
            httpx.Response(500, text="error"),
        ]

        with pytest.raises(PolymarketAPIError) as exc_info:
            client.get_market("12345")

        assert exc_info.value.status_code == 500
        assert route.call_count == 3


class TestContextManager:
    def test_context_manager(self, sample_gamma_market):
        with respx.mock:
            respx.get(f"{BASE_URL}/markets/12345").mock(
                return_value=httpx.Response(200, json=sample_gamma_market)
            )

            with PolymarketClient(base_url=BASE_URL) as client:
                market = client.get_market("12345")
                assert market.market_id == "12345"
