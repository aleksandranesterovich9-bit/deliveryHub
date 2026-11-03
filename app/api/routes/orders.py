from fastapi import APIRouter, status

from app.api.deps import CurrentUser, PaginationDep, SessionDep
from app.application.commands.orders import (
    CancelOrder,
    CreateOrder,
    handle_cancel_order,
    handle_create_order,
)
from app.application.queries.orders import GetOrder, ListOrders, handle_get_order, handle_list_orders
from app.domain.statuses import OrderStatus, UserRole
from app.schemas.orders import OrderCreate, OrderRead

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.post("", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def create_order(body: OrderCreate, session: SessionDep, user: CurrentUser) -> OrderRead:
    """Creates the order and an `order.created` event.

    The delivery is created asynchronously by the worker, so right after
    creation `delivery` is `null` — request the order again a second later.
    """
    command = CreateOrder(user_id=user.id, **body.model_dump())
    order_id = await handle_create_order(command, session)
    return await handle_get_order(GetOrder(order_id, viewer_id=user.id), session)


@router.get("", response_model=list[OrderRead])
async def list_orders(
    session: SessionDep,
    user: CurrentUser,
    page: PaginationDep,
    restaurant_id: int | None = None,
    order_status: OrderStatus | None = None,
) -> list[OrderRead]:
    """Your orders (admins see all orders)."""
    query = ListOrders(
        viewer_id=user.id,
        viewer_is_admin=user.role == UserRole.ADMIN,
        restaurant_id=restaurant_id,
        status=order_status,
        limit=page.limit,
        offset=page.offset,
    )
    return await handle_list_orders(query, session)


@router.get("/{order_id}", response_model=OrderRead)
async def get_order(order_id: int, session: SessionDep, user: CurrentUser) -> OrderRead:
    query = GetOrder(order_id, viewer_id=user.id, viewer_is_admin=user.role == UserRole.ADMIN)
    return await handle_get_order(query, session)


@router.post("/{order_id}/cancel", response_model=OrderRead)
async def cancel_order(order_id: int, session: SessionDep, user: CurrentUser) -> OrderRead:
    """Allowed while the courier has not taken the order yet."""
    is_admin = user.role == UserRole.ADMIN
    await handle_cancel_order(CancelOrder(order_id, user_id=user.id, is_admin=is_admin), session)
    return await handle_get_order(GetOrder(order_id, viewer_id=user.id, viewer_is_admin=is_admin), session)
