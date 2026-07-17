import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from logica.core.permissions import require_role
from logica.core.redis_dep import get_redis
from logica.core.security import get_current_user
from logica.db import get_db
from logica.modules.evaluations import service
from logica.modules.evaluations.schemas import (
    AnswerSummaryOut,
    AttemptResultOut,
    EvaluationCreateRequest,
    EvaluationOut,
    ManualReviewItemOut,
    ManualReviewSubmitRequest,
    PracticeExerciseOut,
    PracticeResultOut,
    PracticeSubmitRequest,
    QuestionResultOut,
    RankingEntryOut,
    SubmitAnswerRequest,
    TakeEvaluationOut,
    TakeExerciseOut,
)
from logica.modules.users.models import User

router = APIRouter(tags=["evaluations"])

RequireTeacher = require_role("teacher", "admin")


@router.post("/evaluations", response_model=EvaluationOut, status_code=201)
async def create_evaluation(
    payload: EvaluationCreateRequest,
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
) -> EvaluationOut:
    evaluation = await service.create_evaluation(
        db,
        user,
        payload.group_id,
        payload.title,
        payload.mode,
        payload.up_to_topic_id,
        payload.duration_minutes,
        payload.is_ranked,
        payload.exercise_ids,
    )
    await db.commit()
    return EvaluationOut.model_validate(evaluation)


@router.get("/groups/{group_id}/evaluations", response_model=list[EvaluationOut])
async def list_group_evaluations(
    group_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[EvaluationOut]:
    evaluations = await service.list_group_evaluations(db, user, group_id)
    return [EvaluationOut.model_validate(e) for e in evaluations]


@router.get("/evaluations/{evaluation_id}/take", response_model=TakeEvaluationOut)
async def take_evaluation(
    evaluation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TakeEvaluationOut:
    evaluation, attempt, pairs = await service.start_or_get_attempt(db, user, evaluation_id)
    await db.commit()

    exercises = [
        TakeExerciseOut(
            evaluation_exercise_id=ee.id,
            order_index=ee.order_index,
            points=ee.points,
            exercise_id=exercise.id,
            type=exercise.type,
            title=exercise.title,
            content=service.sanitize_exercise_content(exercise),
        )
        for ee, exercise in sorted(pairs, key=lambda p: p[0].order_index)
    ]

    deadline = None
    if evaluation.duration_minutes is not None:
        deadline = attempt.started_at + timedelta(minutes=evaluation.duration_minutes)

    return TakeEvaluationOut(
        evaluation=EvaluationOut.model_validate(evaluation),
        attempt_id=attempt.id,
        started_at=attempt.started_at,
        deadline=deadline,
        exercises=exercises,
    )


@router.post("/evaluations/{evaluation_id}/answers", status_code=201)
async def submit_answer(
    evaluation_id: uuid.UUID,
    payload: SubmitAnswerRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    await service.submit_answer(
        db, user, evaluation_id, payload.evaluation_exercise_id, payload.answer
    )
    await db.commit()
    return {"detail": "Respuesta guardada"}


@router.post("/evaluations/{evaluation_id}/submit", response_model=AttemptResultOut)
async def submit_evaluation(
    evaluation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> AttemptResultOut:
    attempt = await service.finalize_attempt(db, redis, user, evaluation_id)
    await db.commit()
    return await _build_result(db, user, evaluation_id, attempt.id)


@router.get("/evaluations/{evaluation_id}/result", response_model=AttemptResultOut)
async def get_result(
    evaluation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AttemptResultOut:
    attempt, _, _ = await service.get_attempt_result(db, user, evaluation_id)
    return await _build_result(db, user, evaluation_id, attempt.id)


async def _build_result(
    db: AsyncSession, user: User, evaluation_id: uuid.UUID, attempt_id: uuid.UUID
) -> AttemptResultOut:
    attempt, answers, max_score = await service.get_attempt_result(db, user, evaluation_id)
    return AttemptResultOut(
        attempt_id=attempt.id,
        status=attempt.status,
        total_score=attempt.total_score,
        max_score=max_score,
        answers=[
            QuestionResultOut(
                evaluation_exercise_id=a.evaluation_exercise_id,
                score=a.score,
                correct=a.correct,
                needs_manual_review=a.needs_manual_review,
                manual_score=a.manual_score,
            )
            for a in answers
        ],
    )


@router.get("/evaluations/{evaluation_id}/ranking", response_model=list[RankingEntryOut])
async def get_ranking(
    evaluation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
) -> list[RankingEntryOut]:
    entries = await service.get_ranking(redis, evaluation_id)
    return [
        RankingEntryOut(student_id=student_id, total_score=score) for student_id, score in entries
    ]


@router.get("/evaluations/{evaluation_id}/answers", response_model=list[AnswerSummaryOut])
async def list_evaluation_answers(
    evaluation_id: uuid.UUID,
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
) -> list[AnswerSummaryOut]:
    pairs = await service.list_all_answers(db, user, evaluation_id)
    return [
        AnswerSummaryOut(
            answer_id=answer.id,
            evaluation_exercise_id=answer.evaluation_exercise_id,
            student_id=student_id,
            score=answer.score,
            correct=answer.correct,
            needs_manual_review=answer.needs_manual_review,
            manual_score=answer.manual_score,
            ai_suggested_score=answer.ai_suggested_score,
        )
        for answer, student_id in pairs
    ]


@router.get("/evaluations/{evaluation_id}/manual-review", response_model=list[ManualReviewItemOut])
async def list_manual_review(
    evaluation_id: uuid.UUID,
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
) -> list[ManualReviewItemOut]:
    queue = await service.list_manual_review_queue(db, user, evaluation_id)
    return [
        ManualReviewItemOut(
            answer_id=answer.id,
            attempt_id=attempt.id,
            student_id=attempt.student_id,
            evaluation_exercise_id=answer.evaluation_exercise_id,
            exercise_title=exercise.title,
            answer=answer.answer,
        )
        for answer, attempt, exercise in queue
    ]


@router.post("/evaluations/{evaluation_id}/manual-review/{answer_id}")
async def submit_manual_review(
    evaluation_id: uuid.UUID,
    answer_id: uuid.UUID,
    payload: ManualReviewSubmitRequest,
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    await service.submit_manual_review(db, user, evaluation_id, answer_id, payload.score)
    await db.commit()
    return {"detail": "Calificación registrada"}


@router.get("/practice", response_model=list[PracticeExerciseOut])
async def list_practice(
    group_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PracticeExerciseOut]:
    exercises = await service.list_practice_exercises(db, user, group_id)
    return [
        PracticeExerciseOut(
            id=exercise.id,
            language_id=exercise.language_id,
            type=exercise.type,
            title=exercise.title,
            content=service.sanitize_exercise_content(exercise),
        )
        for exercise in exercises
    ]


@router.post("/practice/{exercise_id}/submit", response_model=PracticeResultOut)
async def submit_practice(
    exercise_id: uuid.UUID,
    payload: PracticeSubmitRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PracticeResultOut:
    submission = await service.submit_practice(
        db, user, exercise_id, payload.group_id, payload.answer
    )
    await db.commit()
    return PracticeResultOut(
        score=submission.score,
        correct=submission.correct,
        needs_manual_review=submission.needs_manual_review,
    )
