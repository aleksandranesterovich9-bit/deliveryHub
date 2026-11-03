import json
import logging
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class Cache:
    """JSON cache on top of Redis.

    The cache is an optimisation, not a source of truth: if Redis is down,
    every method degrades to a cache miss instead of failing the request.

    Invalidation uses *versioned namespaces*: keys look like
    `restaurants:v7:list:...`. Bumping the version makes all old keys
    unreachable at once (they expire by TTL), which is much cheaper and
    safer than searching and deleting keys by pattern.
    """

    def __init__(self, redis: Redis, ttl_seconds: int) -> None:
        self._redis = redis
        self._ttl = ttl_seconds

    async def get_json(self, key: str) -> Any | None:
        try:
            raw = await self._redis.get(key)
        except RedisError:
            logger.warning("Redis unavailable, cache read skipped for %s", key)
            return None
        return None if raw is None else json.loads(raw)

    async def set_json(self, key: str, value: Any) -> None:
        try:
            await self._redis.set(key, json.dumps(value), ex=self._ttl)
        except RedisError:
            logger.warning("Redis unavailable, cache write skipped for %s", key)

    async def namespace_version(self, namespace: str) -> int:
        try:
            return int(await self._redis.get(f"{namespace}:version") or 0)
        except RedisError:
            logger.warning("Redis unavailable, using default version for %s", namespace)
            return 0

    async def invalidate_namespace(self, namespace: str) -> None:
        try:
            await self._redis.incr(f"{namespace}:version")
        except RedisError:
            # Stale data will live at most `ttl_seconds`.
            logger.warning("Redis unavailable, could not invalidate %s", namespace)
