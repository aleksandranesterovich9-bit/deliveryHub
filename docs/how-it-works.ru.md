# Как устроен DeliveryHub — разбор для обучения

Этот документ — карта проекта. Читай его с открытым кодом: у каждого раздела есть ссылки на файлы.
В конце — эксперименты, задания и вопросы, какие задают на собеседованиях.

---

## 1. Слои проекта

```
api/          → «Как с нами говорить по HTTP». Ничего не решает, только переводит HTTP ↔ команды/запросы
application/  → «Что система умеет делать». Вся бизнес-логика тут
domain/       → «Правила мира». Статусы, какие переходы разрешены, какие бывают события
db/           → «Как хранить». Таблицы SQLAlchemy
infrastructure/ → «Внешние системы». Redis, RabbitMQ, outbox
worker/, relay.py → Фоновые процессы
```

Правило: **зависимости идут внутрь**. `api` знает про `application`, `application` знает про `domain`,
но `domain` не знает ни про FastAPI, ни про базу. Поэтому `application` бросает `NotFoundError`, а не
`HTTPException`: тот же код работает и из HTTP, и из worker'а, и из тестов. Перевод в HTTP-коды — в
[`app/api/errors.py`](../app/api/errors.py).

---

## 2. Путь одного запроса: `POST /orders`

Пройди по этим файлам по порядку, это лучший способ понять проект:

1. **[`api/routes/orders.py`](../app/api/routes/orders.py)** → `create_order`.
   FastAPI проверил тело по схеме `OrderCreate`, `CurrentUser` достал пользователя из JWT
   ([`api/deps.py`](../app/api/deps.py)). Роутер собирает **команду** `CreateOrder` и отдаёт её обработчику.
2. **[`application/commands/orders.py`](../app/application/commands/orders.py)** → `handle_create_order`.
   Проверяет ресторан, создаёт `Order`, делает `flush()` (база выдала `id`, но транзакция ещё открыта),
   кладёт событие `OrderCreated` в таблицу `outbox` и **одним** `commit()` сохраняет и заказ, и событие.
3. Роутер вызывает **запрос** `GetOrder` → [`application/queries/orders.py`](../app/application/queries/orders.py)
   и возвращает свежие данные. `delivery: null` — доставки ещё нет.
4. **[`relay.py`](../app/relay.py)** + [`infrastructure/outbox.py`](../app/infrastructure/outbox.py):
   раз в секунду ищет неотправленные строки в `outbox`, публикует их в RabbitMQ и помечает `published_at`.
5. **RabbitMQ** по routing key `order.created` кладёт копию сообщения в две очереди:
   `deliveries` и `notifications` ([`infrastructure/rabbitmq.py`](../app/infrastructure/rabbitmq.py)).
6. **[`worker/`](../app/worker/__main__.py)** забирает сообщения:
   `create_delivery_for_order` создаёт доставку `pending`, `send_notification` «отправляет SMS» (пишет в лог).
7. Через секунду `GET /orders/1` уже показывает `delivery: {status: "pending"}`.

---

## 3. CQRS — Command Query Responsibility Segregation

**Команда** меняет состояние и ничего не читает «для показа». **Запрос** только читает и ничего не меняет.

| | Команды (`application/commands/`) | Запросы (`application/queries/`) |
|---|---|---|
| Что делают | Проверяют правила, пишут в БД, создают события | Читают и возвращают DTO (Pydantic-схемы) |
| Что возвращают | `id` или ничего | Готовые данные для ответа |
| Кэш | **Сбрасывают** | **Используют** |
| События | Создают | Никогда |

Почему команды возвращают только `id`: так команда не думает о том, *как показать* результат.
После команды роутер вызывает запрос — тот же, что и для `GET`. Ответ на `POST` и на `GET` всегда одинаковый.

Команда — это просто `@dataclass(frozen=True)`: неизменяемый объект «что хотим сделать».
Обработчик — обычная `async`-функция с явными зависимостями `(cmd, session, cache)`.
Без «магии» и медиаторов её легко вызвать в тестах.

> У нас «лёгкий» CQRS: одна база на запись и чтение. В «полном» CQRS у чтения своя база (read model),
> которую обновляют события. Задание 7 ниже — шаг в эту сторону.

---

## 4. Redis

### Кэш ресторанов — [`infrastructure/cache.py`](../app/infrastructure/cache.py), [`queries/restaurants.py`](../app/application/queries/restaurants.py)

Паттерн **cache-aside**: посмотреть в Redis → нет? → прочитать из БД → положить в Redis с TTL.

Самое интересное — **инвалидация через версию**. Ключи выглядят так: `restaurants:v3:list:pizza:20:0`.
Любая команда по ресторанам делает `INCR restaurants:version`, и все старые ключи `v3` становятся
недостижимыми: читатели уже ищут `v4`. Старые ключи удалит TTL.
Альтернатива — искать ключи по маске через `KEYS restaurants:*` — блокирует Redis на больших объёмах. Так делать нельзя.

