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
from logica.modules.evaluations.repository import get_evaluation
from logica.modules.exercises.repository import get_exercise
from logica.modules.groups.service import get_group_with_access
from logica.modules.guides.repository import get_guide
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
    evaluation_id: uuid.UUID | None,
    guide_id: uuid.UUID | None,
    due_at: datetime | None,
) -> Assignment:
    await _ensure_teaches(db, user, group_id)

    # Se valida la tenencia del objetivo, no solo su existencia: sin esto un
    # docente podría asignar contenido de otra institución cuyo id conociera.
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
    if evaluation_id is not None:
        evaluation = await get_evaluation(db, evaluation_id)
        if evaluation is None or evaluation.institution_id != user.institution_id:
            raise NotFoundError("Evaluación no encontrada")
    if guide_id is not None:
        guide = await get_guide(db, user.institution_id, guide_id)
        if guide is None:
            raise NotFoundError("Guía no encontrada")

    assignment = Assignment(
        institution_id=user.institution_id,
        group_id=group_id,
        teacher_id=user.id,
        title=title,
        topic_id=topic_id,
        exercise_id=exercise_id,
        evaluation_id=evaluation_id,
        guide_id=guide_id,
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
    submitted_evaluations = await repository.submitted_evaluation_ids(db, student.id)
    out: list[StudentAssignmentOut] = []

    for assignment, group_name in rows:
        if assignment.evaluation_id is not None:
            # Examen: "cumplida" es "ya la presentó", no un conteo de
            # ejercicios — la evaluación se presenta entera de una vez.
            done = assignment.evaluation_id in submitted_evaluations
            total, solved_count = 1, int(done)
        elif assignment.guide_id is not None:
            # Taller: sin señal de lectura en la plataforma todavía (ver
            # docstring del modelo) — queda pendiente hasta que exista una.
            done, total, solved_count = False, 0, 0
        else:
            if assignment.exercise_id is not None:
                targets = {assignment.exercise_id}
            else:
                assert assignment.topic_id is not None  # el CheckConstraint lo garantiza
                targets = await repository.exercise_ids_for_topic(db, assignment.topic_id)
            solved_count = len(targets & solved)
            total = len(targets)
            # Un tema sin ejercicios no está "cumplido": no hay nada que
            # resolver todavía, y decir que sí le escondería al estudiante
            # que el docente asignó algo que aún no tiene contenido.
            done = total > 0 and solved_count == total

        out.append(
            StudentAssignmentOut(
                id=assignment.id,
                group_id=assignment.group_id,
                group_name=group_name,
                title=assignment.title,
                topic_id=assignment.topic_id,
                exercise_id=assignment.exercise_id,
                evaluation_id=assignment.evaluation_id,
                guide_id=assignment.guide_id,
                due_at=assignment.due_at,
                done=done,
                total_exercises=total,
                solved_exercises=solved_count,
            )
        )

    return out
