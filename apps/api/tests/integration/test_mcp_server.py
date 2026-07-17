"""Fase 7: el servidor MCP reexpone las mismas skills/agentes vía tools y
resources — estos tests verifican que la autenticación por token de docente
se respeta (tokens inválidos o de estudiante rechazados) y que cada tool/
resource devuelve lo mismo que su contraparte HTTP ya probada en fases
anteriores."""

import json

import pytest
from mcp.server.fastmcp.exceptions import ToolError

import logica.mcp.server as mcp_server_module
from logica.ai.harness.router import CompletionResult
from logica.mcp.server import mcp
from logica.modules.users.models import Institution
from tests.integration.conftest import (
    create_group,
    create_language,
    create_topic,
    enable_topic,
    register_and_login,
)


@pytest.fixture(autouse=True)
def _reset_mcp_redis_singleton() -> None:
    """`mcp.server._redis` is a module-level singleton meant for a single
    long-lived process (the real MCP server) — it lazily binds to whichever
    event loop is running on first use. Each pytest-asyncio test gets its
    own fresh loop, so without resetting this between tests, any test after
    the first one to touch Redis fails with "Event loop is closed". The
    previous test's loop is already gone by the time this runs, so we just
    drop the reference rather than attempt a graceful `aclose()`."""
    mcp_server_module._redis = None


async def test_list_tools_and_resource_templates() -> None:
    tools = await mcp.list_tools()
    tool_names = {t.name for t in tools}
    assert tool_names == {
        "validate_pseint",
        "run_code",
        "generate_exercise_draft",
        "get_group_summary",
    }

    templates = await mcp.list_resource_templates()
    uri_templates = {t.uriTemplate for t in templates}
    assert uri_templates == {
        "curriculum://{access_token}/{group_id}",
        "stats://{access_token}/{group_id}",
    }


async def test_tool_rejects_invalid_token() -> None:
    with pytest.raises(ToolError):
        await mcp.call_tool(
            "validate_pseint", {"access_token": "not-a-real-token", "source": "Proceso\nFinProceso"}
        )


async def test_tool_rejects_student_token(client, institution: Institution) -> None:  # type: ignore[no-untyped-def]
    domain = institution.email_domains[0]
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    with pytest.raises(ToolError):
        await mcp.call_tool(
            "validate_pseint",
            {"access_token": student_access, "source": "Proceso\nFinProceso"},
        )


async def test_validate_pseint_tool(client, institution: Institution) -> None:  # type: ignore[no-untyped-def]
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")

    _, result = await mcp.call_tool(
        "validate_pseint",
        {"access_token": teacher_access, "source": "Proceso ejemplo\nFinProceso"},
    )
    assert isinstance(result, dict)
    assert result["valid"] is True

    _, bad_result = await mcp.call_tool(
        "validate_pseint",
        {"access_token": teacher_access, "source": "Proceso ejemplo sin fin"},
    )
    assert bad_result["valid"] is False


@pytest.mark.sandbox
async def test_run_code_tool(client, institution: Institution) -> None:  # type: ignore[no-untyped-def]
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")

    _, result = await mcp.call_tool(
        "run_code",
        {
            "access_token": teacher_access,
            "language": "python",
            "version": "3.10.0",
            "source": "print('hola mundo')",
        },
    )
    assert isinstance(result, dict)
    assert result["stdout"].strip() == "hola mundo"
    assert result["exit_code"] == 0


async def test_generate_exercise_draft_tool(
    client,
    institution: Institution,
    monkeypatch: pytest.MonkeyPatch,  # type: ignore[no-untyped-def]
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")

    language_id = await create_language(client, teacher_access)
    topic_id = await create_topic(client, teacher_access, language_id)
    group = await create_group(client, teacher_access)

    async def fake(task: str, messages: list[dict[str, str]]) -> CompletionResult:
        return CompletionResult(
            text='{"title": "Verdadero o falso vía MCP", '
            '"content": {"statement": "Un ciclo Mientras evalúa antes", "answer": true}}',
            model="groq/fake",
            prompt_tokens=10,
            completion_tokens=10,
        )

    monkeypatch.setattr("logica.ai.harness.harness.router_complete", fake)

    _, result = await mcp.call_tool(
        "generate_exercise_draft",
        {
            "access_token": teacher_access,
            "group_id": group["id"],
            "topic_id": topic_id,
            "exercise_type": "true_false",
        },
    )
    assert isinstance(result, dict)
    assert result["status"] == "draft"
    assert result["title"] == "Verdadero o falso vía MCP"


async def test_get_group_summary_tool(
    client,
    institution: Institution,
    monkeypatch: pytest.MonkeyPatch,  # type: ignore[no-untyped-def]
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    group = await create_group(client, teacher_access)

    async def fake(task: str, messages: list[dict[str, str]]) -> CompletionResult:
        return CompletionResult(
            text="El grupo va bien, sin temas de rezago.",
            model="groq/fake",
            prompt_tokens=5,
            completion_tokens=5,
        )

    monkeypatch.setattr("logica.ai.harness.harness.router_complete", fake)

    _, result = await mcp.call_tool(
        "get_group_summary", {"access_token": teacher_access, "group_id": group["id"]}
    )
    assert isinstance(result, dict)
    assert result["summary"] == "El grupo va bien, sin temas de rezago."


async def test_curriculum_resource(client, institution: Institution) -> None:  # type: ignore[no-untyped-def]
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")

    language_id = await create_language(client, teacher_access)
    topic_id = await create_topic(client, teacher_access, language_id, name="Ciclos")
    group = await create_group(client, teacher_access)
    await enable_topic(client, teacher_access, group["id"], topic_id)

    contents = await mcp.read_resource(f"curriculum://{teacher_access}/{group['id']}")
    [content] = contents

    topics = json.loads(content.content)  # type: ignore[arg-type]
    assert any(t["topic"] == "Ciclos" and t["state"] == "enabled" for t in topics)


async def test_stats_resource(client, institution: Institution) -> None:  # type: ignore[no-untyped-def]
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    group = await create_group(client, teacher_access)

    contents = await mcp.read_resource(f"stats://{teacher_access}/{group['id']}")
    [content] = contents

    stats = json.loads(content.content)  # type: ignore[arg-type]
    assert stats["total_submissions"] == 0
    assert stats["accuracy_overall"] is None
