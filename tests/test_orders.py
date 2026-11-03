from app.db.models import Delivery
from app.domain.statuses import DeliveryStatus


async def test_create_order(client, customer, order_payload, outbox_events):
    response = await client.post("/orders", json=order_payload, headers=customer)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "created"
    assert body["delivery"] is None  # created later by the worker
    assert await outbox_events() == ["order.created"]


async def test_create_order_requires_auth(client, order_payload):
    response = await client.post("/orders", json=order_payload)

    assert response.status_code == 401


async def test_create_order_for_missing_restaurant(client, customer, order_payload, outbox_events):
    response = await client.post("/orders", json={**order_payload, "restaurant_id": 999}, headers=customer)

    assert response.status_code == 404
    assert await outbox_events() == []  # nothing happened -> no event


async def test_quantity_must_be_positive(client, customer, order_payload):
    response = await client.post("/orders", json={**order_payload, "quantity": 0}, headers=customer)

    assert response.status_code == 422


async def test_customer_sees_only_own_orders(client, customer, other_customer, order_payload):
    own = (await client.post("/orders", json=order_payload, headers=customer)).json()
    await client.post("/orders", json=order_payload, headers=other_customer)

    response = await client.get("/orders", headers=customer)

    assert [o["id"] for o in response.json()] == [own["id"]]


async def test_someone_elses_order_is_not_found(client, customer, other_customer, order_payload):
    order = (await client.post("/orders", json=order_payload, headers=customer)).json()

    response = await client.get(f"/orders/{order['id']}", headers=other_customer)

    assert response.status_code == 404


async def test_admin_sees_all_orders(client, admin, customer, other_customer, order_payload):
    await client.post("/orders", json=order_payload, headers=customer)
    await client.post("/orders", json=order_payload, headers=other_customer)

    response = await client.get("/orders", headers=admin)

    assert len(response.json()) == 2


async def test_cancel_order(client, customer, order_payload, outbox_events):
    order = (await client.post("/orders", json=order_payload, headers=customer)).json()

    response = await client.post(f"/orders/{order['id']}/cancel", headers=customer)

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert await outbox_events() == ["order.created", "order.cancelled"]


async def test_cannot_cancel_twice(client, customer, order_payload):
    order = (await client.post("/orders", json=order_payload, headers=customer)).json()
    await client.post(f"/orders/{order['id']}/cancel", headers=customer)

    response = await client.post(f"/orders/{order['id']}/cancel", headers=customer)

    assert response.status_code == 409


async def test_cannot_cancel_someone_elses_order(client, customer, other_customer, order_payload):
    order = (await client.post("/orders", json=order_payload, headers=customer)).json()

    response = await client.post(f"/orders/{order['id']}/cancel", headers=other_customer)

    assert response.status_code == 404


async def test_cancel_also_cancels_pending_delivery(client, customer, order_payload, session_factory):
    order = (await client.post("/orders", json=order_payload, headers=customer)).json()
    async with session_factory() as session:
        session.add(Delivery(order_id=order["id"], status=DeliveryStatus.PENDING))
        await session.commit()

    response = await client.post(f"/orders/{order['id']}/cancel", headers=customer)

    assert response.json()["delivery"]["status"] == "cancelled"


async def test_cannot_cancel_when_courier_took_the_order(client, customer, order_payload, session_factory):
    order = (await client.post("/orders", json=order_payload, headers=customer)).json()
    async with session_factory() as session:
        session.add(Delivery(order_id=order["id"], status=DeliveryStatus.IN_TRANSIT))
        await session.commit()

    response = await client.post(f"/orders/{order['id']}/cancel", headers=customer)

    assert response.status_code == 409
