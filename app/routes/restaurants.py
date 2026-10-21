from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session,joinedload

from app.database import Restaurant as RestaurantModel, get_db


router = APIRouter(tags=['Restaurants'])

class RestaurantResponse(BaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)


# Схема данных, которые клиент присылает
class CreateRestaurant(BaseModel):
    name: str


# GET /restaurants
@router.get("/restaurants", response_model=list[RestaurantResponse])
def get_restaurants(
    name: str | None = None,
    limit: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db)
):
    statement = select(RestaurantModel)

    if name:
        statement = statement.where(
            RestaurantModel.name.ilike(f"%{name}%")
        )

    if limit is not None:
        statement = statement.limit(limit)

    return db.scalars(statement).all()


# GET /restaurants/{restaurant_id}
@router.get(
    "/restaurants/{restaurant_id}",
    response_model=RestaurantResponse
)
async def get_restaurant(
    restaurant_id: int,
    db: Session = Depends(get_db)
):

        statement = select(RestaurantModel).where(RestaurantModel.id == restaurant_id)

        restaurant = db.scalars(statement).one_or_none()

        if restaurant is None:
            raise HTTPException(
                status_code=404,
                detail="Restaurant not found"
            )

        return restaurant


# POST /restaurants
@router.post("/restaurants", response_model=RestaurantResponse)
def create_restaurant(
    obj: CreateRestaurant,
    db: Session = Depends(get_db)
):
    restaurant = RestaurantModel(name=obj.name)

    db.add(restaurant)

    try:
        db.commit()
        db.refresh(restaurant)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Could not create restaurant"
        )

    return restaurant


# PUT /restaurants/{restaurant_id}
@router.put(
    "/restaurants/{restaurant_id}",
    response_model=RestaurantResponse
)
def update_restaurant(
    restaurant_id: int,
    obj: CreateRestaurant,
    db: Session = Depends(get_db)
):
    restaurant = db.get(RestaurantModel, restaurant_id)

    if restaurant is None:
        raise HTTPException(
            status_code=404,
            detail="Restaurant not found"
        )

    restaurant.name = obj.name

    db.commit()
    db.refresh(restaurant)

    return restaurant


# DELETE /restaurants/{restaurant_id}
@router.delete("/restaurants/{restaurant_id}")
def delete_restaurant(
    restaurant_id: int,
    db: Session = Depends(get_db)
):
    restaurant = db.get(RestaurantModel, restaurant_id)

    if restaurant is None:
        raise HTTPException(
            status_code=404,
            detail="Restaurant not found"
        )

    db.delete(restaurant)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Cannot delete restaurant because it has related records"
        )

    return {"message": "Restaurant deleted successfully"}
