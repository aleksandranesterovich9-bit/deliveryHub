from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

class Restaurant(BaseModel):
    id:int
    name:str

class CreateRestaurant(BaseModel):
    name:str


restaurants = [
    {"id": 1, "name": "Pizza House"},
    {"id": 2, "name": "Sushi World"},
    {"id": 3, "name": "Burger King"}
]

@router.get('/restaurants', response_model=list[Restaurant])
async def get_restaurants(name:str=None,limit:int=None):
    result = []
    for restaurant in restaurants:
        if name:
            if name.lower() in restaurant['name'].lower():
                result.append(restaurant)
        else:
            result.append(restaurant)
    if limit:
        return result[:limit]

    return result

@router.get('/restaurants/{restaurants_id}', response_model=Restaurant)
async def get_restaurants_id(restaurants_id:int):
    for restaurant in restaurants:
        if restaurant['id'] == restaurants_id:
            return restaurant
        
    raise HTTPException(status_code=404, detail='Not found:(')

@router.post('/restaurants', response_model=Restaurant)
async def create_restaurant(obj:CreateRestaurant):
    new_id = max(restaurant['id'] for restaurant in restaurants) + 1
    new_dict = {'id': new_id, 'name':obj.name}
    restaurants.append(new_dict)
    return new_dict

@router.put('/restaurants/{restaurants_id}', response_model=Restaurant)
async def change_restaurants(obj:CreateRestaurant,restaurants_id:int):
    for restaurant in restaurants:
        if restaurant['id'] == restaurants_id:
            restaurant['name'] = obj.name
            return restaurant
    raise HTTPException(
        status_code=404,detail='Not found'
    ) 

@router.delete('/restaurants/{restaurants_id}')
async def delete_restaurant(restaurants_id:int):
    for restaurant in restaurants:
        if restaurant['id'] == restaurants_id:
            restaurants.remove(restaurant)
            return f'{restaurant} was deleted'
    raise HTTPException(
        status_code=404,detail='Not found')

