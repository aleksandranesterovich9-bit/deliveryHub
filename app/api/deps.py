"""FastAPI dependencies: the only place that knows how to build handlers' inputs.

Tests replace `get_session` and `get_redis` via `app.dependency_overrides`.
"""

from collections.abc import AsyncIterator
from typing import Annotated

import jwt
from fastapi import Depends, Query, Request
from fastapi.security import OAuth2PasswordBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.security import decode_access_token
from app.db.models import User
from app.db.session import SessionFactory
from app.domain.statuses import UserRole
from app.infrastructure.cache import Cache
from app.infrastructure.rate_limiter import LoginRateLimiter


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        yield session


def get_redis(request: Request) -> Redis:
    return request.app.state.redis


SessionDep = Annotated[AsyncSession, Depends(get_session)]
RedisDep = Annotated[Redis, Depends(get_redis)]


def get_cache(redis: RedisDep) -> Cache:
    return Cache(redis, ttl_seconds=get_settings().cache_ttl_seconds)


def get_login_limiter(redis: RedisDep) -> LoginRateLimiter:
    settings = get_settings()
    return LoginRateLimiter(
        redis,
        max_attempts=settings.login_max_attempts,
        block_seconds=settings.login_block_seconds,
    )


CacheDep = Annotated[Cache, Depends(get_cache)]
LoginLimiterDep = Annotated[LoginRateLimiter, Depends(get_login_limiter)]

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], session: SessionDep) -> User:
    try:
        user_id = decode_access_token(token)
    except (jwt.InvalidTokenError, ValueError):
        raise AuthenticationError("Could not validate credentials") from None

    user = await session.get(User, user_id)
    if user is None:
        raise AuthenticationError("Could not validate credentials")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_admin(user: CurrentUser) -> User:
    if user.role != UserRole.ADMIN:
        raise PermissionDeniedError("Admin rights required")
    return user


AdminUser = Annotated[User, Depends(require_admin)]


class Pagination:
    def __init__(
        self,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> None:
        self.limit = limit
        self.offset = offset


PaginationDep = Annotated[Pagination, Depends()]
