"""Acceso a datos de asignaciones. Cada consulta filtra por `institution_id`
explícitamente (ADR-006: la multi-tenencia es 100% de aplicación, no hay RLS de
Postgres que sirva de red)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from logica.modules.assignments.models import Assignment
from logica.modules.evaluations.models import PracticeSubmission
from logica.modules.exercises.models import TopicExercise
from logica.modules.groups.models import Group, GroupMembership


async def get(
    db: AsyncSession, institution_id: uuid.UUID, assignment_id: uuid.UUID
) -> Assignment | None:
    stmt = select(Assignment).where(
        Assignment.institution_id == institution_id, Assignment.id == assignment_id
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def list_for_group(
    db: AsyncSession, institution_id: uuid.UUID, group_id: uuid.UUID
) -> list[Assignment]:
    stmt = (
        select(Assignment)
        .where(Assignment.institution_id == institution_id, Assignment.group_id == group_id)
        # Las que vencen primero arriba; las sin fecha al final (NULLS LAST) en
        # vez de encabezando la lista, que es lo que hace Postgres por defecto
        # con ASC y pondría "para cuando puedas" antes de lo urgente.
        .order_by(Assignment.due_at.asc().nullslast(), Assignment.created_at.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def list_for_student(
    db: AsyncSession, institution_id: uuid.UUID, student_id: uuid.UUID
) -> list[tuple[Assignment, str]]:
    """(asignación, nombre del grupo) de todos los grupos donde está matriculado.

    El nombre del grupo viaja acá porque el dashboard del estudiante mezcla
    asignaciones de varios grupos y sin él no podría decir de cuál es cada una.
    """
    stmt = (
        select(Assignment, Group.name)
        .join(Group, Group.id == Assignment.group_id)
        .join(GroupMembership, GroupMembership.group_id == Assignment.group_id)
        .where(
            Assignment.institution_id == institution_id,
            GroupMembership.student_id == student_id,
        )
        .order_by(Assignment.due_at.asc().nullslast(), Assignment.created_at.desc())
    )
    return [(row[0], row[1]) for row in (await db.execute(stmt)).all()]


async def exercise_ids_for_topic(db: AsyncSession, topic_id: uuid.UUID) -> set[uuid.UUID]:
    stmt = select(TopicExercise.exercise_id).where(TopicExercise.topic_id == topic_id)
    return set((await db.execute(stmt)).scalars().all())


async def solved_exercise_ids(db: AsyncSession, student_id: uuid.UUID) -> set[uuid.UUID]:
    """Los ejercicios que el estudiante ya resolvió BIEN alguna vez.

    Una sola consulta para todas sus asignaciones en vez de una por asignación:
    el dashboard carga de golpe y son decenas de asignaciones, no miles.
    """
    stmt = select(PracticeSubmission.exercise_id).where(
        PracticeSubmission.student_id == student_id,
        PracticeSubmission.correct.is_(True),
    )
    return set((await db.execute(stmt)).scalars().all())
