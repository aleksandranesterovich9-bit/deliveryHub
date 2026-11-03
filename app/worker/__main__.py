"""Background worker: consumes events from RabbitMQ.

Run: python -m app.worker
"""

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from functools import partial

from aio_pika.abc import AbstractIncomingMessage

from app.core.config import get_settings
from app.core.lifecycle import install_shutdown_handlers
from app.core.logging import configure_logging
from app.db.session import SessionFactory, engine
from app.domain.events import Event, OrderCreated, parse_event
from app.infrastructure import rabbitmq
from app.worker.handlers import create_delivery_for_order, send_notification

logger = logging.getLogger("app.worker")

EventHandler = Callable[[Event], Awaitable[None]]


async def on_create_delivery(event: Event) -> None:
    if isinstance(event, OrderCreated):
        await create_delivery_for_order(event, SessionFactory)


async def consume(message: AbstractIncomingMessage, handler: EventHandler) -> None:
    try:
        # requeue=False: if the handler fails, the message is rejected and,
        # thanks to x-dead-letter-exchange, lands in the dead-letter queue
        # where it can be inspected instead of being retried in an endless loop.
        async with message.process(requeue=False):
            event = parse_event(message.routing_key or "", message.body)
            await handler(event)
    except Exception:
        logger.exception(
            "Failed to process %s (message_id=%s), sent to dead-letter queue",
            message.routing_key,
            message.message_id,
        )


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)

    stop = asyncio.Event()
    install_shutdown_handlers(stop)

    connection = await rabbitmq.connect(settings.rabbitmq_url)
    async with connection:
        channel = await connection.channel()
        # Do not give this worker more than 10 unacknowledged messages at once.
        await channel.set_qos(prefetch_count=10)
        topology = await rabbitmq.declare_topology(channel)

        consumers: dict[str, EventHandler] = {
            rabbitmq.DELIVERIES_QUEUE: on_create_delivery,
            rabbitmq.NOTIFICATIONS_QUEUE: send_notification,
        }
        for queue_name, handler in consumers.items():
            await topology.queues[queue_name].consume(partial(consume, handler=handler))

        logger.info("Worker started, listening to: %s", ", ".join(consumers))
        await stop.wait()

    await engine.dispose()
    logger.info("Worker stopped")


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
