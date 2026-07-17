from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from logica.core.rate_limit import limiter
from logica.core.security import get_current_user
from logica.db import get_db
from logica.modules.users import service
from logica.modules.users.models import User
from logica.modules.users.schemas import (
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    ProfileUpdateRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserOut,
)

auth_router = APIRouter(prefix="/auth", tags=["auth"])
users_router = APIRouter(prefix="/users", tags=["users"])


@auth_router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/hour")
async def register(
    request: Request, payload: RegisterRequest, db: AsyncSession = Depends(get_db)
) -> User:
    user = await service.register(db, payload)
    await db.commit()
    return user


@auth_router.post("/login", response_model=TokenPair)
@limiter.limit("10/minute")
async def login(
    request: Request, payload: LoginRequest, db: AsyncSession = Depends(get_db)
) -> TokenPair:
    tokens = await service.authenticate(db, payload.email, payload.password)
    await db.commit()
    return tokens


@auth_router.post("/refresh", response_model=TokenPair)
@limiter.limit("60/minute")
async def refresh(
    request: Request, payload: RefreshRequest, db: AsyncSession = Depends(get_db)
) -> TokenPair:
    tokens = await service.refresh_tokens(db, payload.refresh_token)
    await db.commit()
    return tokens


@auth_router.post("/password-reset/request", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/hour")
async def password_reset_request(
    request: Request, payload: PasswordResetRequest, db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    await service.request_password_reset(db, payload.email)
    await db.commit()
    return {"detail": "Si el correo existe, se enviaron instrucciones de recuperación"}


@auth_router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/hour")
async def password_reset_confirm(
    request: Request, payload: PasswordResetConfirm, db: AsyncSession = Depends(get_db)
) -> None:
    await service.confirm_password_reset(db, payload.token, payload.new_password)
    await db.commit()


@users_router.get("/me", response_model=UserOut)
async def read_me(user: User = Depends(get_current_user)) -> User:
    return user


@users_router.patch("/me", response_model=UserOut)
async def update_me(
    payload: ProfileUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    updated = await service.update_profile(db, user, payload.full_name)
    await db.commit()
    return updated
