from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models import Restaurant
from app.infrastructure.cache import Cache
from app.schemas.restaurants import RestaurantRead

CACHE_NAMESPACE = "restaurants"


@dataclass(frozen=True, slots=True)
class ListRestaurants:
    name: str | None = None
    limit: int = 20
    offset: int = 0


async def handle_list_restaurants(
    query: ListRestaurants, session: AsyncSession, cache: Cache
) -> list[RestaurantRead]:
    # Cache-aside: look in Redis first, on a miss read the DB and remember the result.
    version = await cache.namespace_version(CACHE_NAMESPACE)
    search = (query.name or "").strip().lower()
    key = f"{CACHE_NAMESPACE}:v{version}:list:{search}:{query.limit}:{query.offset}"

    if (cached := await cache.get_json(key)) is not None:
        return [RestaurantRead.model_validate(item) for item in cached]

    statement = select(Restaurant).order_by(Restaurant.id).limit(query.limit).offset(query.offset)
    if search:
        # autoescape: a user typing "%" or "_" searches for those characters
        # literally instead of using them as SQL wildcards.
        statement = statement.where(Restaurant.name.icontains(search, autoescape=True))

    restaurants = [RestaurantRead.model_validate(r) for r in await session.scalars(statement)]
    await cache.set_json(key, [r.model_dump(mode="json") for r in restaurants])
    return restaurants


@dataclass(frozen=True, slots=True)
class GetRestaurant:
    restaurant_id: int


async def handle_get_restaurant(query: GetRestaurant, session: AsyncSession, cache: Cache) -> RestaurantRead:
    version = await cache.namespace_version(CACHE_NAMESPACE)
    key = f"{CACHE_NAMESPACE}:v{version}:item:{query.restaurant_id}"

    if (cached := await cache.get_json(key)) is not None:
        return RestaurantRead.model_validate(cached)

    restaurant = await session.get(Restaurant, query.restaurant_id)
    if restaurant is None:
        raise NotFoundError("Restaurant not found")

    result = RestaurantRead.model_validate(restaurant)
    await cache.set_json(key, result.model_dump(mode="json"))
    return result
