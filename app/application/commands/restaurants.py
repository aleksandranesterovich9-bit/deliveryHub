from dataclasses import dataclass

from sqlalchemy import exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.restaurants import CACHE_NAMESPACE
from app.core.exceptions import ConflictError, NotFoundError
from app.db.models import Order, Restaurant
from app.infrastructure.cache import Cache


async def _ensure_name_is_free(session: AsyncSession, name: str, exclude_id: int | None = None) -> None:
    statement = select(Restaurant.id).where(Restaurant.name == name)
    if exclude_id is not None:
        statement = statement.where(Restaurant.id != exclude_id)
    if await session.scalar(statement):
        raise ConflictError("Restaurant with this name already exists")


async def _commit(session: AsyncSession) -> None:
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise ConflictError("Restaurant with this name already exists") from None


async def _get_or_404(session: AsyncSession, restaurant_id: int) -> Restaurant:
    restaurant = await session.get(Restaurant, restaurant_id)
    if restaurant is None:
        raise NotFoundError("Restaurant not found")
    return restaurant


@dataclass(frozen=True, slots=True)
class CreateRestaurant:
    name: str


async def handle_create_restaurant(cmd: CreateRestaurant, session: AsyncSession, cache: Cache) -> int:
    await _ensure_name_is_free(session, cmd.name)
    restaurant = Restaurant(name=cmd.name)
    session.add(restaurant)
    await _commit(session)
    # Writes change what readers see, so the read-side cache must be dropped.
    await cache.invalidate_namespace(CACHE_NAMESPACE)
    return restaurant.id


@dataclass(frozen=True, slots=True)
class UpdateRestaurant:
    restaurant_id: int
    name: str


async def handle_update_restaurant(cmd: UpdateRestaurant, session: AsyncSession, cache: Cache) -> None:
    restaurant = await _get_or_404(session, cmd.restaurant_id)
    await _ensure_name_is_free(session, cmd.name, exclude_id=restaurant.id)
    restaurant.name = cmd.name
    await _commit(session)
    await cache.invalidate_namespace(CACHE_NAMESPACE)


@dataclass(frozen=True, slots=True)
class DeleteRestaurant:
    restaurant_id: int


async def handle_delete_restaurant(cmd: DeleteRestaurant, session: AsyncSession, cache: Cache) -> None:
    restaurant = await _get_or_404(session, cmd.restaurant_id)
    has_orders = await session.scalar(select(exists().where(Order.restaurant_id == restaurant.id)))
    if has_orders:
        raise ConflictError("Cannot delete a restaurant that has orders")

    await session.delete(restaurant)
    await session.commit()
    await cache.invalidate_namespace(CACHE_NAMESPACE)
