from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.routes.restaurants import restaurants


router = APIRouter()

orders = {}

last_order_id = max((order['id'] for order in orders.values()),default=0) + 1

class Order(BaseModel):
    id:int
    restaurant_id:int
    dish:str
    quantity:int

class CreateOrder(BaseModel):
    restaurant_id:int
    dish:str
    quantity:int

@router.post('/orders',response_model=Order)
async def create_order(obj:CreateOrder):
    global last_order_id
    new_id = last_order_id
    new_order = {'id': new_id, 'restaurant_id': obj.restaurant_id,'dish': obj.dish, 'quantity':obj.quantity}
    try:
        if restaurants[obj.restaurant_id]:
            orders[new_id] = new_order
            last_order_id += 1
            return new_order
    except KeyError:
        raise HTTPException(
        status_code=404,
        detail='Restaurant not found'
    )
@router.get('/orders', response_model=list[Order])
async def all_orders():
    return orders.values()


