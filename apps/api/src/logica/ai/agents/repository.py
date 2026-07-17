import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from logica.ai.agents.models import CodeIntegrityAlert, TutorMessage
from logica.modules.evaluations.models import EvaluationAnswer, EvaluationExercise


async def create_tutor_message(db: AsyncSession, message: TutorMessage) -> TutorMessage:
    db.add(message)
    await db.flush()
    await db.refresh(message)
    return message


async def list_tutor_messages(
    db: AsyncSession, group_id: uuid.UUID, student_id: uuid.UUID, exercise_id: uuid.UUID
) -> list[TutorMessage]:
    stmt = (
        select(TutorMessage)
        .where(
            TutorMessage.group_id == group_id,
            TutorMessage.student_id == student_id,
            TutorMessage.exercise_id == exercise_id,
        )
        .order_by(TutorMessage.created_at)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_code_integrity_alert(
    db: AsyncSession, alert: CodeIntegrityAlert
) -> CodeIntegrityAlert:
    db.add(alert)
    await db.flush()
    await db.refresh(alert)
    return alert


async def list_alerts_for_evaluation(
    db: AsyncSession, evaluation_id: uuid.UUID
) -> list[CodeIntegrityAlert]:
    stmt = (
        select(CodeIntegrityAlert)
        .join(EvaluationAnswer, EvaluationAnswer.id == CodeIntegrityAlert.evaluation_answer_id)
        .join(EvaluationExercise, EvaluationExercise.id == EvaluationAnswer.evaluation_exercise_id)
        .where(EvaluationExercise.evaluation_id == evaluation_id)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
