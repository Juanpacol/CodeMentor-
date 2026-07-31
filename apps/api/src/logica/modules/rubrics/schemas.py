import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from logica.modules.content.models import TopicLevel
from logica.modules.exercises.models import ExerciseType
from logica.modules.rubrics.models import RubricItemStatus, RubricRunStatus


class RubricItemSpec(BaseModel):
    topic_name: str = Field(min_length=2, max_length=200)
    level: TopicLevel = TopicLevel.basico
    # Material que el docente ya sabe que quiere para este tema. Se descarga con
    # las mismas defensas que cualquier URL de usuario (ver `ai/rag/acquire.py`).
    extra_urls: list[str] = Field(default_factory=list, max_length=5)


class RubricRunCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    language_id: uuid.UUID
    template_id: uuid.UUID
    # Nombre de la carpeta de guías donde aterriza todo. Si ya existe una con ese
    # nombre en el grupo, se reusa en vez de fallar: volver a correr una rúbrica
    # para agregar temas es un caso normal.
    folder_name: str = Field(min_length=2, max_length=200)
    items: list[RubricItemSpec] = Field(min_length=1)
    exercise_types: list[ExerciseType] = Field(min_length=1, max_length=4)
    acquire_content: bool = True


class RubricItemOut(BaseModel):
    id: uuid.UUID
    topic_name: str
    level: TopicLevel
    order_index: int
    topic_id: uuid.UUID | None
    guide_id: uuid.UUID | None
    sources_ingested: int
    exercises_created: int
    status: RubricItemStatus
    error_message: str | None
    # El "ver detalle" del docente: `error_message` dice qué pasó en lenguaje
    # llano, esto dice por qué (qué proveedor de IA, qué validación).
    error_code: str | None = None
    error_details: dict[str, Any] | None = None

    model_config = {"from_attributes": True}


class RubricRunOut(BaseModel):
    id: uuid.UUID
    group_id: uuid.UUID
    folder_id: uuid.UUID
    template_id: uuid.UUID
    language_id: uuid.UUID
    name: str
    exercise_types: list[str]
    acquire_content: bool
    status: RubricRunStatus
    error_message: str | None
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RubricRunDetailOut(BaseModel):
    """El poll target: run + ítems en una sola respuesta, para que la pantalla de
    progreso no tenga que encadenar dos peticiones cada 3 segundos."""

    run: RubricRunOut
    items: list[RubricItemOut]


class ExtractedTopicItem(BaseModel):
    topic_name: str = Field(min_length=2, max_length=200)
    level: TopicLevel = TopicLevel.basico
    order_index: int = 0


class DocumentExtractionResult(BaseModel):
    """Salida de `POST /rubric-runs/extract-topics`: un paso de *preview* puro
    (no crea `RubricRun` ni `RubricItem`), pensado para prellenar el textarea de
    temas que el docente ya conoce y sigue pudiendo editar antes de enviar."""

    # >MAX_ITEMS_PER_RUN (15) a propósito: el recorte final lo hace el docente en
    # el textarea, con el mismo aviso que ya existe para exceso de temas.
    items: list[ExtractedTopicItem] = Field(default_factory=list, max_length=30)
