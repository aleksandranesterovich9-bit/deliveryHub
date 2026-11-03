import os

# Settings are read on import, so configure the environment before importing the app.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough-for-hs256"
os.environ["LOGIN_MAX_ATTEMPTS"] = "3"

from collections.abc import AsyncIterator

import pytest
from fakeredis import FakeAsyncRedis
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.api.deps import get_redis, get_session
from app.core.security import hash_password
from app.db.models import OutboxMessage, User
from app.db.session import Base
from app.domain.statuses import UserRole
from app.main import create_app

# Run against real Postgres with e.g.
# TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/test pytest
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")

PASSWORD = "very-secret-password"


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    if TEST_DATABASE_URL.startswith("sqlite"):
        # One shared in-memory database for all connections of the test.
        engine = create_async_engine(TEST_DATABASE_URL, poolclass=StaticPool)
    else:
        engine = create_async_engine(TEST_DATABASE_URL)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
async def redis() -> AsyncIterator[FakeAsyncRedis]:
    client = FakeAsyncRedis(decode_responses=True)
    yield client
    await client.flushall()
    await client.aclose()


@pytest.fixture
async def client(session_factory, redis) -> AsyncIterator[AsyncClient]:
    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_redis] = lambda: redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def _login(client: AsyncClient, phone: str, password: str = PASSWORD) -> dict[str, str]:
    response = await client.post("/auth/login", data={"username": phone, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def login():
    return _login


@pytest.fixture
def register(client: AsyncClient):
    async def _register(phone: str, name: str = "Test User") -> dict[str, str]:
        response = await client.post(
            "/auth/register", json={"name": name, "phone": phone, "password": PASSWORD}
        )
        assert response.status_code == 201, response.text
        return await _login(client, phone)

    return _register


@pytest.fixture
async def customer(register) -> dict[str, str]:
    """Auth headers of a regular customer."""
    return await register("+70000000001", name="Customer")


@pytest.fixture
async def other_customer(register) -> dict[str, str]:
    return await register("+70000000002", name="Other Customer")


@pytest.fixture
async def admin(client: AsyncClient, session_factory) -> dict[str, str]:
    """Auth headers of an admin (admins can't self-register, so create one in the DB)."""
    async with session_factory() as session:
        session.add(
            User(
                name="Admin", phone="+79990000000", password_hash=hash_password(PASSWORD), role=UserRole.ADMIN
            )
        )
        await session.commit()
    return await _login(client, "+79990000000")


@pytest.fixture
async def restaurant(client: AsyncClient, admin) -> dict:
    response = await client.post("/restaurants", json={"name": "Pizza House"}, headers=admin)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def order_payload(restaurant) -> dict:
    return {
        "restaurant_id": restaurant["id"],
        "dish": "Margherita",
        "quantity": 2,
        "delivery_address": "Lenina 1, apt. 5",
    }


@pytest.fixture
def outbox_events(session_factory):
    """Returns routing keys of events staged in the outbox, in order."""

    async def _events() -> list[str]:
        async with session_factory() as session:
            rows = await session.scalars(select(OutboxMessage).order_by(OutboxMessage.id))
            return [row.routing_key for row in rows]

    return _events
