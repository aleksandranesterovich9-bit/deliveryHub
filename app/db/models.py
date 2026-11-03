from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base, utc_now
from app.domain.statuses import DeliveryStatus, OrderStatus, UserRole


def _str_enum(enum_cls: type[StrEnum]) -> Enum:
    # Stored as VARCHAR with enum *values* ("in_transit"), not names ("IN_TRANSIT"):
    # adding a new status later does not require ALTER TYPE.
    return Enum(
        enum_cls,
        native_enum=False,
        length=20,
        values_callable=lambda members: [member.value for member in members],
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, server_default=func.now()
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(20), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(_str_enum(UserRole), default=UserRole.CUSTOMER)


class Restaurant(TimestampMixin, Base):
    __tablename__ = "restaurants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)


class Order(TimestampMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (CheckConstraint("quantity > 0", name="quantity_positive"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("restaurants.id"), index=True)
    dish: Mapped[str] = mapped_column(String(100))
    quantity: Mapped[int] = mapped_column(Integer)
    delivery_address: Mapped[str] = mapped_column(String(255))
    status: Mapped[OrderStatus] = mapped_column(
        _str_enum(OrderStatus), default=OrderStatus.CREATED, index=True
    )

    # lazy="raise": in async code an accidental lazy load is a bug, so fail loudly.
    # Load it explicitly with selectinload(Order.delivery) where needed.
    delivery: Mapped["Delivery | None"] = relationship(back_populates="order", lazy="raise")


class Delivery(TimestampMixin, Base):
    __tablename__ = "deliveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # unique=True: one delivery per order. It also makes the worker idempotent
    # when RabbitMQ delivers the same `order.created` message twice.
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), unique=True)
    status: Mapped[DeliveryStatus] = mapped_column(
        _str_enum(DeliveryStatus), default=DeliveryStatus.PENDING, index=True
    )

    order: Mapped[Order] = relationship(back_populates="delivery", lazy="raise")


class OutboxMessage(Base):
    """Transactional outbox: events are saved here in the same transaction as
    the business change, and a separate relay process publishes them to RabbitMQ.
    """

    __tablename__ = "outbox"
    __table_args__ = (
        # Partial index: the relay only ever looks for unpublished rows.
        Index(
            "ix_outbox_unpublished",
            "id",
            postgresql_where="published_at IS NULL",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[UUID] = mapped_column(Uuid, unique=True)
    routing_key: Mapped[str] = mapped_column(String(100))
    payload: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now()
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
