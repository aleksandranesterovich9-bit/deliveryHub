from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictError, NotFoundError
from app.db.models import Order, Restaurant
from app.domain.events import OrderCancelled, OrderCreated
from app.domain.statuses import DeliveryStatus, OrderStatus
from app.infrastructure.outbox import stage_event


@dataclass(frozen=True, slots=True)
class CreateOrder:
    user_id: int
    restaurant_id: int
    dish: str
    quantity: int
    delivery_address: str


async def handle_create_order(cmd: CreateOrder, session: AsyncSession) -> int:
    if await session.get(Restaurant, cmd.restaurant_id) is None:
        raise NotFoundError("Restaurant not found")

    order = Order(
        user_id=cmd.user_id,
        restaurant_id=cmd.restaurant_id,
        dish=cmd.dish,
        quantity=cmd.quantity,
        delivery_address=cmd.delivery_address,
        status=OrderStatus.CREATED,
    )
    session.add(order)
    await session.flush()  # sends INSERT, so the DB assigns order.id; nothing is committed yet

    # Same transaction as the order: either both are saved or neither.
    stage_event(
        session,
        OrderCreated(order_id=order.id, user_id=order.user_id, restaurant_id=order.restaurant_id),
    )
    await session.commit()
    return order.id


@dataclass(frozen=True, slots=True)
class CancelOrder:
    order_id: int
    user_id: int
    is_admin: bool = False


async def handle_cancel_order(cmd: CancelOrder, session: AsyncSession) -> None:
    statement = select(Order).options(selectinload(Order.delivery)).where(Order.id == cmd.order_id)
    order = await session.scalar(statement)
    # Someone else's order looks exactly like a missing one: don't leak which ids exist.
    if order is None or (order.user_id != cmd.user_id and not cmd.is_admin):
        raise NotFoundError("Order not found")

    if order.status != OrderStatus.CREATED:
        raise ConflictError(f"Order is already {order.status}")
    if order.delivery is not None and order.delivery.status != DeliveryStatus.PENDING:
        raise ConflictError("The courier has already taken the order, it cannot be cancelled")

    order.status = OrderStatus.CANCELLED
    if order.delivery is not None:
        order.delivery.status = DeliveryStatus.CANCELLED

    stage_event(session, OrderCancelled(order_id=order.id, user_id=order.user_id))
    await session.commit()
