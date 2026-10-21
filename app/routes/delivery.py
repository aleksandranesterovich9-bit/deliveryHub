from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import Delivery as DeliveryModel, get_db

router = APIRouter(tags=['Deliveries'])


class DeliveryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    status: str


@router.get("/deliveries", response_model=list[DeliveryResponse])
def get_deliveries(db: Session = Depends(get_db)):
    statement = select(DeliveryModel).order_by(DeliveryModel.id)
    return db.scalars(statement).all()

