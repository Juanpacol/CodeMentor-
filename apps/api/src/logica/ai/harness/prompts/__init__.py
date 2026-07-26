"""Prompt templates as code (§9.4): each task has its own versioned Jinja2
template file in this package, reviewed and committed like any other source
file — never built as an f-string scattered across callers.

Versionado (ítem 15): un prompt publicado NUNCA se edita in-situ. Un cambio
de contenido agrega `<tarea>.vN+1.j2` (el archivo anterior se queda tal cual
en el repo) y actualiza `ACTIVE_PROMPT_VERSIONS` acá abajo — así el texto de
la versión anterior sigue siendo ejecutable por las evals de regresión que
comparan ambas versiones lado a lado."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATES_DIR = Path(__file__).parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(disabled_extensions=(".txt", ".j2")),
    trim_blocks=True,
    lstrip_blocks=True,
)

# Versión activa por tarea. Ver el docstring del módulo: agregar una versión
# nueva es un archivo `<tarea>.vN+1.j2` + cambiar el número acá, nunca editar
# el .j2 publicado.
ACTIVE_PROMPT_VERSIONS: dict[str, int] = {
    "progressive_hint": 1,
    "pedagogical_feedback": 1,
    "summarize_group": 1,
    "exercise_generation": 1,
    "grading_suggestion": 1,
    "code_integrity": 1,
    "guide_generation": 1,
}
_DEFAULT_VERSION = 1


@dataclass(frozen=True)
class RenderedPrompt:
    text: str
    version: int


def active_version(task: str) -> int:
    return ACTIVE_PROMPT_VERSIONS.get(task, _DEFAULT_VERSION)


def render_prompt(
    task: str, *, prompt_version: int | None = None, **variables: Any
) -> RenderedPrompt:
    """`prompt_version=None` (el caso normal) usa la versión activa de la
    tarea; pasar un entero explícito permite a las evals de regresión pedir
    una versión específica para comparar contra la activa. El kwarg se llama
    `prompt_version`, no `version`, para no chocar con ninguna variable de
    plantilla real (`**variables` reenvía cualquier nombre tal cual a Jinja)."""
    version = prompt_version if prompt_version is not None else active_version(task)
    template = _env.get_template(f"{task}.v{version}.j2")
    return RenderedPrompt(text=template.render(**variables), version=version)
