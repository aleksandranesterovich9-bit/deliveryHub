import pytest

from app.db.models import Delivery
from app.domain.statuses import DeliveryStatus


@pytest.fixture
async def delivery(client, customer, order_payload, session_factory) -> dict:
    """An order plus the pending delivery the worker would have created for it."""
    order = (await client.post("/orders", json=order_payload, headers=customer)).json()
    async with session_factory() as session:
        delivery = Delivery(order_id=order["id"], status=DeliveryStatus.PENDING)
        session.add(delivery)
        await session.commit()
        return {"id": delivery.id, "order_id": order["id"]}


async def _set_status(client, admin, delivery_id: int, status: str):
    return await client.patch(f"/deliveries/{delivery_id}/status", json={"status": status}, headers=admin)


async def test_full_delivery_lifecycle(client, admin, customer, delivery, outbox_events):
    for status in ("courier_assigned", "in_transit", "delivered"):
        response = await _set_status(client, admin, delivery["id"], status)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == status

    order = (await client.get(f"/orders/{delivery['order_id']}", headers=customer)).json()
    assert order["status"] == "completed"
    assert (await outbox_events()).count("delivery.status_changed") == 3


async def test_cannot_skip_delivery_steps(client, admin, delivery):
    response = await _set_status(client, admin, delivery["id"], "delivered")

    assert response.status_code == 409


async def test_cancelling_delivery_cancels_order(client, admin, customer, delivery):
    await _set_status(client, admin, delivery["id"], "cancelled")

    order = (await client.get(f"/orders/{delivery['order_id']}", headers=customer)).json()
    assert order["status"] == "cancelled"


async def test_customer_cannot_manage_deliveries(client, customer, delivery):
    assert (await client.get("/deliveries", headers=customer)).status_code == 403
    assert (await _set_status(client, customer, delivery["id"], "courier_assigned")).status_code == 403


async def test_admin_lists_deliveries_by_status(client, admin, delivery):
    pending = await client.get("/deliveries", params={"delivery_status": "pending"}, headers=admin)
    delivered = await client.get("/deliveries", params={"delivery_status": "delivered"}, headers=admin)

    assert [d["id"] for d in pending.json()] == [delivery["id"]]
    assert delivered.json() == []


async def test_missing_delivery_is_not_found(client, admin):
    response = await _set_status(client, admin, 999, "courier_assigned")

    assert response.status_code == 404
