import secrets
import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from logica.core.audit import record_audit
from logica.core.errors import NotFoundError, PermissionDeniedError, ValidationDomainError
from logica.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from logica.modules.users.models import Institution, PasswordResetToken, Role, User
from logica.modules.users.repository import (
    find_institution_by_email_domain,
    find_user_by_email_any_institution,
    get_user_by_email,
    get_user_by_id,
)
from logica.modules.users.schemas import RegisterRequest, TokenPair

logger = structlog.get_logger()


async def _resolve_institution(
    db: AsyncSession, email: str, student_code: str | None, role: Role
) -> Institution:
    institution = await find_institution_by_email_domain(db, email)
    if institution is not None:
        return institution

    if role == Role.student and student_code:
        # Fallback for the current single-institution deployment: a student
        # without an institutional email can still register with a valid
        # student code. Multi-institution self-service onboarding (§5.3) will
        # replace this with an explicit institution/invite selection.
        result = await db.execute(select(Institution).limit(2))
        institutions = result.scalars().all()
        if len(institutions) == 1:
            return institutions[0]

    raise ValidationDomainError(
        "No se pudo verificar tu identidad institucional: usa el correo del "
        "colegio o proporciona tu código de estudiante."
    )


async def register(db: AsyncSession, payload: RegisterRequest) -> User:
    if payload.role == Role.admin:
        raise PermissionDeniedError("El rol administrador no se asigna por auto-registro")

    institution = await _resolve_institution(db, payload.email, payload.student_code, payload.role)

    existing = await get_user_by_email(db, institution.id, payload.email)
    if existing is not None:
        raise ValidationDomainError("Ya existe una cuenta con este correo")

    user = User(
        institution_id=institution.id,
        email=payload.email.lower(),
        student_code=payload.student_code,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


def _issue_token_pair(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(
            user_id=user.id, institution_id=user.institution_id, role=user.role.value
        ),
        refresh_token=create_refresh_token(
            user_id=user.id, institution_id=user.institution_id, role=user.role.value
        ),
    )


async def authenticate(db: AsyncSession, email: str, password: str) -> TokenPair:
    institution = await find_institution_by_email_domain(db, email)
    user = None
    if institution is not None:
        user = await get_user_by_email(db, institution.id, email)

    if user is None:
        # Domain-based resolution doesn't cover every account (e.g. students
        # bulk-enrolled by CSV with a personal email).
        user = await find_user_by_email_any_institution(db, email)

    if user is None or not verify_password(password, user.hashed_password):
        raise ValidationDomainError("Correo o contraseña incorrectos")
    if not user.is_active:
        raise PermissionDeniedError("Cuenta inactiva")

    return _issue_token_pair(user)


async def refresh_tokens(db: AsyncSession, refresh_token: str) -> TokenPair:
    payload = decode_token(refresh_token, expected_type="refresh")
    user = await get_user_by_id(db, payload.sub)
    if user is None or not user.is_active:
        raise ValidationDomainError("Sesión inválida")
    return _issue_token_pair(user)


async def request_password_reset(db: AsyncSession, email: str) -> str | None:
    """Returns the raw reset token in dev (no real email provider until Fase 9);
    always returns None to the caller-facing response to avoid user enumeration."""
    user = None
    institution = await find_institution_by_email_domain(db, email)
    if institution is not None:
        user = await get_user_by_email(db, institution.id, email)
    if user is None:
        user = await find_user_by_email_any_institution(db, email)
    if user is None:
        return None

    raw_token = secrets.token_urlsafe(32)
    entry = PasswordResetToken(user_id=user.id, token_hash=hash_password(raw_token))
    db.add(entry)
    await db.flush()
    logger.info("password_reset_requested", user_id=str(user.id))
    return raw_token


async def confirm_password_reset(db: AsyncSession, token: str, new_password: str) -> None:
    result = await db.execute(select(PasswordResetToken).where(PasswordResetToken.used.is_(False)))
    candidates = result.scalars().all()
    matched = next(
        (c for c in candidates if verify_password(token, c.token_hash)),
        None,
    )
    if matched is None:
        raise ValidationDomainError("Token de recuperación inválido o expirado")

    user = await get_user_by_id(db, matched.user_id)
    if user is None:
        raise NotFoundError("Usuario no encontrado")

    user.hashed_password = hash_password(new_password)
    matched.used = True
    await db.flush()
    await record_audit(
        db,
        institution_id=user.institution_id,
        actor_user_id=user.id,
        action="password_reset",
        target_type="user",
        target_id=str(user.id),
    )


async def update_profile(db: AsyncSession, user: User, full_name: str | None) -> User:
    if full_name:
        user.full_name = full_name
        await db.flush()
        await db.refresh(user)
    return user


async def change_role(
    db: AsyncSession, actor: User, target_user_id: uuid.UUID, new_role: Role
) -> User:
    if actor.role != Role.admin:
        raise PermissionDeniedError("Solo un administrador puede cambiar roles")

    target = await get_user_by_id(db, target_user_id)
    if target is None or target.institution_id != actor.institution_id:
        raise NotFoundError("Usuario no encontrado")

    previous_role = target.role
    target.role = new_role
    await db.flush()
    await record_audit(
        db,
        institution_id=actor.institution_id,
        actor_user_id=actor.id,
        action="role_change",
        target_type="user",
        target_id=str(target.id),
        details={"previous_role": previous_role.value, "new_role": new_role.value},
    )
    return target
