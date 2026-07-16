import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from logica.modules.content.models import TopicGroupStateValue, TopicLevel


class LanguageCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(min_length=1, max_length=50, pattern=r"^[a-z0-9_-]+$")
    syntax_mode: str = Field(min_length=1, max_length=50)


class LanguageOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    syntax_mode: str
    is_active: bool

    model_config = {"from_attributes": True}


class TopicCreateRequest(BaseModel):
    language_id: uuid.UUID
    name: str = Field(min_length=2, max_length=200)
    level: TopicLevel
    order_index: int = 0


class TopicUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    level: TopicLevel | None = None
    order_index: int | None = None


class TopicOut(BaseModel):
    id: uuid.UUID
    institution_id: uuid.UUID
    language_id: uuid.UUID
    name: str
    level: TopicLevel
    order_index: int
    version: int

    model_config = {"from_attributes": True}


class ScheduleEnableRequest(BaseModel):
    enable_at: datetime


class CurriculumTopicOut(BaseModel):
    topic: TopicOut
    state: TopicGroupStateValue
    enabled_at: datetime | None
    scheduled_enable_at: datetime | None