### Защита логина — [`infrastructure/rate_limiter.py`](../app/infrastructure/rate_limiter.py)

`INCR login_failures:+7999...` при каждой ошибке и `EXPIRE ... NX` (таймер ставится только при первой).
После 5 ошибок → 429 и заголовок `Retry-After`. Успешный вход сбрасывает счётчик.

### Если Redis упал

Все методы ловят `RedisError`. Кэш превращается в «промах», лимитер пропускает (fail open). API работает, просто медленнее.
Мы это проверяли: `docker compose stop redis` → `/restaurants` отвечает 200, `/health` отвечает 503 `degraded`.

---

## 5. RabbitMQ

Словарь (смотри на картинку в начале [`rabbitmq.py`](../app/infrastructure/rabbitmq.py)):

- **Exchange** — «сортировочный центр». Сам ничего не хранит, только решает, в какие очереди отправить.
- **Queue** — «почтовый ящик». Хранит сообщения, пока их не заберут.
- **Binding** — правило «из этого exchange с таким ключом → в эту очередь».
- **Routing key** — «адрес» на сообщении: `order.created`.
- **Topic exchange** — ключи с масками: `order.*` ловит `order.created` и `order.cancelled`;
  `#` — ноль или больше слов.

Важные настройки и зачем они:

| Где | Что | Зачем |
|---|---|---|
| exchange, queue | `durable=True` | переживают перезапуск RabbitMQ |
| сообщение | `DeliveryMode.PERSISTENT` | само сообщение тоже пишется на диск |
| канал | publisher confirms (по умолчанию в aio-pika) | `publish()` ждёт подтверждения, что брокер принял |
| worker | `set_qos(prefetch_count=10)` | не брать больше 10 необработанных сообщений за раз |
| worker | `message.process(requeue=False)` | успех → **ack** (удалить из очереди); ошибка → **reject** |
| очередь | `x-dead-letter-exchange` | отклонённое сообщение уходит в `dead_letters`, а не теряется |

Если worker упал посреди обработки и не успел сделать ack, RabbitMQ отдаст сообщение снова.
Отсюда правило: **обработчики должны быть идемпотентными** — повторная обработка ничего не ломает.
Смотри `create_delivery_for_order`: проверка «доставка уже есть?» плюс `UNIQUE(order_id)` в базе.

---

## 6. Transactional Outbox — зачем такие сложности?

Наивный вариант:

```python
await session.commit()  # 1. заказ сохранён
await rabbit.publish(event)  # 2. 💥 RabbitMQ недоступен / процесс упал
```

Заказ есть, события нет: доставка никогда не создастся. А если поменять порядок, будет событие о заказе,
которого нет. Это **проблема двойной записи** (dual write): нельзя атомарно записать в две разные системы.

Решение: пишем событие **в ту же базу и в той же транзакции** (таблица `outbox`), а отдельный процесс
(relay) уже без спешки доставляет события в RabbitMQ. Либо сохранилось всё, либо ничего.

Мы проверяли вживую: остановили RabbitMQ → заказ создался (201) → событие ждало в `outbox` →
запустили RabbitMQ → relay сам отправил событие → worker создал доставку.

`with_for_update(skip_locked=True)` в relay — чтобы два relay параллельно не взяли одни и те же строки.

---

## 7. Async SQLAlchemy — чем отличается от того, что было

- `await session.execute(...)`, `await session.commit()` — каждый поход в базу через `await`.
- **Ленивой загрузки нет.** В sync-коде `order.delivery` молча делал SQL-запрос. В async так нельзя.
  Поэтому у связей `lazy="raise"` (ошибка сразу, а не тихий баг), а нужные связи грузим явно:
  `.options(selectinload(Order.delivery))`.
- `expire_on_commit=False` — после `commit()` объект остаётся читаемым и не требует нового запроса.
- `flush()` ≠ `commit()`. `flush` отправляет SQL и получает `id`, но транзакцию можно откатить. `commit` фиксирует.

---

## 8. Тесты — [`tests/`](../tests)

- `pytest` — SQLite в памяти и fakeredis, Docker не нужен. В CI те же тесты идут на настоящем Postgres
  (`TEST_DATABASE_URL`).
- Главный трюк — `app.dependency_overrides` в [`conftest.py`](../tests/conftest.py): подменяем
  `get_session` и `get_redis`, и приложение не знает, что оно в тесте.
- RabbitMQ в тестах не нужен: команды проверяем по строкам в `outbox`, relay — с `FakePublisher`,
  обработчики worker'а вызываем напрямую ([`test_messaging.py`](../tests/test_messaging.py)).

---

## 9. Эксперименты руками (обязательно попробуй)

Запусти `docker compose up --build` и:

1. **Посмотри на RabbitMQ изнутри.** http://localhost:15672 (guest/guest) → Exchanges → `delivery_hub.events`
   → Bindings. Создай заказ в Swagger и посмотри графики в Queues.
