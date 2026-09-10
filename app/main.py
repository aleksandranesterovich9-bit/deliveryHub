from fastapi import FastAPI
from app.routes.restaurants import router


app = FastAPI()

@app.get('/')
def root():
    return 'Hello! '

app.include_router(router)

