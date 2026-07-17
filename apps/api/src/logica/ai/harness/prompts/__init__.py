"""Prompt templates as code (§9.4): each task has its own versioned Jinja2
template file in this package, reviewed and committed like any other source
file — never built as an f-string scattered across callers."""

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


def render_prompt(task: str, **variables: Any) -> str:
    template = _env.get_template(f"{task}.j2")
    return template.render(**variables)