2. **Сломай сообщение.** В UI: Exchanges → `delivery_hub.events` → Publish message, routing key `order.created`,
   payload `привет`. Открой очередь `delivery_hub.dead_letters` → Get messages. Сообщение там, а в логах
   worker'а — ошибка. Так работает DLQ.
   Вопрос: почему в `dead_letters` оказалось **два** сообщения, хотя ты отправила одно?
3. **Outbox в деле.** `docker compose stop rabbitmq` → создай заказ → в базе
   `docker compose exec postgres psql -U postgres -d delivery_hub -c "select * from outbox"` →
   `docker compose start rabbitmq` → `docker compose logs -f relay worker`.
4. **Загляни в Redis.** `docker compose exec redis redis-cli` → `KEYS *`, `GET restaurants:version`,
   `TTL <ключ>`. Измени ресторан через API и снова посмотри версию.
5. **Конкурирующие потребители.** `docker compose up -d --scale worker=3` → создай 5 заказов →
   `docker compose logs worker`. Сообщения распределились между worker'ами — так масштабируется обработка.
6. **Брутфорс.** 5 раз введи неверный пароль → 429. В redis-cli: `GET login_failures:+7...` и `TTL`.

---

## 10. Задания (от простого к сложному)

Делай каждое в отдельной ветке, с тестом и отдельным коммитом. Так получается красивая история в git.

**🟢 1. `GET /deliveries/{id}` для админа.**
Запрос `handle_get_delivery` уже есть, нужен только роутер и тест.
→ `api/routes/deliveries.py`, `tests/test_deliveries.py`

**🟢 2. Поле `address` у ресторана.**
Пройди всю цепочку: модель → `alembic revision --autogenerate -m "restaurant address"` → схемы → команды → тесты.
→ `db/models.py`, `schemas/restaurants.py`, `commands/restaurants.py`

**🟡 3. Событие `order.completed`.**
Когда доставка `delivered`, отправлять отдельное событие → уведомление «Оцените заказ».
→ `domain/events.py` (не забудь `EVENT_TYPES`), `commands/deliveries.py`, `worker/handlers.py`, тесты.
Подумай: нужно ли менять bindings в `rabbitmq.py`? (Подсказка: посмотри на маску `order.*`.)

**🟡 4. Backoff в relay.**
Сейчас при недоступном RabbitMQ relay пишет ошибку каждую секунду. Сделай экспоненциальную паузу:
1 → 2 → 4 → … → максимум 30 секунд, со сбросом после успеха.
→ `infrastructure/outbox.py`, метод `run`

**🟡 5. Выход из системы (logout) через Redis.**
JWT нельзя «отозвать», пока не истёк срок. Добавь в токен `jti` (uuid), а при `POST /auth/logout` клади
`jti` в Redis с TTL до конца жизни токена. `get_current_user` должен отклонять токены из этого списка.
→ `core/security.py`, `api/deps.py`, `api/routes/auth.py`

**🔴 6. Повторы перед DLQ.**
Сейчас любая ошибка сразу отправляет сообщение в DLQ. Сделай 3 попытки с задержкой: очередь
`delivery_hub.retry` с `x-message-ttl=5000` и `x-dead-letter-exchange` обратно в `delivery_hub.events`.
Счётчик попыток храни в заголовке сообщения.
→ `infrastructure/rabbitmq.py`, `worker/__main__.py`

**🔴 7. Роль курьера.**
`UserRole.COURIER`, `Delivery.courier_id`, эндпоинты «свободные доставки», «взять доставку»,
«сменить статус своей доставки». Курьер не должен трогать чужие доставки. Как сделать, чтобы два курьера
не взяли одну доставку одновременно? (Подсказка: `UPDATE ... WHERE courier_id IS NULL`.)

**🔴 8. Меню и заказ из нескольких блюд.**
Таблицы `dishes` (restaurant_id, name, price) и `order_items`; сумма заказа считается на сервере;
меню ресторана кэшируется в Redis.

---

## 11. Вопросы для самопроверки (часто спрашивают на собеседованиях)

1. Почему нельзя просто сделать `publish()` после `commit()`? Что такое dual write?
2. Что гарантирует наш outbox: at-most-once, at-least-once или exactly-once? Почему?
3. Что будет, если worker упадёт посреди обработки сообщения?
4. Почему для чужого заказа мы отвечаем 404, а не 403?
5. Зачем нужен `FOR UPDATE SKIP LOCKED`?
6. Чем exchange отличается от queue? Когда нужен topic, а когда хватит direct или fanout?
7. Что такое `prefetch_count` и что будет, если поставить 1000?
8. Почему кэш инвалидируется версией, а не удалением ключей?
9. Лимитер логина работает по принципу fail open. Когда правильнее fail closed?
10. Что делает `flush()` и чем он отличается от `commit()`?
11. Почему в async SQLAlchemy нельзя ленивую загрузку связей?
12. Что такое идемпотентность и как она реализована в worker'е?

Если можешь своими словами ответить на все 12 — этот проект можно смело защищать на собеседовании.
