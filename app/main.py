from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from redis.asyncio import Redis

from app.api.errors import register_exception_handlers
from app.api.routes import auth, deliveries, health, orders, restaurants
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import engine

DESCRIPTION = """
Food delivery backend: restaurants, orders and deliveries.

* **CQRS** — write operations are commands, read operations are queries.
* **Redis** — cache for restaurants and brute-force protection for login.
* **RabbitMQ** — order and delivery events, delivered via a transactional outbox
  and processed by a background worker.

To try protected endpoints: register, then press **Authorize** and log in
with your phone as the username.
"""


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.redis = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        # Fail fast: a slow cache must not make the whole API slow.
        socket_timeout=2,
        socket_connect_timeout=2,
    )
    yield
    await app.state.redis.aclose()
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=f"{settings.app_name} API", version="1.0.0", description=DESCRIPTION, lifespan=lifespan
    )
    register_exception_handlers(app)

    for module in (auth, restaurants, orders, deliveries, health):
        app.include_router(module.router)

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse("/docs")

    return app


app = create_app()
