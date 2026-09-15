from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

class Restaurant(BaseModel):
    id:int
    name:str

class CreateRestaurant(BaseModel):
    name:str


restaurants = {
    1: {"id": 1, "name": "Pizza House"},
    2: {"id": 2, "name": "Sushi World"},
    3: {"id": 3, "name": "Burger King"}
}

last_id = max((restaurant['id'] for restaurant in restaurants.values()), default=0) + 1


@router.get('/restaurants', response_model=list[Restaurant])
async def get_restaurants(name:str=None,limit:int=None):
    result = []
    for restaurant in restaurants.values():
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
    try:
        return restaurants[restaurants_id]
    except KeyError:
        raise HTTPException(status_code=404, detail='Not found:(')

@router.post('/restaurants', response_model=Restaurant)
async def create_restaurant(obj:CreateRestaurant):
    global last_id
    new_id = last_id
    new_dict = {'id': new_id, 'name':obj.name}
    restaurants[new_id] = new_dict
    last_id += 1
    return new_dict

@router.put('/restaurants/{restaurants_id}', response_model=Restaurant)
async def change_restaurants(obj:CreateRestaurant,restaurants_id:int):
    try:
        restaurant = restaurants[restaurants_id]
        restaurant['name'] = obj.name
        return restaurant
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail='Not found'
        )

@router.delete('/restaurants/{restaurants_id}')
async def delete_restaurant(restaurants_id:int):
    try:
        del restaurants[restaurants_id]
        return {'message': 'Restaurant deleted successfully'}
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail='Not found'
        )

