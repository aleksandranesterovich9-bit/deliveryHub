"""Outbox relay and worker handlers, tested without a real RabbitMQ."""

import json
import logging

import pytest
from sqlalchemy import func, select

from app.db.models import Delivery, Order, OutboxMessage, Restaurant, User
from app.domain.events import DeliveryStatusChanged, OrderCreated, parse_event
from app.domain.statuses import DeliveryStatus, OrderStatus
from app.infrastructure.outbox import OutboxRelay, stage_event
from app.worker.handlers import create_delivery_for_order, notification_text, send_notification


class FakePublisher:
    def __init__(self, fail_on: int | None = None) -> None:
        self.published: list[tuple[str, dict]] = []
        self._fail_on = fail_on

    async def publish(self, routing_key: str, body: bytes, message_id: str) -> None:
        if self._fail_on is not None and len(self.published) == self._fail_on:
            raise ConnectionError("RabbitMQ is down")
        self.published.append((routing_key, json.loads(body)))


@pytest.fixture
async def order(session_factory) -> Order:
    async with session_factory() as session:
        user = User(name="U", phone="+70000000009", password_hash="x")
        restaurant = Restaurant(name="R")
        session.add_all([user, restaurant])
        await session.flush()
        order = Order(
            user_id=user.id,
            restaurant_id=restaurant.id,
            dish="Soup",
            quantity=1,
            delivery_address="Somewhere 1",
            status=OrderStatus.CREATED,
        )
        session.add(order)
        await session.commit()
        return order


def _order_created(order: Order) -> OrderCreated:
    return OrderCreated(order_id=order.id, user_id=order.user_id, restaurant_id=order.restaurant_id)


async def _stage(session_factory, *events) -> None:
    async with session_factory() as session:
        for event in events:
            stage_event(session, event)
        await session.commit()


async def _unpublished_count(session_factory) -> int:
    async with session_factory() as session:
        return await session.scalar(
            select(func.count()).select_from(OutboxMessage).where(OutboxMessage.published_at.is_(None))
        )


# --- outbox relay -----------------------------------------------------------


async def test_relay_publishes_staged_events_once(session_factory, order):
    await _stage(session_factory, _order_created(order))
    publisher = FakePublisher()
    relay = OutboxRelay(session_factory, publisher)

    assert await relay.publish_pending() == 1
    assert await relay.publish_pending() == 0  # already marked as published

    routing_key, payload = publisher.published[0]
    assert routing_key == "order.created"
    assert payload["order_id"] == order.id


async def test_relay_keeps_events_if_broker_is_down(session_factory, order):
    await _stage(session_factory, _order_created(order), _order_created(order))
    relay = OutboxRelay(session_factory, FakePublisher(fail_on=1))

    with pytest.raises(ConnectionError):
        await relay.publish_pending()

    # The transaction rolled back: both events will be retried (at-least-once).
    assert await _unpublished_count(session_factory) == 2


# --- worker -----------------------------------------------------------------


async def _deliveries(session_factory) -> list[Delivery]:
    async with session_factory() as session:
        return list(await session.scalars(select(Delivery)))


async def test_worker_creates_pending_delivery(session_factory, order):
    await create_delivery_for_order(_order_created(order), session_factory)

    [delivery] = await _deliveries(session_factory)
    assert delivery.order_id == order.id
    assert delivery.status == DeliveryStatus.PENDING


async def test_worker_is_idempotent(session_factory, order):
    event = _order_created(order)

    await create_delivery_for_order(event, session_factory)
    await create_delivery_for_order(event, session_factory)  # RabbitMQ re-delivered it

    assert len(await _deliveries(session_factory)) == 1


async def test_worker_skips_cancelled_order(session_factory, order):
    async with session_factory() as session:
        (await session.get(Order, order.id)).status = OrderStatus.CANCELLED
        await session.commit()

    await create_delivery_for_order(_order_created(order), session_factory)

    assert await _deliveries(session_factory) == []


async def test_worker_skips_unknown_order(session_factory):
    await create_delivery_for_order(OrderCreated(order_id=404, user_id=1, restaurant_id=1), session_factory)

    assert await _deliveries(session_factory) == []


async def test_notification_is_sent(caplog):
    event = DeliveryStatusChanged(
        delivery_id=1,
        order_id=7,
        user_id=3,
        old_status=DeliveryStatus.COURIER_ASSIGNED,
        new_status=DeliveryStatus.IN_TRANSIT,
    )

    with caplog.at_level(logging.INFO):
        await send_notification(event)

    assert "Notification to user #3: Order #7: delivery is now in transit" in caplog.text


# --- event serialization ------------------------------------------------------


def test_event_roundtrip_through_json():
    event = OrderCreated(order_id=1, user_id=2, restaurant_id=3)

    parsed = parse_event(event.routing_key, event.model_dump_json().encode())

    assert parsed == event
    assert notification_text(parsed) == "Order #1 has been accepted"


def test_unknown_event_type_is_rejected():
    with pytest.raises(ValueError, match="Unknown event type"):
        parse_event("payment.refunded", b"{}")
