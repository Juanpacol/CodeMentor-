"""Tests de `POST /rubric-runs/extract-topics`: un paso de *preview* puro que
lee un PDF/DOCX de rúbrica institucional y propone temas, sin crear ningún
`RubricRun` ni tocar la DB de negocio del docente."""

import io

import pytest
from docx import Document
from httpx import AsyncClient

from logica.ai.harness.router import CompletionResult
from logica.modules.users.models import Institution
from tests.integration.conftest import auth_headers, register_and_login

_EXTRACTION_JSON = (
    '{"items": [{"topic_name": "Estructuras condicionales", "level": "basico", '
    '"order_index": 0}, {"topic_name": "Ciclos anidados", "level": "intermedio", '
    '"order_index": 1}]}'
)


def _stub_model(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake(task: str, messages: list[dict[str, str]]) -> CompletionResult:
        return CompletionResult(
            text=_EXTRACTION_JSON, model="groq/fake", prompt_tokens=10, completion_tokens=20
        )

    monkeypatch.setattr("logica.ai.harness.harness.router_complete", fake)


def _build_docx_bytes(paragraphs: list[str]) -> bytes:
    document = Document()
    for text in paragraphs:
        document.add_paragraph(text)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


async def test_extrae_temas_de_un_docx(
    client: AsyncClient, institution: Institution, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_model(monkeypatch)
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")

    raw = _build_docx_bytes(["Unidad 1", "Estructuras condicionales", "Ciclos anidados"])
    resp = await client.post(
        "/rubric-runs/extract-topics",
        files={
            "file": (
                "rubrica.docx",
                raw,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        headers=auth_headers(teacher_access),
    )

    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    assert [item["topic_name"] for item in items] == [
        "Estructuras condicionales",
        "Ciclos anidados",
    ]
    assert items[1]["level"] == "intermedio"


async def test_rechaza_extension_no_soportada(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")

    resp = await client.post(
        "/rubric-runs/extract-topics",
        files={"file": ("rubrica.txt", b"Estructuras condicionales", "text/plain")},
        headers=auth_headers(teacher_access),
    )

    assert resp.status_code == 422, resp.text


async def test_rechaza_docx_sin_texto_legible(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")

    raw = _build_docx_bytes([])
    resp = await client.post(
        "/rubric-runs/extract-topics",
        files={
            "file": (
                "vacio.docx",
                raw,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        headers=auth_headers(teacher_access),
    )

    assert resp.status_code == 422, resp.text


async def test_estudiante_no_puede_extraer_temas(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    student_access, _ = await register_and_login(
        client, email=f"est@{domain}", role="student", student_code="E001"
    )

    raw = _build_docx_bytes(["Estructuras condicionales"])
    resp = await client.post(
        "/rubric-runs/extract-topics",
        files={
            "file": (
                "rubrica.docx",
                raw,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        headers=auth_headers(student_access),
    )

    assert resp.status_code == 403, resp.text
