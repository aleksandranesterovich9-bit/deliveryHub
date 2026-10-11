from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from pwdlib import PasswordHash

from app.database import User, get_db
from app.database import SessionLocal


router = APIRouter(prefix="/auth", tags=["Auth"])

password_hash = PasswordHash.recommended()


class RegisterRequest(BaseModel):
    name: str
    phone: str
    password: str


@router.post("/register")
async def register(user: RegisterRequest, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.phone == user.phone).first()

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="User with this phone already exists"
        )

    hashed_password = password_hash.hash(user.password)

    new_user = User(
        name=user.name,
        phone=user.phone,
        password_hash=hashed_password
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "id": new_user.id,
        "name": new_user.name,
        "phone": new_user.phone
    }