"""Seed de datos demo. Se completa incrementalmente a medida que existen los modelos
de dominio (Fase 1: institución/usuarios/grupos; Fase 2: temas/lenguajes; ...).
"""

import asyncio
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select

from logica.core.security import hash_password
from logica.db import get_session_factory
from logica.modules.content.models import (
    Language,
    Topic,
    TopicGroupState,
    TopicGroupStateValue,
    TopicLevel,
)
from logica.modules.evaluations import service as evaluations_service
from logica.modules.evaluations.models import Evaluation, EvaluationMode
from logica.modules.exercises import service as exercises_service
from logica.modules.exercises.models import Exercise, ExerciseStatus, ExerciseType
from logica.modules.groups.models import Group, GroupMembership
from logica.modules.users.models import Institution, Role, User

logger = structlog.get_logger()

DEMO_DOMAIN = "inem.edu.co"
DEMO_PASSWORD = "Logica2026!"


async def seed() -> None:
    logger.info("seed_start")
    session_factory = get_session_factory()

    async with session_factory() as db:
        result = await db.execute(
            select(Institution).where(Institution.email_domains.any(DEMO_DOMAIN))  # type: ignore[arg-type]
        )
        institution = result.scalar_one_or_none()
        if institution is None:
            institution = Institution(
                name="INEM José Félix de Restrepo",
                email_domains=[DEMO_DOMAIN],
            )
            db.add(institution)
            await db.flush()
            logger.info("institution_created", id=str(institution.id))

        async def get_or_create_user(
            email: str, full_name: str, role: Role, student_code: str | None = None
        ) -> User:
            result = await db.execute(
                select(User).where(User.institution_id == institution.id, User.email == email)
            )
            user = result.scalar_one_or_none()
            if user is None:
                user = User(
                    institution_id=institution.id,
                    email=email,
                    full_name=full_name,
                    student_code=student_code,
                    hashed_password=hash_password(DEMO_PASSWORD),
                    role=role,
                )
                db.add(user)
                await db.flush()
                logger.info("user_created", email=email, role=role.value)
            return user

        teacher = await get_or_create_user(
            f"docente.logica@{DEMO_DOMAIN}", "Docente de Lógica", Role.teacher
        )
        student_a = await get_or_create_user(
            f"estudiante.uno@{DEMO_DOMAIN}", "Estudiante Uno", Role.student, student_code="E001"
        )
        student_b = await get_or_create_user(
            f"estudiante.dos@{DEMO_DOMAIN}", "Estudiante Dos", Role.student, student_code="E002"
        )

        result = await db.execute(
            select(Group).where(
                Group.institution_id == institution.id, Group.teacher_id == teacher.id
            )
        )
        group = result.scalars().first()
        if group is None:
            group = Group(
                institution_id=institution.id,
                teacher_id=teacher.id,
                name="Grupo piloto 10-1",
                grade_or_shift="10° - Jornada mañana",
                invite_code="PILOTO1",
            )
            db.add(group)
            await db.flush()
            logger.info("group_created", id=str(group.id))

        for student in (student_a, student_b):
            result = await db.execute(
                select(GroupMembership).where(
                    GroupMembership.group_id == group.id, GroupMembership.student_id == student.id
                )
            )
            if result.scalar_one_or_none() is None:
                db.add(GroupMembership(group_id=group.id, student_id=student.id))

        result = await db.execute(
            select(Language).where(
                Language.institution_id == institution.id, Language.slug == "pseint"
            )
        )
        pseint = result.scalar_one_or_none()
        if pseint is None:
            pseint = Language(
                institution_id=institution.id, name="PSeInt", slug="pseint", syntax_mode="pseint"
            )
            db.add(pseint)
            await db.flush()
            logger.info("language_created", slug="pseint")

        result = await db.execute(
            select(Language).where(
                Language.institution_id == institution.id, Language.slug == "python"
            )
        )
        python = result.scalar_one_or_none()
        if python is None:
            python = Language(
                institution_id=institution.id, name="Python", slug="python", syntax_mode="python"
            )
            db.add(python)
            await db.flush()
            logger.info("language_created", slug="python")

        result = await db.execute(
            select(Topic).where(
                Topic.institution_id == institution.id, Topic.language_id == pseint.id
            )
        )
        topic = result.scalars().first()
        if topic is None:
            topic = Topic(
                institution_id=institution.id,
                language_id=pseint.id,
                created_by_id=teacher.id,
                name="Estructuras condicionales (Si/Sino)",
                level=TopicLevel.basico,
                order_index=1,
            )
            db.add(topic)
            await db.flush()
            logger.info("topic_created", id=str(topic.id))

        result = await db.execute(
            select(TopicGroupState).where(
                TopicGroupState.topic_id == topic.id, TopicGroupState.group_id == group.id
            )
        )
        state = result.scalar_one_or_none()
        if state is None:
            db.add(
                TopicGroupState(
                    topic_id=topic.id,
                    group_id=group.id,
                    state=TopicGroupStateValue.enabled,
                    enabled_at=datetime.now(UTC),
                )
            )
            logger.info("topic_enabled_for_group", topic_id=str(topic.id), group_id=str(group.id))

        async def get_or_create_exercise(
            language_id: Any, title: str, exercise_type: ExerciseType, content: dict[str, Any]
        ) -> Exercise:
            result = await db.execute(
                select(Exercise).where(
                    Exercise.institution_id == institution.id, Exercise.title == title
                )
            )
            exercise = result.scalar_one_or_none()
            if exercise is None:
                exercise = await exercises_service.create_exercise(
                    db,
                    teacher,
                    language_id,
                    title,
                    exercise_type,
                    content,
                    ExerciseStatus.published,
                )
                await exercises_service.attach_exercise_to_topic(db, teacher, topic.id, exercise.id)
                logger.info("exercise_created", title=title, type=exercise_type.value)
            return exercise

        # Un ejercicio de cada uno de los 8 tipos (RF-10 + live_code) para que
        # el banco de ejercicios y la práctica libre no aparezcan vacíos en la
        # demo — el contenido usa los mismos nombres de campo que leen tanto
        # los graders (grading/plugins.py) como los renderers del frontend.
        ex_true_false = await get_or_create_exercise(
            pseint.id,
            "V o F: Repetir...Hasta Que valida al final",
            ExerciseType.true_false,
            {
                "statement": (
                    "En PSeInt, la estructura Repetir...Hasta Que evalúa la condición "
                    "después de ejecutar el cuerpo del ciclo al menos una vez."
                ),
                "answer": True,
            },
        )
        ex_multiple_choice = await get_or_create_exercise(
            pseint.id,
            "Selección: salida de un Si/Sino",
            ExerciseType.multiple_choice,
            {
                "statement": (
                    "Definir x Como Entero; x <- 5; Si x > 3 Entonces Escribir 'A'; "
                    "Sino Escribir 'B'; FinSi — ¿qué se escribe?"
                ),
                "options": ["A", "B", "Error de sintaxis", "No imprime nada"],
                "answer_index": 0,
            },
        )
        ex_fill_code = await get_or_create_exercise(
            pseint.id,
            "Completar: mayor de dos números",
            ExerciseType.fill_code,
            {
                "statement": "Completa el pseudocódigo para leer dos números y escribir el mayor.",
                "code_template": (
                    "Proceso Mayor\n"
                    "    Definir a, b Como Entero\n"
                    "    Leer a\n"
                    "    Leer ___\n"
                    "    Si a > b Entonces\n"
                    "        Escribir ___\n"
                    "    Sino\n"
                    "        Escribir b\n"
                    "    FinSi\n"
                    "FinProceso"
                ),
                "blanks": ["b", "a"],
            },
        )
        await get_or_create_exercise(
            pseint.id,
            "Encontrar el error: saludo",
            ExerciseType.find_error,
            {
                "statement": "Encuentra la línea con el error de sintaxis.",
                "code": (
                    "Proceso Saludo\n"
                    "    Definir nombre Como Cadena\n"
                    "    Leer nombre\n"
                    "    Escribir 'Hola, ' nombre\n"
                    "FinAlgoritmo"
                ),
                "error_line": 5,
                "error_kind": "sintaxis",
            },
        )
        await get_or_create_exercise(
            pseint.id,
            "Trazar: contador en un ciclo Para",
            ExerciseType.trace_variables,
            {
                "statement": "Traza el valor de la variable contador en cada iteración del ciclo.",
                "code": (
                    "Definir contador Como Entero\n"
                    "contador <- 0\n"
                    "Para i <- 1 Hasta 3 Con Paso 1\n"
                    "    contador <- contador + 2\n"
                    "FinPara"
                ),
                "expected_trace": [{"contador": 2}, {"contador": 4}, {"contador": 6}],
            },
        )
        await get_or_create_exercise(
            pseint.id,
            "Ordenar: cálculo de un promedio",
            ExerciseType.order_lines,
            {
                "statement": (
                    "Ordena las líneas para que el algoritmo calcule correctamente "
                    "el promedio de dos notas."
                ),
                "lines": [
                    "Escribir promedio",
                    "promedio <- (n1 + n2) / 2",
                    "Leer n1, n2",
                    "Definir n1, n2, promedio Como Real",
                ],
                "correct_order": [3, 2, 1, 0],
            },
        )
        await get_or_create_exercise(
            pseint.id,
            "Argumenta: Mientras vs. Repetir",
            ExerciseType.argued_response,
            {
                "prompt": (
                    "Explica con tus palabras la diferencia entre un ciclo Mientras y un "
                    "ciclo Repetir en PSeInt. ¿En qué situación usarías cada uno?"
                ),
            },
        )
        await get_or_create_exercise(
            python.id,
            "Reto en vivo: suma de pares",
            ExerciseType.live_code,
            {
                "statement": (
                    "Lee una línea con números separados por espacios y escribe la suma "
                    "de los que son pares."
                ),
                "starter_code": "numeros = list(map(int, input().split()))\n# tu código aquí\n",
                "language": "python",
                "version": "3.10.0",
                "test_cases": [
                    {"stdin": "1 2 3 4 5 6", "expected_stdout": "12"},
                    {"stdin": "10 15 20", "expected_stdout": "30"},
                ],
            },
        )

        result = await db.execute(
            select(Evaluation).where(
                Evaluation.institution_id == institution.id,
                Evaluation.title == "Quiz piloto: Si/Sino",
            )
        )
        if result.scalar_one_or_none() is None:
            await evaluations_service.create_evaluation(
                db,
                teacher,
                group.id,
                "Quiz piloto: Si/Sino",
                EvaluationMode.fixed,
                topic.id,
                20,
                True,
                [ex_true_false.id, ex_multiple_choice.id, ex_fill_code.id],
            )
            logger.info("evaluation_created", title="Quiz piloto: Si/Sino")

        await db.commit()

    logger.info("seed_done", demo_password=DEMO_PASSWORD)


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()
