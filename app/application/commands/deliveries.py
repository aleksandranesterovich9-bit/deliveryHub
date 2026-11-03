from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictError, NotFoundError
from app.db.models import Delivery
from app.domain.events import DeliveryStatusChanged
from app.domain.statuses import DeliveryStatus, OrderStatus, can_change_delivery_status
from app.infrastructure.outbox import stage_event

# What happens to the order when its delivery reaches a final status.
_ORDER_STATUS_BY_DELIVERY_STATUS = {
    DeliveryStatus.DELIVERED: OrderStatus.COMPLETED,
    DeliveryStatus.CANCELLED: OrderStatus.CANCELLED,
}


@dataclass(frozen=True, slots=True)
class ChangeDeliveryStatus:
    delivery_id: int
    new_status: DeliveryStatus


async def handle_change_delivery_status(cmd: ChangeDeliveryStatus, session: AsyncSession) -> None:
    statement = select(Delivery).options(selectinload(Delivery.order)).where(Delivery.id == cmd.delivery_id)
    delivery = await session.scalar(statement)
    if delivery is None:
        raise NotFoundError("Delivery not found")

    old_status = delivery.status
    if not can_change_delivery_status(old_status, cmd.new_status):
        raise ConflictError(f"Cannot change delivery status from {old_status} to {cmd.new_status}")

    delivery.status = cmd.new_status
    if order_status := _ORDER_STATUS_BY_DELIVERY_STATUS.get(cmd.new_status):
        delivery.order.status = order_status

    stage_event(
        session,
        DeliveryStatusChanged(
            delivery_id=delivery.id,
            order_id=delivery.order_id,
            user_id=delivery.order.user_id,
            old_status=old_status,
            new_status=cmd.new_status,
        ),
    )
    await session.commit()
