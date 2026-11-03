from fastapi import APIRouter

from app.api.deps import AdminUser, PaginationDep, SessionDep
from app.application.commands.deliveries import (
    ChangeDeliveryStatus,
    handle_change_delivery_status,
)
from app.application.queries.deliveries import (
    GetDelivery,
    ListDeliveries,
    handle_get_delivery,
    handle_list_deliveries,
)
from app.domain.statuses import DeliveryStatus
from app.schemas.deliveries import DeliveryRead, DeliveryStatusUpdate

router = APIRouter(prefix="/deliveries", tags=["Deliveries"])


@router.get("", response_model=list[DeliveryRead])
async def list_deliveries(
    session: SessionDep,
    _: AdminUser,
    page: PaginationDep,
    delivery_status: DeliveryStatus | None = None,
) -> list[DeliveryRead]:
    query = ListDeliveries(status=delivery_status, limit=page.limit, offset=page.offset)
    return await handle_list_deliveries(query, session)


@router.patch("/{delivery_id}/status", response_model=DeliveryRead)
async def change_delivery_status(
    delivery_id: int, body: DeliveryStatusUpdate, session: SessionDep, _: AdminUser
) -> DeliveryRead:
    """pending → courier_assigned → in_transit → delivered (or pending → cancelled)."""
    await handle_change_delivery_status(ChangeDeliveryStatus(delivery_id, body.status), session)
    return await handle_get_delivery(GetDelivery(delivery_id), session)
