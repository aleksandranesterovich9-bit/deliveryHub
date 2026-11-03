"""Integration events: facts about what happened, published to RabbitMQ.

The routing key doubles as the event type. Consumers subscribe by pattern,
e.g. `order.*` receives both `order.created` and `order.cancelled`.
"""

from datetime import UTC, datetime
from typing import ClassVar
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.domain.statuses import DeliveryStatus


class Event(BaseModel):
    routing_key: ClassVar[str]

    event_id: UUID = Field(default_factory=uuid4)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OrderCreated(Event):
    routing_key: ClassVar[str] = "order.created"

    order_id: int
    user_id: int
    restaurant_id: int


class OrderCancelled(Event):
    routing_key: ClassVar[str] = "order.cancelled"

    order_id: int
    user_id: int


class DeliveryStatusChanged(Event):
    routing_key: ClassVar[str] = "delivery.status_changed"

    delivery_id: int
    order_id: int
    user_id: int
    old_status: DeliveryStatus
    new_status: DeliveryStatus


EVENT_TYPES: dict[str, type[Event]] = {
    cls.routing_key: cls for cls in (OrderCreated, OrderCancelled, DeliveryStatusChanged)
}


def parse_event(routing_key: str, body: bytes) -> Event:
    try:
        event_type = EVENT_TYPES[routing_key]
    except KeyError:
        raise ValueError(f"Unknown event type: {routing_key}") from None
    return event_type.model_validate_json(body)
