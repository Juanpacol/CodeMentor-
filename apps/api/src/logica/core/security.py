import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from logica.config import Settings, get_settings
from logica.db import get_db

if TYPE_CHECKING:
    from logica.modules.users.models import User

_hasher = PasswordHasher()

bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(raw_password: str) -> str:
    return _hasher.hash(raw_password)


def verify_password(raw_password: str, hashed_password: str) -> bool:
    try:
        return _hasher.verify(hashed_password, raw_password)
    except VerifyMismatchError:
        return False


class TokenPayload:
    def __init__(
        self,
        sub: uuid.UUID,
        institution_id: uuid.UUID,
        role: str,
        token_type: Literal["access", "refresh"],
        jti: str,
    ) -> None:
        self.sub = sub
        self.institution_id = institution_id
        self.role = role
        self.token_type = token_type
        self.jti = jti


def _encode(
    settings: Settings,
    *,
    user_id: uuid.UUID,
    institution_id: uuid.UUID,
    role: str,
    token_type: Literal["access", "refresh"],
    expires_delta: timedelta,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "inst": str(institution_id),
        "role": role,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(*, user_id: uuid.UUID, institution_id: uuid.UUID, role: str) -> str:
    settings = get_settings()
    return _encode(
        settings,
        user_id=user_id,
        institution_id=institution_id,
        role=role,
        token_type="access",
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(*, user_id: uuid.UUID, institution_id: uuid.UUID, role: str) -> str:
    settings = get_settings()
    return _encode(
        settings,
        user_id=user_id,
        institution_id=institution_id,
        role=role,
        token_type="refresh",
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str, *, expected_type: Literal["access", "refresh"]) -> TokenPayload:
    settings = get_settings()
    try:
        raw = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado"
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido"
        ) from exc

    if raw.get("type") != expected_type:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Tipo de token inválido"
        )

    return TokenPayload(
        sub=uuid.UUID(raw["sub"]),
        institution_id=uuid.UUID(raw["inst"]),
        role=raw["role"],
        token_type=raw["type"],
        jti=raw["jti"],
    )


def _revoked_key(jti: str) -> str:
    return f"revoked_refresh:{jti}"


async def revoke_refresh_token(redis: Redis, jti: str, ttl_seconds: int) -> None:
    await redis.set(_revoked_key(jti), "1", ex=ttl_seconds)


async def is_refresh_token_revoked(redis: Redis, jti: str) -> bool:
    return bool(await redis.exists(_revoked_key(jti)))


async def get_current_token_payload(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> TokenPayload:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autenticado")
    return decode_token(credentials.credentials, expected_type="access")


async def get_current_user(
    payload: TokenPayload = Depends(get_current_token_payload),
    db: AsyncSession = Depends(get_db),
) -> "User":
    from logica.modules.users.repository import get_user_by_id

    user = await get_user_by_id(db, payload.sub)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no válido")
    return user
