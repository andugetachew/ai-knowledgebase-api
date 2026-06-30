import asyncio
import pytest
from unittest.mock import AsyncMock, patch

from app.services.rate_limiter import check_rate_limit


class FakeRedis:
    """In-memory fake that mimics atomic INCR behavior."""
    def __init__(self):
        self.store = {}
        self._lock = asyncio.Lock()

    async def incr(self, key):
        async with self._lock:
            self.store[key] = self.store.get(key, 0) + 1
            return self.store[key]

    async def expire(self, key, ttl):
        return True

    async def get(self, key):
        return str(self.store[key]) if key in self.store else None


@pytest.mark.asyncio
async def test_rate_limit_blocks_after_limit_reached():
    fake_redis = FakeRedis()
    with patch("app.services.rate_limiter.get_redis", return_value=fake_redis):
        for _ in range(10):
            result = await check_rate_limit("ws-1", "free")
            assert result["allowed"] is True

        # 11th request on free plan (limit=10) must be blocked
        result = await check_rate_limit("ws-1", "free")
        assert result["allowed"] is False
        assert result["remaining"] == 0


@pytest.mark.asyncio
async def test_rate_limit_concurrent_requests_never_exceed_limit():
    """
    Regression test for the TOCTOU race condition: fire 20 concurrent
    requests against a limit of 10 and assert exactly 10 are allowed.
    """
    fake_redis = FakeRedis()
    with patch("app.services.rate_limiter.get_redis", return_value=fake_redis):
        results = await asyncio.gather(*[
            check_rate_limit("ws-2", "free") for _ in range(20)
        ])

    allowed_count = sum(1 for r in results if r["allowed"])
    assert allowed_count == 10, f"Expected exactly 10 allowed, got {allowed_count}"


@pytest.mark.asyncio
async def test_rate_limit_pro_plan_has_higher_limit():
    fake_redis = FakeRedis()
    with patch("app.services.rate_limiter.get_redis", return_value=fake_redis):
        result = await check_rate_limit("ws-3", "pro")
        assert result["limit"] == 10000


@pytest.mark.asyncio
async def test_rate_limit_no_redis_allows_everything():
    with patch("app.services.rate_limiter.get_redis", return_value=None):
        result = await check_rate_limit("ws-4", "free")
        assert result["allowed"] is True