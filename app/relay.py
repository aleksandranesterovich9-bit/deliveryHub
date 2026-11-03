"""Outbox relay: moves staged events from the `outbox` table to RabbitMQ.

Run: python -m app.relay
"""

import asyncio
import contextlib
import logging

from app.core.config import get_settings
from app.core.lifecycle import install_shutdown_handlers
from app.core.logging import configure_logging
from app.db.session import SessionFactory, engine
from app.infrastructure import rabbitmq
from app.infrastructure.outbox import OutboxRelay

logger = logging.getLogger("app.relay")


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)

    stop = asyncio.Event()
    install_shutdown_handlers(stop)

    connection = await rabbitmq.connect(settings.rabbitmq_url)
    async with connection:
        channel = await connection.channel()  # publisher confirms are on by default
        topology = await rabbitmq.declare_topology(channel)
        relay = OutboxRelay(
            SessionFactory,
            rabbitmq.RabbitMQPublisher(topology.exchange),
            batch_size=settings.outbox_batch_size,
        )
        await relay.run(stop, poll_interval_seconds=settings.outbox_poll_interval_seconds)

    await engine.dispose()


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
