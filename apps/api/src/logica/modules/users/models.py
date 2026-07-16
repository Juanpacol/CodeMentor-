import enum
import uuid

from sqlalchemy import ARRAY, Boolean, Enum, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from logica.core.mixins import TenantMixin, TimestampMixin, UUIDPkMixin
from logica.db import Base


class Role(enum.StrEnum):
    student = "student"
    teacher = "teacher"
    admin = "admin"


class Institution(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "institutions"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email_domains: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)


class User(UUIDPkMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("institution_id", "email", name="uq_user_institution_email"),
    )

    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    student_code: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role, name="user_role"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PasswordResetToken(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "password_reset_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
