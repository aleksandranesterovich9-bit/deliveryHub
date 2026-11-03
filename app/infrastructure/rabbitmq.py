"""RabbitMQ topology and publishing.

outbox relay ──► [exchange: delivery_hub.events (topic)]
                      │ order.created               ──► queue delivery_hub.deliveries
                      │ order.*, delivery.*         ──► queue delivery_hub.notifications
                      ▼
failed messages ──► [exchange: delivery_hub.dlx] ──► queue delivery_hub.dead_letters
"""

import asyncio
import logging
from dataclasses import dataclass

import aio_pika
from aio_pika.abc import (
    AbstractChannel,
    AbstractExchange,
    AbstractQueue,
    AbstractRobustConnection,
)

logger = logging.getLogger(__name__)

EVENTS_EXCHANGE = "delivery_hub.events"
DEAD_LETTER_EXCHANGE = "delivery_hub.dlx"

DELIVERIES_QUEUE = "delivery_hub.deliveries"
NOTIFICATIONS_QUEUE = "delivery_hub.notifications"
DEAD_LETTER_QUEUE = "delivery_hub.dead_letters"

QUEUE_BINDINGS: dict[str, tuple[str, ...]] = {
    DELIVERIES_QUEUE: ("order.created",),
    NOTIFICATIONS_QUEUE: ("order.*", "delivery.*"),
}


@dataclass(frozen=True)
class Topology:
    exchange: AbstractExchange
    queues: dict[str, AbstractQueue]


async def connect(url: str, attempts: int = 10, delay_seconds: float = 3.0) -> AbstractRobustConnection:
    """Connect with retries: on `docker compose up` RabbitMQ may still be starting.

    A robust connection also reconnects by itself if the broker restarts later.
    """
    for attempt in range(1, attempts + 1):
        try:
            return await aio_pika.connect_robust(url)
        except (ConnectionError, aio_pika.exceptions.AMQPConnectionError):
            if attempt == attempts:
                raise
            logger.warning("RabbitMQ is not available (attempt %d/%d), retrying...", attempt, attempts)
            await asyncio.sleep(delay_seconds)
    raise AssertionError("unreachable")


async def declare_topology(channel: AbstractChannel) -> Topology:
    """Declare exchanges, queues and bindings. Safe to call many times (idempotent).

    Both the publisher and the consumer call it, so no message is lost
    because the queues did not exist yet when the first event was published.
    """
    dlx = await channel.declare_exchange(DEAD_LETTER_EXCHANGE, aio_pika.ExchangeType.FANOUT, durable=True)
    dead_letters = await channel.declare_queue(DEAD_LETTER_QUEUE, durable=True)
    await dead_letters.bind(dlx)

    exchange = await channel.declare_exchange(EVENTS_EXCHANGE, aio_pika.ExchangeType.TOPIC, durable=True)

    queues: dict[str, AbstractQueue] = {DEAD_LETTER_QUEUE: dead_letters}
    for queue_name, routing_keys in QUEUE_BINDINGS.items():
        queue = await channel.declare_queue(
            queue_name,
            durable=True,
            # A message rejected by a consumer goes to the dead-letter exchange
            # instead of being lost or re-delivered forever.
            arguments={"x-dead-letter-exchange": DEAD_LETTER_EXCHANGE},
        )
        for routing_key in routing_keys:
            await queue.bind(exchange, routing_key=routing_key)
        queues[queue_name] = queue

    return Topology(exchange=exchange, queues=queues)


class RabbitMQPublisher:
    def __init__(self, exchange: AbstractExchange) -> None:
        self._exchange = exchange

    async def publish(self, routing_key: str, body: bytes, message_id: str) -> None:
        message = aio_pika.Message(
            body=body,
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,  # survives a broker restart
            message_id=message_id,
            type=routing_key,
        )
        # The channel uses publisher confirms (aio-pika default), so this
        # returns only after RabbitMQ has accepted the message.
        await self._exchange.publish(message, routing_key=routing_key)
