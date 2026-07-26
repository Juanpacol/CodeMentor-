import re

import pytest
from jinja2 import TemplateNotFound

from logica.ai.harness.prompts import _TEMPLATES_DIR, ACTIVE_PROMPT_VERSIONS, render_prompt
from logica.ai.harness.router import TASK_TIERS


def test_progressive_hint_grounds_on_reference_context_when_present() -> None:
    rendered = render_prompt(
        "progressive_hint",
        language="PSeInt",
        topic_name="Ciclos",
        statement="¿Qué hace un ciclo Mientras?",
        attempt_number=1,
        student_answer="no sé",
        reference_context="[Fuente: Referencia PSeInt]\nEl ciclo Mientras...",
    )
    assert rendered.version == 1
    normalized = " ".join(rendered.text.split())
    assert "si no cubre la pregunta del estudiante, dilo explícitamente" in normalized
    assert "[Fuente: Referencia PSeInt]" in rendered.text
    assert "No hay material de referencia" not in rendered.text


def test_progressive_hint_falls_back_explicitly_when_context_empty() -> None:
    rendered = render_prompt(
        "progressive_hint",
        language="PSeInt",
        topic_name="Ciclos",
        statement="¿Qué hace un ciclo Mientras?",
        attempt_number=1,
        student_answer="no sé",
        reference_context="",
    )
    normalized = " ".join(rendered.text.split())
    assert "No hay material de referencia del curso disponible" in normalized
    assert "apóyate únicamente en tu conocimiento general de PSeInt" in normalized


def test_exercise_generation_grounds_on_reference_context_when_present() -> None:
    rendered = render_prompt(
        "exercise_generation",
        exercise_type="true_false",
        topic_name="Ciclos",
        language="PSeInt",
        level="basico",
        reference_context="[Fuente: Referencia PSeInt]\nEl ciclo Mientras...",
        similar_exercises="",
        schema_hint='{"title": "...", "content": {}}',
    )
    assert "no lo contradigas" in rendered.text
    assert "[Fuente: Referencia PSeInt]" in rendered.text
    assert "No hay material de referencia" not in rendered.text


def test_exercise_generation_falls_back_explicitly_when_context_empty() -> None:
    rendered = render_prompt(
        "exercise_generation",
        exercise_type="true_false",
        topic_name="Ciclos",
        language="PSeInt",
        level="basico",
        reference_context="",
        similar_exercises="",
        schema_hint='{"title": "...", "content": {}}',
    )
    assert "No hay material de referencia del curso para este tema" in rendered.text
    assert "terminología estándar de PSeInt/Python" in rendered.text


# --- Estructurales (ítem 15): protegen el esquema de versionado en sí mismo,
# no el contenido de una plantilla particular. ---


def test_cada_version_activa_tiene_archivo() -> None:
    for task, version in ACTIVE_PROMPT_VERSIONS.items():
        path = _TEMPLATES_DIR / f"{task}.v{version}.j2"
        assert path.exists(), f"falta el archivo de la versión activa: {path.name}"


def test_no_quedan_plantillas_sin_version() -> None:
    sin_version = [
        p.name for p in _TEMPLATES_DIR.glob("*.j2") if not re.search(r"\.v\d+\.j2$", p.name)
    ]
    assert sin_version == [], f"plantillas sin versionar: {sin_version}"


def test_toda_tarea_de_task_tiers_tiene_plantilla_activa() -> None:
    for task in TASK_TIERS:
        version = ACTIVE_PROMPT_VERSIONS.get(task, 1)
        path = _TEMPLATES_DIR / f"{task}.v{version}.j2"
        assert path.exists(), f"TASK_TIERS tiene '{task}' pero no existe {path.name}"


def test_version_inexistente_lanza_template_not_found() -> None:
    with pytest.raises(TemplateNotFound):
        render_prompt("progressive_hint", prompt_version=999, language="PSeInt")
