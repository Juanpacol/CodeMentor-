import uuid

from arq import ArqRedis
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from logica.core.arq_dep import get_arq_pool
from logica.core.permissions import require_role
from logica.db import get_db
from logica.modules.rubrics import service
from logica.modules.rubrics.models import RubricRun
from logica.modules.rubrics.schemas import (
    RubricItemOut,
    RubricRunCreateRequest,
    RubricRunDetailOut,
    RubricRunOut,
)
from logica.modules.users.models import User

router = APIRouter(tags=["rubrics"])

RequireTeacher = require_role("teacher", "admin")


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


@router.post("/rubric-runs/{run_id}/cancel", response_model=RubricRunOut)
async def cancel_rubric_run(
    run_id: uuid.UUID,
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
) -> RubricRun:
    run = await service.cancel_run(db, user, run_id)
    await db.commit()
    return run
