"""Consultas de rúbricas. Igual que en `modules/guides/repository.py`, cada
función toma `institution_id` explícito incluso para leer una sola fila: la
multi-tenencia es 100% a nivel de aplicación (ADR-006) y un `db.get` suelto es
justo la forma de saltársela sin darse cuenta.

`RubricItem` no lleva `institution_id`: sus consultas pasan siempre por el run,
que sí lo tiene.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from logica.modules.rubrics.models import RubricItem, RubricRun


async def get_run(
    db: AsyncSession, institution_id: uuid.UUID, run_id: uuid.UUID
) -> RubricRun | None:
    result = await db.execute(
        select(RubricRun).where(RubricRun.id == run_id, RubricRun.institution_id == institution_id)
    )
    return result.scalar_one_or_none()


async def list_runs_for_group(
    db: AsyncSession, institution_id: uuid.UUID, group_id: uuid.UUID
) -> list[RubricRun]:
    result = await db.execute(
        select(RubricRun)
        .where(RubricRun.institution_id == institution_id, RubricRun.group_id == group_id)
        .order_by(RubricRun.created_at.desc())
    )
    return list(result.scalars().all())


async def list_items(db: AsyncSession, run_id: uuid.UUID) -> list[RubricItem]:
    result = await db.execute(
        select(RubricItem).where(RubricItem.run_id == run_id).order_by(RubricItem.order_index)
    )
    return list(result.scalars().all())
