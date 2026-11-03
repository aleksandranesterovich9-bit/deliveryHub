from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.statuses import DeliveryStatus, OrderStatus


class OrderCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    restaurant_id: int = Field(gt=0)
    dish: str = Field(min_length=1, max_length=100, examples=["Margherita"])
    quantity: int = Field(gt=0, le=50)
    delivery_address: str = Field(min_length=5, max_length=255, examples=["Lenina 1, apt. 5"])


class DeliveryBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: DeliveryStatus
    updated_at: datetime


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    restaurant_id: int
    dish: str
    quantity: int
    delivery_address: str
    status: OrderStatus
    created_at: datetime
    delivery: DeliveryBrief | None = Field(
        default=None,
        description="Appears a moment after the order is created: the worker creates it from the event.",
    )
