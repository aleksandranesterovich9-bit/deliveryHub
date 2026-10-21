from fastapi import FastAPI

from app.routes.restaurants import router as restaurants_router
from app.routes.orders import router as orders_router
from app.routes.auth import router as auth_router
from app.routes.delivery import router as deliveries_router

app = FastAPI()

@app.get('/')
def hello():
    return 'Hello! Open the FastAPI/docs'

app.include_router(restaurants_router)
app.include_router(orders_router)
app.include_router(auth_router)
app.include_router(deliveries_router)
