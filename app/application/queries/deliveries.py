from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models import Delivery
from app.domain.statuses import DeliveryStatus
from app.schemas.deliveries import DeliveryRead


@dataclass(frozen=True, slots=True)
class ListDeliveries:
    status: DeliveryStatus | None = None
    limit: int = 20
    offset: int = 0


async def handle_list_deliveries(query: ListDeliveries, session: AsyncSession) -> list[DeliveryRead]:
    statement = select(Delivery).order_by(Delivery.id.desc()).limit(query.limit).offset(query.offset)
    if query.status is not None:
        statement = statement.where(Delivery.status == query.status)
    return [DeliveryRead.model_validate(d) for d in await session.scalars(statement)]


@dataclass(frozen=True, slots=True)
class GetDelivery:
    delivery_id: int


async def handle_get_delivery(query: GetDelivery, session: AsyncSession) -> DeliveryRead:
    statement = (
        select(Delivery).where(Delivery.id == query.delivery_id).execution_options(populate_existing=True)
    )
    delivery = await session.scalar(statement)
    if delivery is None:
        raise NotFoundError("Delivery not found")
    return DeliveryRead.model_validate(delivery)
