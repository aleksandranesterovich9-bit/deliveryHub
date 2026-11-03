from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import CurrentUser, LoginLimiterDep, SessionDep
from app.application.commands.auth import (
    LoginUser,
    RegisterUser,
    handle_login,
    handle_register_user,
)
from app.db.models import User
from app.schemas.auth import Token, UserRead, UserRegister, normalize_phone

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(body: UserRegister, session: SessionDep) -> User:
    user_id = await handle_register_user(
        RegisterUser(name=body.name, phone=body.phone, password=body.password), session
    )
    return await session.get(User, user_id)


@router.post("/login", response_model=Token)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: SessionDep,
    limiter: LoginLimiterDep,
) -> Token:
    """OAuth2 password flow: put the **phone** into the `username` field."""
    token = await handle_login(
        LoginUser(phone=normalize_phone(form.username), password=form.password), session, limiter
    )
    return Token(access_token=token)


@router.get("/me", response_model=UserRead)
async def me(user: CurrentUser) -> User:
    return user
