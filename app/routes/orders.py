from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import restaurants


router = APIRouter()

orders = []

class Order(BaseModel):
    id:int
    restaurant_id:int
    dish:str
    quantity:int

class CreateOrder(BaseModel):
    restaurant_id:int
    dish:str
    quantity:int

@router.post('/order',response_model=Order)
async def create_order(obj:CreateOrder):
    if orders:
        new_id = max(order['id'] for order in orders) + 1
    else:
        new_id = 1
    new_order = {'id': new_id, 'restaurant_id': obj.restaurant_id,'dish': obj.dish, 'quantity':obj.quantity}
    for restaurant in restaurants:
        if restaurant['id'] == obj.restaurant_id:
            orders.append(new_order)
            return new_order
    raise HTTPException(
        status_code=404,
        detail='Restaurant not found'
    )
