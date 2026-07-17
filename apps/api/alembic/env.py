import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import all module models here so Base.metadata is fully populated for autogenerate.
from logica.ai.agents.models import AgentConfig, CodeIntegrityAlert, TutorMessage  # noqa: F401
from logica.ai.models import AiInteraction  # noqa: F401
from logica.ai.rag.models import RagChunk, RagDocument  # noqa: F401
from logica.config import get_settings
from logica.core.audit import AuditLog  # noqa: F401
from logica.db import Base
from logica.modules.content.models import Language, Topic, TopicGroupState  # noqa: F401
from logica.modules.evaluations.models import (  # noqa: F401
    Evaluation,
    EvaluationAnswer,
    EvaluationAttempt,
    EvaluationExercise,
    PracticeSubmission,
)
from logica.modules.exercises.models import Exercise, TopicExercise  # noqa: F401
from logica.modules.groups.models import Group, GroupMembership  # noqa: F401
from logica.modules.users.models import Institution, PasswordResetToken, User  # noqa: F401

# (populated incrementally as each domain module is implemented — see Fase 7+)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

config.set_main_option("sqlalchemy.url", get_settings().database_url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
