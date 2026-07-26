import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from logica.modules.content.models import TopicLevel
from logica.modules.guides.models import GuideOrigin, GuideStatus


class GuideSectionSpec(BaseModel):
    """Una sección pedida por el docente. `instructions` es lo que se le pasa al
    modelo como consigna de esa sección, así que su longitud mínima no es
    cosmética: "algo" produce prosa genérica."""

    heading: str = Field(min_length=2, max_length=200)
    instructions: str = Field(min_length=10, max_length=1000)


class GuidesFolderCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class GuidesFolderOut(BaseModel):
    id: uuid.UUID
    group_id: uuid.UUID
    name: str
    description: str | None
    auto_generate_template_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class GuidesFolderUpdateRequest(BaseModel):
    """Semántica de asignación, no de merge: `null` apaga la autogeneración. No
    hace falta distinguir "omitido" de "null" porque este PATCH tiene un solo
    campo — omitirlo sería una petición sin efecto, no una intención distinta."""

    auto_generate_template_id: uuid.UUID | None = None


class GuideTemplateCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    # Tope de 10 secciones: cada una es una llamada al modelo, así que esto es lo
    # que separa "una guía" de "agotar el rate limit del tier gratuito de Groq en
    # una sola petición".
    sections: list[GuideSectionSpec] = Field(min_length=1, max_length=10)
    tone: str = Field(min_length=2, max_length=50)
    target_level: TopicLevel


class GuideTemplateOut(BaseModel):
    id: uuid.UUID
    name: str
    sections: list[GuideSectionSpec]
    tone: str
    target_level: TopicLevel
    version: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class GuideGenerateRequest(BaseModel):
    folder_id: uuid.UUID
    template_id: uuid.UUID
    topic_id: uuid.UUID


class GuideUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=300)
    content_md: str | None = Field(default=None, max_length=100_000)


class GuideOut(BaseModel):
    id: uuid.UUID
    folder_id: uuid.UUID
    template_id: uuid.UUID | None
    topic_id: uuid.UUID
    title: str
    content_md: str
    origin: GuideOrigin
    status: GuideStatus
    published_at: datetime | None
    error_message: str | None
    sources: list[str] | None
    prompt_version: int | None
    created_at: datetime

    model_config = {"from_attributes": True}
