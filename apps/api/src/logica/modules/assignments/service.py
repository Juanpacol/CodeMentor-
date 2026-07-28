"""Servicio de asignaciones: lo que el docente pide, con fecha límite, y lo que
al estudiante le falta.

El estado "cumplida" NO se persiste: se resuelve contra los envíos correctos de
práctica del estudiante. Una columna `done` sería una segunda fuente de verdad
que habría que actualizar en cada envío y que se desincronizaría en cuanto un
ejercicio se agregue o quite del tema.
"""

import uuid
from datetime import datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from logica.core.errors import NotFoundError, PermissionDeniedError
from logica.modules.assignments import repository
from logica.modules.assignments.models import Assignment
from logica.modules.assignments.schemas import StudentAssignmentOut
from logica.modules.content.repository import get_topic
from logica.modules.exercises.repository import get_exercise
from logica.modules.groups.service import get_group_with_access
from logica.modules.users.models import Role, User

logger = structlog.get_logger()


def _ensure_teacher(user: User) -> None:
    if user.role not in (Role.teacher, Role.admin):
        raise PermissionDeniedError("Solo un docente o administrador puede gestionar asignaciones")


async def _ensure_teaches(db: AsyncSession, user: User, group_id: uuid.UUID) -> None:
    _ensure_teacher(user)
    _, is_teacher_view = await get_group_with_access(db, user, group_id)
    if not is_teacher_view:
        raise PermissionDeniedError("No administras este grupo")


async def create_assignment(
    db: AsyncSession,
    user: User,
    *,
    group_id: uuid.UUID,
    title: str,
    topic_id: uuid.UUID | None,
    exercise_id: uuid.UUID | None,
    due_at: datetime | None,
) -> Assignment:
    await _ensure_teaches(db, user, group_id)

    # Se valida la tenencia del objetivo, no solo su existencia: sin esto un
    # docente podría asignar el tema de otra institución cuyo id conociera.
    if topic_id is not None:
        topic = await get_topic(db, topic_id)
        if topic is None or topic.institution_id != user.institution_id:
            raise NotFoundError("Tema no encontrado")
    if exercise_id is not None:
        # `get_exercise` no filtra por institución (recibe solo el id), así que
        # la comprobación de tenencia va acá — igual que con el tema.
        exercise = await get_exercise(db, exercise_id)
        if exercise is None or exercise.institution_id != user.institution_id:
            raise NotFoundError("Ejercicio no encontrado")

    assignment = Assignment(
        institution_id=user.institution_id,
        group_id=group_id,
        teacher_id=user.id,
        title=title,
        topic_id=topic_id,
        exercise_id=exercise_id,
        due_at=due_at,
    )
    db.add(assignment)
    await db.flush()
    await db.refresh(assignment)
    logger.info(
        "assignment_created",
        assignment_id=str(assignment.id),
        group_id=str(group_id),
        due_at=due_at.isoformat() if due_at else None,
    )
    return assignment


async def list_assignments(db: AsyncSession, user: User, group_id: uuid.UUID) -> list[Assignment]:
    await _ensure_teaches(db, user, group_id)
    return await repository.list_for_group(db, user.institution_id, group_id)


async def update_assignment(
    db: AsyncSession,
    user: User,
    assignment_id: uuid.UUID,
    *,
    title: str | None,
    due_at: datetime | None,
) -> Assignment:
    assignment = await repository.get(db, user.institution_id, assignment_id)
    if assignment is None:
        raise NotFoundError("Asignación no encontrada")
    await _ensure_teaches(db, user, assignment.group_id)

    if title is not None:
        assignment.title = title
    # `due_at` se asigna siempre, incluso None: es cómo se quita una fecha
    # límite ("para cuando puedas"). Un `if due_at is not None` haría imposible
    # deshacer una fecha puesta por error.
    assignment.due_at = due_at
    await db.flush()
    await db.refresh(assignment)
    return assignment


async def delete_assignment(db: AsyncSession, user: User, assignment_id: uuid.UUID) -> None:
    assignment = await repository.get(db, user.institution_id, assignment_id)
    if assignment is None:
        raise NotFoundError("Asignación no encontrada")
    await _ensure_teaches(db, user, assignment.group_id)
    await db.delete(assignment)
    await db.flush()


async def list_my_assignments(db: AsyncSession, student: User) -> list[StudentAssignmentOut]:
    """Lo pendiente del estudiante, de todos sus grupos, con lo cumplido resuelto.

    Los ejercicios resueltos se consultan UNA vez para todas las asignaciones:
    una consulta por asignación multiplicaría las idas a la BD por algo que el
    dashboard carga de golpe.
    """
    rows = await repository.list_for_student(db, student.institution_id, student.id)
    if not rows:
        return []

    solved = await repository.solved_exercise_ids(db, student.id)
    out: list[StudentAssignmentOut] = []

    for assignment, group_name in rows:
        if assignment.exercise_id is not None:
            targets = {assignment.exercise_id}
        else:
            assert assignment.topic_id is not None  # el CheckConstraint lo garantiza
            targets = await repository.exercise_ids_for_topic(db, assignment.topic_id)

        solved_here = len(targets & solved)
        out.append(
            StudentAssignmentOut(
                id=assignment.id,
                group_id=assignment.group_id,
                group_name=group_name,
                title=assignment.title,
                topic_id=assignment.topic_id,
                exercise_id=assignment.exercise_id,
                due_at=assignment.due_at,
                # Un tema sin ejercicios no está "cumplido": no hay nada que
                # resolver todavía, y decir que sí le escondería al estudiante
                # que el docente asignó algo que aún no tiene contenido.
                done=len(targets) > 0 and solved_here == len(targets),
                total_exercises=len(targets),
                solved_exercises=solved_here,
            )
        )

    return out
