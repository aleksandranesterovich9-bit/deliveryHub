import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.statuses import UserRole

_PHONE_SEPARATORS = re.compile(r"[\s\-()]")


def normalize_phone(phone: str) -> str:
    """'+7 (999) 123-45-67' -> '+79991234567', so one person = one account."""
    return _PHONE_SEPARATORS.sub("", phone)


class UserRegister(BaseModel):
    name: str = Field(min_length=2, max_length=100, examples=["Alex"])
    phone: str = Field(pattern=r"^\+?\d{7,15}$", examples=["+79991234567"])
    password: str = Field(min_length=8, max_length=128, examples=["strong-password"])

    @field_validator("phone", mode="before")
    @classmethod
    def _normalize_phone(cls, value: str) -> str:
        return normalize_phone(value) if isinstance(value, str) else value


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: str
    role: UserRole
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
