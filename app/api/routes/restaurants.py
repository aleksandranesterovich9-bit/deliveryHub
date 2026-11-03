from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import AdminUser, CacheDep, PaginationDep, SessionDep
from app.application.commands.restaurants import (
    CreateRestaurant,
    DeleteRestaurant,
    UpdateRestaurant,
    handle_create_restaurant,
    handle_delete_restaurant,
    handle_update_restaurant,
)
from app.application.queries.restaurants import (
    GetRestaurant,
    ListRestaurants,
    handle_get_restaurant,
    handle_list_restaurants,
)
from app.schemas.restaurants import RestaurantRead, RestaurantWrite

router = APIRouter(prefix="/restaurants", tags=["Restaurants"])


@router.get("", response_model=list[RestaurantRead])
async def list_restaurants(
    session: SessionDep,
    cache: CacheDep,
    page: PaginationDep,
    name: Annotated[str | None, Query(max_length=100, description="Search by part of the name")] = None,
) -> list[RestaurantRead]:
    query = ListRestaurants(name=name, limit=page.limit, offset=page.offset)
    return await handle_list_restaurants(query, session, cache)


@router.get("/{restaurant_id}", response_model=RestaurantRead)
async def get_restaurant(restaurant_id: int, session: SessionDep, cache: CacheDep) -> RestaurantRead:
    return await handle_get_restaurant(GetRestaurant(restaurant_id), session, cache)


@router.post("", response_model=RestaurantRead, status_code=status.HTTP_201_CREATED)
async def create_restaurant(
    body: RestaurantWrite, session: SessionDep, cache: CacheDep, _: AdminUser
) -> RestaurantRead:
    restaurant_id = await handle_create_restaurant(CreateRestaurant(name=body.name), session, cache)
    return await handle_get_restaurant(GetRestaurant(restaurant_id), session, cache)


@router.put("/{restaurant_id}", response_model=RestaurantRead)
async def update_restaurant(
    restaurant_id: int, body: RestaurantWrite, session: SessionDep, cache: CacheDep, _: AdminUser
) -> RestaurantRead:
    await handle_update_restaurant(UpdateRestaurant(restaurant_id, body.name), session, cache)
    return await handle_get_restaurant(GetRestaurant(restaurant_id), session, cache)


@router.delete("/{restaurant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_restaurant(restaurant_id: int, session: SessionDep, cache: CacheDep, _: AdminUser) -> None:
    await handle_delete_restaurant(DeleteRestaurant(restaurant_id), session, cache)
