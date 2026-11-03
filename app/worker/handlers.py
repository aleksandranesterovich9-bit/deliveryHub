"""Event handlers of the background worker.

RabbitMQ guarantees "at least once" delivery, so every handler must be
idempotent: processing the same event twice must give the same result.
"""

import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Delivery, Order
from app.domain.events import DeliveryStatusChanged, Event, OrderCancelled, OrderCreated
from app.domain.statuses import DeliveryStatus, OrderStatus

logger = logging.getLogger(__name__)

SessionFactory = async_sessionmaker[AsyncSession]


async def create_delivery_for_order(event: OrderCreated, session_factory: SessionFactory) -> None:
    async with session_factory() as session:
        order = await session.get(Order, event.order_id)
        if order is None:
            logger.warning("Order %s not found, skipping", event.order_id)
            return
        if order.status != OrderStatus.CREATED:
            logger.info("Order %s is already %s, no delivery needed", order.id, order.status)
            return

        if await session.scalar(select(Delivery.id).where(Delivery.order_id == order.id)):
            logger.info("Delivery for order %s already exists (duplicate event)", order.id)
            return

        session.add(Delivery(order_id=order.id, status=DeliveryStatus.PENDING))
        try:
            await session.commit()
        except IntegrityError:
            # Another worker instance created it at the same moment.
            logger.info("Delivery for order %s was created concurrently", order.id)
            return
        logger.info("Created delivery for order %s, looking for a courier", order.id)


def notification_text(event: Event) -> str | None:
    match event:
        case OrderCreated():
            return f"Order #{event.order_id} has been accepted"
        case OrderCancelled():
            return f"Order #{event.order_id} has been cancelled"
        case DeliveryStatusChanged():
            status = event.new_status.value.replace("_", " ")
            return f"Order #{event.order_id}: delivery is now {status}"
        case _:
            return None


async def send_notification(event: Event) -> None:
    # A real system would call an SMS / push / email provider here.
    if text := notification_text(event):
        user_id = getattr(event, "user_id", "?")
        logger.info("Notification to user #%s: %s", user_id, text)
