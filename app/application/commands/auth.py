from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, ConflictError, TooManyRequestsError
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import User
from app.domain.statuses import UserRole
from app.infrastructure.rate_limiter import LoginRateLimiter


@dataclass(frozen=True, slots=True)
class RegisterUser:
    name: str
    phone: str
    password: str


async def handle_register_user(cmd: RegisterUser, session: AsyncSession) -> int:
    if await session.scalar(select(User.id).where(User.phone == cmd.phone)):
        raise ConflictError("User with this phone already exists")

    user = User(
        name=cmd.name,
        phone=cmd.phone,
        password_hash=hash_password(cmd.password),
        role=UserRole.CUSTOMER,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        # Two simultaneous registrations with the same phone: the unique
        # constraint in the DB is the final guard.
        await session.rollback()
        raise ConflictError("User with this phone already exists") from None
    return user.id


@dataclass(frozen=True, slots=True)
class LoginUser:
    phone: str
    password: str


async def handle_login(cmd: LoginUser, session: AsyncSession, limiter: LoginRateLimiter) -> str:
    """Returns a JWT access token."""
    if retry_after := await limiter.seconds_until_unblocked(cmd.phone):
        raise TooManyRequestsError("Too many failed login attempts, try again later", retry_after)

    user = await session.scalar(select(User).where(User.phone == cmd.phone))
    if not verify_password(cmd.password, user.password_hash if user else None):
        await limiter.register_failure(cmd.phone)
        raise AuthenticationError("Incorrect phone number or password")

    await limiter.reset(cmd.phone)
    return create_access_token(user.id)
