"""Guarda el invariante que declara el docstring de `AgentName`: cada agente con
interruptor por grupo es una tarea real del harness (los agentes son un
subconjunto de las tareas — ver `test_harness_task_registries_agree_with_each_other`).

Existe porque el invariante estuvo roto sin que nada lo notara — la Fase 15 dejó
`curriculum_planner = "curriculum_planning"` en el enum sin plantilla `.j2` y sin
entrada en `TASK_TIERS`. El síntoma visible era un agente que el docente veía
como activo en `GET /ai/groups/{id}/agents` y podía apagar, pero que no existía;
el síntoma latente, un `TemplateNotFound` en runtime si algo lo hubiera invocado.
"""

from logica.ai.agents.models import AgentName
from logica.ai.harness.prompts import _TEMPLATES_DIR, ACTIVE_PROMPT_VERSIONS, active_version
from logica.ai.harness.router import TASK_TIERS


def test_every_agent_has_a_model_tier() -> None:
    """Sin entrada en `TASK_TIERS`, `_tier_for_task` cae al default "cheap" en
    silencio — un agente de generación quedaría corriendo en el modelo pequeño
    sin que nadie lo pidiera."""
    missing = [a.name for a in AgentName if a.value not in TASK_TIERS]
    assert not missing, f"agentes sin tier en TASK_TIERS: {missing}"


def test_every_agent_has_an_active_prompt_version() -> None:
    missing = [a.name for a in AgentName if a.value not in ACTIVE_PROMPT_VERSIONS]
    assert not missing, f"agentes sin versión activa en ACTIVE_PROMPT_VERSIONS: {missing}"


def test_every_active_prompt_version_has_its_template_file() -> None:
    """La verificación que de verdad atrapa el fallo en runtime: `render_prompt`
    construye el nombre del archivo como `<tarea>.v<N>.j2`, así que una versión
    activa sin su archivo es un `TemplateNotFound` en la primera petición."""
    missing = [
        f"{agent.value}.v{active_version(agent.value)}.j2"
        for agent in AgentName
        if not (_TEMPLATES_DIR / f"{agent.value}.v{active_version(agent.value)}.j2").exists()
    ]
    assert not missing, f"plantillas de prompt inexistentes: {missing}"


def test_harness_task_registries_agree_with_each_other() -> None:
    """Los dos registros de tareas del harness (`TASK_TIERS` y
    `ACTIVE_PROMPT_VERSIONS`) describen el mismo conjunto, así que divergen solo
    si alguien agregó o quitó una tarea a medias.

    Nótese que NO se comparan contra `AgentName`: los agentes son un subconjunto
    de las tareas. `pedagogical_feedback` es una *skill*
    (`ai/skills/pedagogical_feedback.py`) — pasa por el harness pero no tiene
    interruptor por grupo, porque no es algo que el docente prenda y apague. Exigir
    igualdad acá obligaría a inventarle un agente que no existe."""
    assert set(TASK_TIERS) == set(ACTIVE_PROMPT_VERSIONS), (
        f"registros de tareas divergentes: solo en TASK_TIERS "
        f"{set(TASK_TIERS) - set(ACTIVE_PROMPT_VERSIONS)}, solo en "
        f"ACTIVE_PROMPT_VERSIONS {set(ACTIVE_PROMPT_VERSIONS) - set(TASK_TIERS)}"
    )


def test_every_harness_task_has_its_template_file() -> None:
    """Igual que la verificación por agente, pero sobre TODAS las tareas — incluye
    las skills, que también renderizan prompt y romperían igual en runtime."""
    missing = [
        f"{task}.v{active_version(task)}.j2"
        for task in TASK_TIERS
        if not (_TEMPLATES_DIR / f"{task}.v{active_version(task)}.j2").exists()
    ]
    assert not missing, f"plantillas de prompt inexistentes: {missing}"
