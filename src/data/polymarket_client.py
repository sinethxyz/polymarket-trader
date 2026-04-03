"""Polymarket Gamma API REST client.

Fetches market data from the public Gamma API. No authentication required
for read-only market queries. This is the data ingestion layer for V1.
"""

import logging
import time
from typing import Any, Optional

import httpx

from src.data.schemas import GammaMarketResponse, MarketState, parse_gamma_market

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://gamma-api.polymarket.com"
DEFAULT_TIMEOUT = 10.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_PAGE_SIZE = 100
DEFAULT_REQUEST_DELAY = 0.2
MAX_PAGES = 10  # Safety cap to prevent runaway pagination


class PolymarketAPIError(Exception):
    """Raised when the Polymarket API returns a non-retryable error."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Polymarket API error {status_code}: {message}")


class PolymarketClient:
    """Synchronous REST client for the Polymarket Gamma API.

    Usage:
        with PolymarketClient() as client:
            markets, cursor = client.get_active_markets(limit=50)
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        request_delay: float = DEFAULT_REQUEST_DELAY,
    ):
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self.request_delay = request_delay
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            headers={"Accept": "application/json"},
        )

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        self._client.close()

    def _request(self, method: str, path: str, **kwargs) -> Any:
        """Make an HTTP request with retry logic.

        Retries on: timeouts, 429 (rate limit), 5xx (server errors).
        No retry on: 4xx (except 429).
        Backoff: 1s, 2s, 4s (exponential).
        """
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                response = self._client.request(method, path, **kwargs)

                if response.status_code == 200:
                    return response.json()

                # Retryable server errors
                if response.status_code == 429 or response.status_code >= 500:
                    last_exception = PolymarketAPIError(
                        response.status_code, response.text
                    )
                    backoff = 2**attempt  # 1s, 2s, 4s
                    logger.warning(
                        "Retryable error %d on %s (attempt %d/%d), backing off %.1fs",
                        response.status_code,
                        path,
                        attempt + 1,
                        self.max_retries,
                        backoff,
                    )
                    time.sleep(backoff)
                    continue

                # Non-retryable client errors
                raise PolymarketAPIError(response.status_code, response.text)

            except httpx.TimeoutException as e:
                last_exception = e
                backoff = 2**attempt
                logger.warning(
                    "Timeout on %s (attempt %d/%d), backing off %.1fs",
                    path,
                    attempt + 1,
                    self.max_retries,
                    backoff,
                )
                time.sleep(backoff)
                continue

        # All retries exhausted
        if isinstance(last_exception, PolymarketAPIError):
            raise last_exception
        raise PolymarketAPIError(0, f"Request failed after {self.max_retries} retries: {last_exception}")

    def get_active_markets(
        self, limit: int = DEFAULT_PAGE_SIZE, cursor: Optional[str] = None
    ) -> tuple[list[MarketState], Optional[str]]:
        """Fetch a single page of active, non-closed markets.

        Returns:
            Tuple of (list of MarketState, next_cursor or None if last page).
        """
        params: dict[str, Any] = {
            "active": "true",
            "closed": "false",
            "limit": limit,
        }
        if cursor:
            params["next_cursor"] = cursor

        data = self._request("GET", "/markets", params=params)

        # Gamma API returns a list directly, with next_cursor in the response
        # if there are more pages. The exact pagination format may vary.
        markets_data = data if isinstance(data, list) else data.get("data", data)
        next_cursor = None
        if isinstance(data, dict):
            next_cursor = data.get("next_cursor")

        markets = []
        for item in markets_data:
            try:
                raw = GammaMarketResponse.model_validate(item)
                market = parse_gamma_market(raw)
                markets.append(market)
            except (ValueError, Exception) as e:
                # Skip markets with unparseable data rather than failing the whole batch
                logger.warning("Skipping market %s: %s", item.get("id", "unknown"), e)
                continue

        return markets, next_cursor

    def get_all_active_markets(self) -> list[MarketState]:
        """Fetch all active markets, paginating automatically.

        Safety cap: stops after MAX_PAGES pages to prevent runaway loops.
        """
        all_markets: list[MarketState] = []
        cursor = None

        for page in range(MAX_PAGES):
            markets, cursor = self.get_active_markets(cursor=cursor)
            all_markets.extend(markets)
            logger.debug("Fetched page %d: %d markets (total: %d)", page + 1, len(markets), len(all_markets))

            if not cursor or not markets:
                break

            time.sleep(self.request_delay)

        return all_markets

    def get_market(self, market_id: str) -> MarketState:
        """Fetch a single market by ID.

        Raises:
            PolymarketAPIError: If the market is not found or API fails.
            ValueError: If the market data cannot be parsed.
        """
        data = self._request("GET", f"/markets/{market_id}")
        raw = GammaMarketResponse.model_validate(data)
        return parse_gamma_market(raw)
