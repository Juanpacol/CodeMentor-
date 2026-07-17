import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from logica.modules.evaluations.models import (
    Evaluation,
    EvaluationAnswer,
    EvaluationAttempt,
    EvaluationExercise,
    PracticeSubmission,
)


async def get_evaluation(db: AsyncSession, evaluation_id: uuid.UUID) -> Evaluation | None:
    return await db.get(Evaluation, evaluation_id)


async def list_evaluations_for_group(db: AsyncSession, group_id: uuid.UUID) -> list[Evaluation]:
    stmt = (
        select(Evaluation)
        .where(Evaluation.group_id == group_id)
        .order_by(Evaluation.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_evaluation_exercises(
    db: AsyncSession, evaluation_id: uuid.UUID
) -> list[EvaluationExercise]:
    stmt = (
        select(EvaluationExercise)
        .where(EvaluationExercise.evaluation_id == evaluation_id)
        .order_by(EvaluationExercise.order_index)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_evaluation_exercise(
    db: AsyncSession, evaluation_exercise_id: uuid.UUID
) -> EvaluationExercise | None:
    return await db.get(EvaluationExercise, evaluation_exercise_id)


async def get_attempt(
    db: AsyncSession, evaluation_id: uuid.UUID, student_id: uuid.UUID
) -> EvaluationAttempt | None:
    stmt = select(EvaluationAttempt).where(
        EvaluationAttempt.evaluation_id == evaluation_id,
        EvaluationAttempt.student_id == student_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_attempt_by_id(db: AsyncSession, attempt_id: uuid.UUID) -> EvaluationAttempt | None:
    return await db.get(EvaluationAttempt, attempt_id)


async def get_answer(
    db: AsyncSession, attempt_id: uuid.UUID, evaluation_exercise_id: uuid.UUID
) -> EvaluationAnswer | None:
    stmt = select(EvaluationAnswer).where(
        EvaluationAnswer.attempt_id == attempt_id,
        EvaluationAnswer.evaluation_exercise_id == evaluation_exercise_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_answers_for_attempt(
    db: AsyncSession, attempt_id: uuid.UUID
) -> list[EvaluationAnswer]:
    stmt = select(EvaluationAnswer).where(EvaluationAnswer.attempt_id == attempt_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_answer_by_id(db: AsyncSession, answer_id: uuid.UUID) -> EvaluationAnswer | None:
    return await db.get(EvaluationAnswer, answer_id)


async def list_pending_manual_review(
    db: AsyncSession, evaluation_id: uuid.UUID
) -> list[EvaluationAnswer]:
    stmt = (
        select(EvaluationAnswer)
        .join(
            EvaluationExercise,
            EvaluationExercise.id == EvaluationAnswer.evaluation_exercise_id,
        )
        .where(
            EvaluationExercise.evaluation_id == evaluation_id,
            EvaluationAnswer.needs_manual_review.is_(True),
            EvaluationAnswer.manual_score.is_(None),
        )
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_answers_for_evaluation(
    db: AsyncSession, evaluation_id: uuid.UUID
) -> list[tuple[EvaluationAnswer, uuid.UUID]]:
    """All (answer, student_id) pairs across every student's attempt — the
    teacher-facing view used to browse submissions (e.g. to pick one for a
    code-integrity check, §9.2), as opposed to `list_pending_manual_review`
    which only surfaces answers still awaiting a grade."""
    stmt = (
        select(EvaluationAnswer, EvaluationAttempt.student_id)
        .join(EvaluationExercise, EvaluationExercise.id == EvaluationAnswer.evaluation_exercise_id)
        .join(EvaluationAttempt, EvaluationAttempt.id == EvaluationAnswer.attempt_id)
        .where(EvaluationExercise.evaluation_id == evaluation_id)
    )
    result = await db.execute(stmt)
    return [(answer, student_id) for answer, student_id in result.all()]


async def list_attempts_for_evaluation(
    db: AsyncSession, evaluation_id: uuid.UUID
) -> list[EvaluationAttempt]:
    stmt = select(EvaluationAttempt).where(EvaluationAttempt.evaluation_id == evaluation_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_practice_submission(
    db: AsyncSession, submission_id: uuid.UUID
) -> PracticeSubmission | None:
    return await db.get(PracticeSubmission, submission_id)
