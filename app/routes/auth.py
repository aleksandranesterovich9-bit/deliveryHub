import os
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel, Field
import jwt
from jwt.exceptions import InvalidTokenError
from fastapi import Depends, HTTPException, status,APIRouter
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pwdlib import PasswordHash

from app.database import User, get_db

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is missing in .env")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

password_hash = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=5, max_length=20)
    password: str = Field(min_length=8, max_length=128)

def create_access_token(user_id: int) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": str(user_id),
        "exp": expires_at,
    }

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

@router.post('/register',status_code=status.HTTP_201_CREATED)
def register(user_data:RegisterRequest,db:Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.phone==user_data.phone).first()

    if existing_user: 
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this phone already exists",
        )

    user = User(name=user_data.name,phone=user_data.phone, password_hash=password_hash.hash(user_data.password))
    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "id": user.id,
        "name": user.name,
        "phone": user.phone,
    }

@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = (
        db.query(User)
        .filter(User.phone == form_data.username)
        .first()
    )

    if user is None or not password_hash.verify(
        form_data.password, user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect phone number or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(user.id)

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )
        subject = payload.get("sub")

        if subject is None:
            raise credentials_exception

        user_id = int(subject)

    except (InvalidTokenError, ValueError):
        raise credentials_exception

    user = db.get(User, user_id)

    if user is None:
        raise credentials_exception

    return user


@router.get("/me")
def read_current_user(
    current_user: User = Depends(get_current_user),
):
    return {
        "id": current_user.id,
        "name": current_user.name,
        "phone": current_user.phone,
    }
