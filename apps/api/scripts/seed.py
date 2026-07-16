"""Seed de datos demo. Se completa incrementalmente a medida que existen los modelos
de dominio (Fase 1: institución/usuarios/grupos; Fase 2: temas/lenguajes; ...).
"""

import asyncio
from datetime import UTC, datetime

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

        await db.commit()

    logger.info("seed_done", demo_password=DEMO_PASSWORD)


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()
