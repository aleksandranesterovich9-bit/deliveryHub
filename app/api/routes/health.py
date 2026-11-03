import logging

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.api.deps import RedisDep, SessionDep

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health(session: SessionDep, redis: RedisDep, response: Response) -> dict[str, str]:
    """Used by Docker healthcheck. Returns 503 if a dependency is down."""
    checks: dict[str, str] = {}

    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        logger.exception("Database health check failed")
        checks["database"] = "unavailable"

    try:
        await redis.ping()
        checks["redis"] = "ok"
    except Exception:
        logger.exception("Redis health check failed")
        checks["redis"] = "unavailable"

    healthy = all(value == "ok" for value in checks.values())
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok" if healthy else "degraded", **checks}
