import asyncio
import random

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import Order as OrderModel
from app.database import Restaurant as RestaurantModel
from app.database import get_db

router = APIRouter(tags=['Orders'])


# Схема заказа для ответа API
class OrderResponse(BaseModel):
    id: int
    user_id: int
    restaurant_id: int
    dish: str
    quantity: int

    model_config = ConfigDict(from_attributes=True)


# Схема для создания заказа
class CreateOrder(BaseModel):
    user_id: int
    restaurant_id: int
    dish: str
    quantity: int


# Создание заказа
@router.post("/orders", response_model=OrderResponse)
def create_order(
    obj: CreateOrder,
    db: Session = Depends(get_db)
):
    restaurant = db.get(RestaurantModel, obj.restaurant_id)

    if restaurant is None:
        raise HTTPException(
            status_code=404,
            detail="Restaurant not found"
        )

    order = OrderModel(
        user_id=obj.user_id,
        restaurant_id=obj.restaurant_id,
        dish=obj.dish,
        quantity=obj.quantity
    )

    db.add(order)

    try:
        db.commit()
        db.refresh(order)
    except Exception:
        db.rollback()
        raise

    return order


# Получение всех заказов
@router.get("/orders", response_model=list[OrderResponse])
def get_all_orders(db: Session = Depends(get_db)):
    statement = select(OrderModel).order_by(OrderModel.id)
    return db.scalars(statement).all()


# Получение заказов конкретного ресторана
@router.get(
    "/restaurants/{restaurant_id}/orders",
    response_model=list[OrderResponse]
)
def get_restaurant_orders(
    restaurant_id: int,
    db: Session = Depends(get_db)
):
    restaurant = db.get(RestaurantModel, restaurant_id)

    if restaurant is None:
        raise HTTPException(
            status_code=404,
            detail="Restaurant not found"
        )

    statement = (
        select(OrderModel)
        .where(OrderModel.restaurant_id == restaurant_id)
        .order_by(OrderModel.id)
    )

    return db.scalars(statement).all()


# Получение дополнительной информации о заказе
async def get_order_info(order: OrderModel):
    delay = random.uniform(1, 3)
    await asyncio.sleep(delay)

    return {
        "id": order.id,
        "user_id": order.user_id,
        "restaurant_id": order.restaurant_id,
        "dish": order.dish,
        "quantity": order.quantity
    }


@router.get("/orders_info")
async def get_orders_info(db: Session = Depends(get_db)):
    statement = select(OrderModel).order_by(OrderModel.id)
    orders = db.scalars(statement).all()

    return await asyncio.gather(
        *(get_order_info(order) for order in orders)
    )

