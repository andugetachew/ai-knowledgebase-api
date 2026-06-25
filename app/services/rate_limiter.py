from datetime import datetime, UTC
from app.db.redis import get_redis


PLAN_LIMITS = {
    "free": 10,
    "pro": 10000,
}


async def check_rate_limit(workspace_id: str, plan: str) -> dict:
    """
    Returns {"allowed": True/False, "remaining": int, "limit": int}
    Uses Redis to count queries per day per workspace.
    """
    redis = get_redis()
    if not redis:
        return {"allowed": True, "remaining": 999, "limit": 999}

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    key = f"rate:{workspace_id}:{today}"
    limit = PLAN_LIMITS.get(plan, 10)

    current = await redis.get(key)
    count = int(current) if current else 0

    if count >= limit:
        return {"allowed": False, "remaining": 0, "limit": limit}

    new_count = await redis.incr(key)
    await redis.expire(key, 86400)  # expires in 24 hours

    return {
        "allowed": True,
        "remaining": max(0, limit - new_count),
        "limit": limit,
    }


async def get_query_count_today(workspace_id: str) -> int:
    redis = get_redis()
    if not redis:
        return 0
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    key = f"rate:{workspace_id}:{today}"
    current = await redis.get(key)
    return int(current) if current else 0