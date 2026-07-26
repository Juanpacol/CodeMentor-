import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from logica.core.mixins import TenantMixin, TimestampMixin, UUIDPkMixin
from logica.db import Base
from logica.modules.content.models import TopicLevel


class GuidesFolder(UUIDPkMixin, TenantMixin, TimestampMixin, Base):
    """Fase 16: cómo un docente organiza las guías de UN grupo (p.ej. "Guías de
    laboratorio 10-A"). El alcance es por grupo y no por institución porque el
    ciclo que las genera solo existe por grupo — el cron se dispara desde
    `TopicGroupState`, que es (tema, grupo)."""

    __tablename__ = "guides_folders"
    __table_args__ = (
        UniqueConstraint("institution_id", "group_id", "name", name="uq_guides_folder_group_name"),
    )

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("groups.id"), nullable=False, index=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Opt-in a la autogeneración: con una plantilla acá, el cron
    # (`workers/settings.py::generate_guides_for_enabled_topics_job`) redacta un
    # borrador cuando el docente habilita un tema para este grupo. NULL = el cron
    # ignora la carpeta. Es una FK explícita y no un booleano + heurística porque
    # un grupo puede tener varias plantillas: adivinar cuál usar haría que crear
    # una plantilla nueva cambiara en silencio lo que la plataforma genera.
    auto_generate_template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("guide_templates.id"), nullable=True
    )


class GuideTemplate(UUIDPkMixin, TenantMixin, TimestampMixin, Base):
    """Qué secciones quiere el docente en cada guía, definido una sola vez.

    Inmutable-versionada igual que los prompts (`ai/harness/prompts`): editar
    una plantilla crea la fila `version=N+1` en vez de mutar la existente, para
    que una guía generada hace tres meses siga siendo explicable contra la
    plantilla exacta que la produjo. Sin esto, `Guide.template_id` apuntaría a
    un texto que ya cambió y la trazabilidad sería falsa."""

    __tablename__ = "guide_templates"
    __table_args__ = (
        UniqueConstraint(
            "institution_id", "name", "version", name="uq_guide_template_name_version"
        ),
    )

    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # list[{"heading": str, "instructions": str}] — el orden de la lista es el
    # orden de las secciones en la guía. JSON y no una tabla hija porque nunca
    # se consulta una sección por separado: siempre se leen todas juntas para
    # generar o para mostrar.
    sections: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False)
    tone: Mapped[str] = mapped_column(String(50), nullable=False)
    target_level: Mapped[TopicLevel] = mapped_column(
        Enum(TopicLevel, name="topic_level"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class GuideOrigin(enum.StrEnum):
    ai = "ai"
    manual = "manual"


class GuideStatus(enum.StrEnum):
    """`generating` y `failed` existen porque una `Guide` es su propio job de
    polling: `POST /ai/guides/generate` crea la fila y devuelve 202, y el worker
    la completa. No hay tabla `GuideJob` como sí la hay para reportes
    (`reports/models.py::ReportJob`) — ahí el producto es un archivo en disco y
    hace falta una fila aparte para rastrearlo; acá el producto ES la fila."""

    generating = "generating"
    draft = "draft"
    published = "published"
    archived = "archived"
    failed = "failed"


class Guide(UUIDPkMixin, TenantMixin, TimestampMixin, Base):
    """Una guía de clase para un tema. Nace `origin=ai, status=generating` y pasa
    a `draft` — invisible al estudiante hasta que un docente la publica
    explícitamente (§9.2: la plataforma nunca publica contenido de IA sola).

    El grupo no se duplica acá: se deriva por `folder_id → GuidesFolder.group_id`,
    que es la única fuente de verdad."""

    __tablename__ = "guides"

    folder_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("guides_folders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Nullable y sin CASCADE: una guía `origin=manual` no viene de plantilla, y
    # las plantillas nunca se borran (son inmutables), así que la FK no puede
    # quedar colgando por un DELETE.
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("guide_templates.id"), nullable=True
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id"), nullable=False, index=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    # Vacío mientras `status=generating`. No nullable: simplifica el frontend,
    # que nunca tiene que distinguir "sin contenido" de "contenido nulo".
    content_md: Mapped[str] = mapped_column(Text, nullable=False, default="")
    origin: Mapped[GuideOrigin] = mapped_column(
        Enum(GuideOrigin, name="guide_origin"), nullable=False
    )
    status: Mapped[GuideStatus] = mapped_column(
        Enum(GuideStatus, name="guide_status"), nullable=False, default=GuideStatus.generating
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Títulos de RagDocument que fundamentaron el contenido — mismo idioma que
    # `TutorMessage.sources`: el docente verifica de qué material salió en vez
    # de confiar ciegamente en el LLM.
    sources: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    prompt_version: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Sin UniqueConstraint en (folder_id, topic_id) a propósito: regenerar una
    # guía para un tema que ya la tiene es un caso de uso normal (la primera
    # salió mal), y una restricción lo convertiría en un 409. El cron de
    # `workers/settings.py` hace la verificación de "ya existe" explícitamente
    # para no duplicar por su cuenta.
