from conftest import PASSWORD


async def test_register_returns_user_without_password(client):
    response = await client.post(
        "/auth/register",
        json={"name": "Alex", "phone": "+7 (999) 123-45-67", "password": PASSWORD},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["phone"] == "+79991234567"  # normalized
    assert body["role"] == "customer"
    assert "password" not in body and "password_hash" not in body


async def test_register_duplicate_phone_is_conflict(client, customer):
    response = await client.post(
        "/auth/register", json={"name": "Again", "phone": "+70000000001", "password": PASSWORD}
    )

    assert response.status_code == 409


async def test_register_validates_input(client):
    response = await client.post("/auth/register", json={"name": "A", "phone": "abc", "password": "short"})

    assert response.status_code == 422


async def test_me_returns_current_user(client, customer):
    response = await client.get("/auth/me", headers=customer)

    assert response.status_code == 200
    assert response.json()["phone"] == "+70000000001"


async def test_me_without_token_is_unauthorized(client):
    response = await client.get("/auth/me")

    assert response.status_code == 401


async def test_me_with_garbage_token_is_unauthorized(client):
    response = await client.get("/auth/me", headers={"Authorization": "Bearer not-a-jwt"})

    assert response.status_code == 401


async def test_login_with_wrong_password_is_unauthorized(client, customer):
    response = await client.post(
        "/auth/login", data={"username": "+70000000001", "password": "wrong-password"}
    )

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


async def test_login_is_blocked_after_too_many_failures(client, customer):
    # LOGIN_MAX_ATTEMPTS=3 in conftest
    for _ in range(3):
        await client.post("/auth/login", data={"username": "+70000000001", "password": "wrong-password"})

    # Even the correct password is rejected while blocked.
    response = await client.post("/auth/login", data={"username": "+70000000001", "password": PASSWORD})

    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0


async def test_successful_login_resets_failure_counter(client, customer, redis):
    await client.post("/auth/login", data={"username": "+70000000001", "password": "wrong-password"})
    assert await redis.get("login_failures:+70000000001") == "1"

    response = await client.post("/auth/login", data={"username": "+70000000001", "password": PASSWORD})

    assert response.status_code == 200
    assert await redis.get("login_failures:+70000000001") is None
