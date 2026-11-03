from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.db.models import Order
from app.domain.statuses import OrderStatus
from app.schemas.orders import OrderRead


@dataclass(frozen=True, slots=True)
class GetOrder:
    order_id: int
    viewer_id: int
    viewer_is_admin: bool = False


async def handle_get_order(query: GetOrder, session: AsyncSession) -> OrderRead:
    statement = (
        select(Order)
        .options(selectinload(Order.delivery))
        .where(Order.id == query.order_id)
        # The order may already be in the session (e.g. right after a command
        # in the same request): reload it so we always return fresh data.
        .execution_options(populate_existing=True)
    )
    if not query.viewer_is_admin:
        statement = statement.where(Order.user_id == query.viewer_id)

    order = await session.scalar(statement)
    if order is None:
        raise NotFoundError("Order not found")
    return OrderRead.model_validate(order)


@dataclass(frozen=True, slots=True)
class ListOrders:
    viewer_id: int
    viewer_is_admin: bool = False
    restaurant_id: int | None = None
    status: OrderStatus | None = None
    limit: int = 20
    offset: int = 0


async def handle_list_orders(query: ListOrders, session: AsyncSession) -> list[OrderRead]:
    """Customers see their own orders, admins see everything."""
    statement = (
        select(Order)
        .options(selectinload(Order.delivery))
        .order_by(Order.id.desc())
        .limit(query.limit)
        .offset(query.offset)
    )
    if not query.viewer_is_admin:
        statement = statement.where(Order.user_id == query.viewer_id)
    if query.restaurant_id is not None:
        statement = statement.where(Order.restaurant_id == query.restaurant_id)
    if query.status is not None:
        statement = statement.where(Order.status == query.status)

    return [OrderRead.model_validate(order) for order in await session.scalars(statement)]
