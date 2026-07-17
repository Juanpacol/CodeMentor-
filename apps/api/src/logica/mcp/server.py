"""Servidor MCP (§9.2, §9.3): expone las mismas skills que usan el motor de
calificación y los agentes — una sola implementación, ahora un tercer
consumidor (Claude Desktop/Code u otro cliente MCP), sin duplicar lógica.

Cada tool/resource recibe `access_token` como primer argumento y lo
resuelve contra un docente real (`mcp.auth.resolve_teacher`) — el servidor
MCP es una superficie para docentes, nunca para estudiantes (§9.2).

Se ejecuta como un proceso separado del API principal (como el worker de
arq): `uv run python -m logica.mcp.server` para el transporte stdio que
usan Claude Desktop/Code."""

import sys
import uuid
from typing import Any

from mcp.server.fastmcp import FastMCP
from redis.asyncio import Redis

from logica.ai.agents.exercise_generator import (
    generate_exercise_draft as generate_exercise_draft_service,
)
from logica.ai.agents.learning_analytics import get_group_stats, summarize_group
from logica.config import get_settings
from logica.db import get_session_factory
from logica.mcp.auth import resolve_teacher
from logica.modules.content.service import get_curriculum_for_group
from logica.modules.exercises.models import ExerciseType
from logica.modules.sandbox.piston_client import run_code as sandbox_run_code
from logica.modules.sandbox.pseint.interpreter import validate_pseint as pseint_validate

mcp = FastMCP(
    name="logica-mcp",
    instructions=(
        "Servidor MCP de la plataforma CodeMentor. Todas las herramientas requieren "
        "el access_token de un docente autenticado (mismo token que /auth/login)."
    ),
)

_redis: Redis | None = None


def _get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    return _redis


@mcp.tool()
async def validate_pseint(access_token: str, source: str) -> dict[str, Any]:
    """Valida la sintaxis de un bloque de pseudocódigo PSeInt y devuelve si
    es válido y en qué línea está el error, si existe."""
    session_factory = get_session_factory()
    async with session_factory() as db:
        await resolve_teacher(db, access_token)

    result = pseint_validate(source)
    return {
        "valid": result.valid,
        "error_line": result.error_line,
        "error_message": result.error_message,
    }


@mcp.tool()
async def run_code(
    access_token: str, language: str, version: str, source: str, stdin: str = ""
) -> dict[str, Any]:
    """Ejecuta código en el sandbox aislado (Piston) y devuelve stdout/stderr."""
    session_factory = get_session_factory()
    async with session_factory() as db:
        await resolve_teacher(db, access_token)

    result = await sandbox_run_code(language, version, source, stdin=stdin)
    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.exit_code,
        "timed_out": result.timed_out,
    }


@mcp.tool(name="generate_exercise_draft")
async def generate_exercise_draft_tool(
    access_token: str, group_id: str, topic_id: str, exercise_type: str
) -> dict[str, Any]:
    """Genera un ejercicio nuevo en estado "borrador" (RF-32) para que el
    docente lo revise antes de publicarlo — nunca visible a estudiantes
    hasta su aprobación explícita."""
    session_factory = get_session_factory()
    async with session_factory() as db:
        teacher = await resolve_teacher(db, access_token)
        exercise = await generate_exercise_draft_service(
            db,
            _get_redis(),
            teacher,
            group_id=uuid.UUID(group_id),
            topic_id=uuid.UUID(topic_id),
            exercise_type=ExerciseType(exercise_type),
        )
        await db.commit()
        return {
            "id": str(exercise.id),
            "title": exercise.title,
            "type": exercise.type.value,
            "status": exercise.status.value,
            "content": exercise.content,
        }


@mcp.tool()
async def get_group_summary(access_token: str, group_id: str) -> dict[str, Any]:
    """Resumen en lenguaje natural del avance del grupo (§9.2, agente de
    analítica de aprendizaje) — informativo, nunca actúa sobre calificaciones
    o contenido por sí solo."""
    session_factory = get_session_factory()
    async with session_factory() as db:
        teacher = await resolve_teacher(db, access_token)
        summary = await summarize_group(db, _get_redis(), teacher, group_id=uuid.UUID(group_id))
        await db.commit()
        return {"summary": summary}


@mcp.resource("curriculum://{access_token}/{group_id}")
async def curriculum_resource(access_token: str, group_id: str) -> list[dict[str, Any]]:
    """Línea de tiempo curricular del grupo (RF-23): cada tema con su estado
    (bloqueado/habilitado/evaluado) y fecha de habilitación."""
    session_factory = get_session_factory()
    async with session_factory() as db:
        teacher = await resolve_teacher(db, access_token)
        curriculum = await get_curriculum_for_group(db, _get_redis(), teacher, uuid.UUID(group_id))
        return [
            {
                "topic": item.topic.name,
                "level": item.topic.level.value,
                "state": item.state.value,
                "enabled_at": item.enabled_at.isoformat() if item.enabled_at else None,
            }
            for item in curriculum
        ]


@mcp.resource("stats://{access_token}/{group_id}")
async def stats_resource(access_token: str, group_id: str) -> dict[str, Any]:
    """Estadísticas agregadas de práctica del grupo (sin resumen de IA — ver
    la tool `get_group_summary` para la versión en lenguaje natural)."""
    session_factory = get_session_factory()
    async with session_factory() as db:
        teacher = await resolve_teacher(db, access_token)
        return await get_group_stats(db, teacher, group_id=uuid.UUID(group_id))


def main() -> None:
    """`uv run python -m logica.mcp.server` → stdio (Claude Desktop/Code).
    `uv run python -m logica.mcp.server --http` → streamable-http (§9.2
    "servidor MCP (stdio + HTTP)"), useful for clients that speak MCP over
    a network connection instead of a local subprocess."""
    if "--http" in sys.argv:
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
