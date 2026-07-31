import uuid

from arq import ArqRedis
from fastapi import APIRouter, Depends, Request, UploadFile
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from logica.ai.agents.rubric_topic_extractor import extract_topics_from_text
from logica.core.arq_dep import get_arq_pool
from logica.core.errors import ValidationDomainError
from logica.core.permissions import require_permission
from logica.core.rate_limit import user_limiter
from logica.core.redis_dep import get_redis
from logica.db import get_db
from logica.modules.rubrics import document_extraction, service
from logica.modules.rubrics.models import RubricRun
from logica.modules.rubrics.schemas import (
    DocumentExtractionResult,
    RubricItemOut,
    RubricRunCreateRequest,
    RubricRunDetailOut,
    RubricRunOut,
)
from logica.modules.users.models import User

router = APIRouter(tags=["rubrics"])

RequireTeacher = require_permission("rubrics:manage")


@router.post("/groups/{group_id}/rubric-runs", response_model=RubricRunOut, status_code=202)
async def create_rubric_run(
    group_id: uuid.UUID,
    payload: RubricRunCreateRequest,
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> RubricRun:
    """202: la corrida son minutos de trabajo del worker. Devuelve la fila en
    `pending` y el cliente hace polling sobre `GET /rubric-runs/{id}`."""
    run = await service.request_rubric_run(
        db,
        arq_pool,
        user,
        group_id=group_id,
        language_id=payload.language_id,
        template_id=payload.template_id,
        folder_name=payload.folder_name,
        name=payload.name,
        items=payload.items,
        exercise_types=[t.value for t in payload.exercise_types],
        acquire_content=payload.acquire_content,
    )
    await db.commit()
    return run


@router.get("/groups/{group_id}/rubric-runs", response_model=list[RubricRunOut])
async def list_rubric_runs(
    group_id: uuid.UUID,
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
) -> list[RubricRun]:
    return await service.list_runs(db, user, group_id)


@router.get("/rubric-runs/{run_id}", response_model=RubricRunDetailOut)
async def get_rubric_run(
    run_id: uuid.UUID,
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
) -> RubricRunDetailOut:
    """El poll target. Devuelve run + ítems juntos para que la pantalla de
    progreso no encadene dos peticiones cada 3 segundos."""
    run = await service.get_run(db, user, run_id)
    items = await service.list_items(db, user, run_id)
    return RubricRunDetailOut(
        run=RubricRunOut.model_validate(run),
        items=[RubricItemOut.model_validate(item) for item in items],
    )


@router.post("/rubric-runs/extract-topics", response_model=DocumentExtractionResult)
@user_limiter.limit("10/minute")
async def extract_topics_from_document(
    request: Request,
    file: UploadFile,
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> DocumentExtractionResult:
    """Paso de *preview* puro: extrae los temas de un PDF/DOCX de rúbrica
    institucional para prellenar el textarea de `POST /rubric-runs`, pero no
    crea ningún `RubricRun` — el docente revisa/edita antes de enviar."""
    filename = file.filename or ""
    if not filename.lower().endswith(document_extraction.ALLOWED_EXTENSIONS):
        raise ValidationDomainError(
            "Formato de archivo no soportado",
            hint="Solo se aceptan archivos .pdf o .docx.",
        )
    if file.content_type not in document_extraction.ALLOWED_CONTENT_TYPES:
        raise ValidationDomainError(
            "Formato de archivo no soportado",
            hint="Solo se aceptan archivos .pdf o .docx.",
        )

    raw = await file.read()
    if len(raw) > document_extraction.MAX_FILE_BYTES:
        raise ValidationDomainError(
            "El documento es demasiado grande",
            hint=f"El máximo es {document_extraction.MAX_FILE_BYTES // 1_000_000} MB.",
        )

    if filename.lower().endswith(".pdf"):
        raw_text = document_extraction.extract_text_from_pdf(raw)
    else:
        raw_text = document_extraction.extract_text_from_docx(raw)

    return await extract_topics_from_text(db, redis, user=user, raw_text=raw_text)


@router.post("/rubric-runs/{run_id}/cancel", response_model=RubricRunOut)
async def cancel_rubric_run(
    run_id: uuid.UUID,
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> RubricRun:
    run = await service.cancel_run(db, redis, user, run_id)
    await db.commit()
    return run
