from fastapi import FastAPI

from app.routes.restaurants import router as restaurants_router
from app.routes.orders import router as orders_router

app = FastAPI()

app.include_router(restaurants_router)
app.include_router(orders_router)
