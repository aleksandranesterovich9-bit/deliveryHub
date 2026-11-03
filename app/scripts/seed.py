"""Fill an empty database with demo data and create the admin user.

Run: python -m app.scripts.seed   (docker compose runs it automatically)
Idempotent: running it again does not create duplicates.
"""

import asyncio
import logging

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.security import hash_password
from app.db.models import Restaurant, User
from app.db.session import SessionFactory, engine
from app.domain.statuses import UserRole
from app.schemas.auth import normalize_phone

logger = logging.getLogger("app.seed")

DEMO_RESTAURANTS = ("Pizza House", "Sushi Master", "Burger Lab", "Green Bowl", "Pho Saigon")


async def seed() -> None:
    settings = get_settings()

    async with SessionFactory() as session:
        if settings.admin_phone and settings.admin_password:
            phone = normalize_phone(settings.admin_phone)
            if not await session.scalar(select(User.id).where(User.phone == phone)):
                session.add(
                    User(
                        name="Admin",
                        phone=phone,
                        password_hash=hash_password(settings.admin_password.get_secret_value()),
                        role=UserRole.ADMIN,
                    )
                )
                logger.info("Created admin %s", phone)

        if not await session.scalar(select(func.count()).select_from(Restaurant)):
            session.add_all(Restaurant(name=name) for name in DEMO_RESTAURANTS)
            logger.info("Created %d demo restaurants", len(DEMO_RESTAURANTS))

        await session.commit()


async def main() -> None:
    configure_logging(get_settings().log_level)
    try:
        await seed()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
