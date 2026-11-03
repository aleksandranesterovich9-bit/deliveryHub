import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class LoginRateLimiter:
    """Brute-force protection: block a phone after N failed logins for a while.

    Redis keeps a counter `login_failures:<phone>` with a TTL. The TTL starts
    on the first failure, so the user is unblocked automatically.
    If Redis is unavailable we *fail open* (allow login) to avoid locking
    everyone out because of a cache outage.
    """

    def __init__(self, redis: Redis, max_attempts: int, block_seconds: int) -> None:
        self._redis = redis
        self._max_attempts = max_attempts
        self._block_seconds = block_seconds

    @staticmethod
    def _key(phone: str) -> str:
        return f"login_failures:{phone}"

    async def seconds_until_unblocked(self, phone: str) -> int:
        """0 means login is allowed."""
        key = self._key(phone)
        try:
            attempts = await self._redis.get(key)
            if attempts is None or int(attempts) < self._max_attempts:
                return 0
            return max(await self._redis.ttl(key), 1)
        except RedisError:
            logger.warning("Redis unavailable, login rate limit skipped")
            return 0

    async def register_failure(self, phone: str) -> None:
        key = self._key(phone)
        try:
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.incr(key)
                pipe.expire(key, self._block_seconds, nx=True)
                await pipe.execute()
        except RedisError:
            logger.warning("Redis unavailable, failed login not counted")

    async def reset(self, phone: str) -> None:
        try:
            await self._redis.delete(self._key(phone))
        except RedisError:
            logger.warning("Redis unavailable, login counter not reset")
