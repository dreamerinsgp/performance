"""
Locust load test for DEX core APIs.
Targets: get_candlestick, get_token_info, index_trending, get_trade_list.
"""
import random
import time
from locust import HttpUser, task, between


class DEXCoreAPIs(HttpUser):
    """Simulate users hitting core market APIs."""
    wait_time = between(0.5, 2)

    # Sample pair for Solana (Pump.fun style). Replace with real pair if available.
    SAMPLE_PAIRS = [
        "6nsxY6RfHnFJn1nMj4AoR4cMhALj5hNX1x1nA5aJ3KPp",
        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    ]

    @task(3)
    def get_candlestick(self):
        """GET /v1/market/get_candlestick - Kline data."""
        now = int(time.time())
        pair = random.choice(self.SAMPLE_PAIRS)
        self.client.get(
            "/v1/market/get_candlestick",
            params={
                "chain_id": 100000,
                "pair_address": pair,
                "interval": "1m",
                "from_timestamp": now - 3600,
                "to_timestamp": now,
                "limit": 60,
            },
            name="/v1/market/get_candlestick",
        )

    @task(2)
    def get_token_info(self):
        """GET /v1/market/get_token_info - Token market info."""
        pair = random.choice(self.SAMPLE_PAIRS)
        self.client.get(
            "/v1/market/get_token_info",
            params={
                "chain_id": 100000,
                "pair_address": pair,
            },
            name="/v1/market/get_token_info",
        )

    @task(4)
    def index_trending(self):
        """GET /v1/market/index_trending - Trending tokens (whitelisted, no auth)."""
        self.client.get(
            "/v1/market/index_trending",
            name="/v1/market/index_trending",
        )

    @task(2)
    def get_trade_list(self):
        """GET /v1/market/get_trade_list - Latest trades."""
        pair = random.choice(self.SAMPLE_PAIRS)
        self.client.get(
            "/v1/market/get_trade_list",
            params={
                "chain_id": 100000,
                "pair_address": pair,
            },
            name="/v1/market/get_trade_list",
        )

    @task(1)
    def search(self):
        """GET /v1/market/search - Search (whitelisted)."""
        self.client.get(
            "/v1/market/search",
            params={"keyword": "sol"},
            name="/v1/market/search",
        )
