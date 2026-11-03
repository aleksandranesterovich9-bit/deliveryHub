async def test_list_restaurants_is_public(client, restaurant):
    response = await client.get("/restaurants")

    assert response.status_code == 200
    assert [r["name"] for r in response.json()] == ["Pizza House"]


async def test_search_restaurants_by_name(client, admin):
    for name in ("Pizza House", "Sushi Master", "Pizza Hut"):
        await client.post("/restaurants", json={"name": name}, headers=admin)

    response = await client.get("/restaurants", params={"name": "pIzZa"})

    assert sorted(r["name"] for r in response.json()) == ["Pizza House", "Pizza Hut"]


async def test_search_treats_percent_literally(client, restaurant):
    response = await client.get("/restaurants", params={"name": "%"})

    assert response.json() == []


async def test_get_missing_restaurant_is_not_found(client):
    response = await client.get("/restaurants/999")

    assert response.status_code == 404


async def test_anonymous_cannot_create_restaurant(client):
    response = await client.post("/restaurants", json={"name": "Nope"})

    assert response.status_code == 401


async def test_customer_cannot_create_restaurant(client, customer):
    response = await client.post("/restaurants", json={"name": "Nope"}, headers=customer)

    assert response.status_code == 403


async def test_duplicate_restaurant_name_is_conflict(client, admin, restaurant):
    response = await client.post("/restaurants", json={"name": "Pizza House"}, headers=admin)

    assert response.status_code == 409


async def test_list_is_cached_in_redis(client, restaurant, redis):
    await client.get("/restaurants")

    keys = await redis.keys("restaurants:*:list:*")
    assert len(keys) == 1


async def test_cache_is_invalidated_after_write(client, admin, restaurant):
    await client.get("/restaurants")  # warm up the cache

    await client.post("/restaurants", json={"name": "Sushi Master"}, headers=admin)
    response = await client.get("/restaurants")

    assert [r["name"] for r in response.json()] == ["Pizza House", "Sushi Master"]


async def test_update_restaurant(client, admin, restaurant):
    await client.get(f"/restaurants/{restaurant['id']}")  # cached old name

    response = await client.put(
        f"/restaurants/{restaurant['id']}", json={"name": "Pizza Palace"}, headers=admin
    )

    assert response.status_code == 200
    assert (await client.get(f"/restaurants/{restaurant['id']}")).json()["name"] == "Pizza Palace"


async def test_delete_restaurant(client, admin, restaurant):
    response = await client.delete(f"/restaurants/{restaurant['id']}", headers=admin)

    assert response.status_code == 204
    assert (await client.get(f"/restaurants/{restaurant['id']}")).status_code == 404


async def test_cannot_delete_restaurant_with_orders(client, admin, customer, order_payload):
    await client.post("/orders", json=order_payload, headers=customer)

    response = await client.delete(f"/restaurants/{order_payload['restaurant_id']}", headers=admin)

    assert response.status_code == 409
