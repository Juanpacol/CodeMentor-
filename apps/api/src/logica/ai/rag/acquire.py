"""Adquisición de material de referencia para un tema, a costo $0 (Fase 17).

Vive dentro de `ai/rag/` y no como módulo propio porque su único consumidor es
`ingestion.py::ingest_document` y su producto es material RAG: separar esto en
un paquete nuevo sería la abstracción prematura que CLAUDE.md prohíbe.

La fuente principal es la action API de Wikipedia/Wikibooks en español, elegida
por tres razones concretas y no por popularidad: no pide API key (el requisito
de $0 es duro — las únicas claves del proyecto son GROQ y GEMINI), su licencia
CC BY-SA permite el uso educativo con atribución (por eso `RagDocument.source_url`),
y con `explaintext=1` devuelve **texto plano** con párrafos separados por `\\n\\n`,
que es exactamente lo que `chunking.py::chunk_text` espera. Ese último punto es
el que evita arrastrar una dependencia de parseo de HTML para el camino principal.

El camino secundario —URLs que pega el docente— sí necesita HTML, y ahí está el
riesgo real: fetchear una URL arbitraria desde el servidor es SSRF, y esta app es
multi-tenant. Todo lo que viene del usuario pasa por `validate_public_url` antes
de tocar la red, y cada salto de redirección se revalida (ver `_fetch_text`).
"""

import asyncio
import ipaddress
import re
import socket
from collections.abc import Sequence
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any
from urllib.parse import quote, urljoin, urlparse

import httpx
import structlog

from logica.config import get_settings
from logica.core.errors import ValidationDomainError

logger = structlog.get_logger()

# Corte de tamaño: media docena de artículos largos de Wikipedia caben de sobra,
# y un cuerpo mayor casi siempre es una descarga que no es texto.
_MAX_BYTES = 512_000
# Debajo de esto un extracto es una entradilla o una desambiguación, no material.
_MIN_USEFUL_CHARS = 400
_MAX_REDIRECTS = 3
_ALLOWED_CONTENT_TYPES = frozenset({"text/html", "text/plain", "text/markdown"})
# Cortesía con Wikimedia entre peticiones. No es un rate limit real: el volumen
# de una rúbrica (≈3 fuentes × 15 temas) está muy por debajo de sus umbrales.
_POLITENESS_DELAY_SECONDS = 0.3
# Wikimedia pide un User-Agent identificable; sin él responden 403.
_USER_AGENT = "CodeMentor/1.0 (plataforma educativa; material de referencia docente)"

_WIKI_SOURCES: tuple[tuple[str, str], ...] = (
    ("wikipedia", "es.wikipedia.org"),
    ("wikibooks", "es.wikibooks.org"),
)

_SKIP_TAGS = frozenset(
    {"script", "style", "nav", "footer", "header", "aside", "form", "noscript", "svg"}
)
_BLOCK_TAGS = frozenset(
    {"p", "div", "br", "li", "tr", "section", "article", "h1", "h2", "h3", "h4", "h5", "h6"}
)

_STOPWORDS = frozenset(
    {
        "para",
        "como",
        "este",
        "esta",
        "esto",
        "estos",
        "estas",
        "desde",
        "hasta",
        "sobre",
        "entre",
        "cuando",
        "donde",
        "pero",
        "porque",
        "todo",
        "toda",
        "todos",
        "todas",
    }
)


@dataclass(frozen=True)
class AcquiredSource:
    """Una fuente lista para ingerir. `text` ya viene en texto plano con los
    párrafos separados por `\\n\\n`, que es el contrato que `chunk_text` asume."""

    title: str
    url: str
    text: str
    origin: str  # "wikipedia" | "wikibooks" | "teacher_url"


async def _resolve_ips(host: str) -> list[str]:
    """Seam de monkeypatch para los tests, y `to_thread` porque `getaddrinfo`
    bloquea el event loop."""
    infos = await asyncio.to_thread(
        socket.getaddrinfo, host, 443, socket.AF_UNSPEC, socket.SOCK_STREAM
    )
    return [str(info[4][0]) for info in infos]


async def validate_public_url(raw: str) -> str:
    """Valida que una URL suministrada por el docente apunte a internet pública.

    Sin esto, un docente (o alguien con su sesión) podría hacer que el servidor
    descargue `http://169.254.169.254/...` —el endpoint de metadatos de casi
    cualquier nube— o un servicio interno del clúster, y el contenido terminaría
    ingerido en el RAG de su institución. Se rechazan **todas** las direcciones
    del host y no solo la primera: un host con varios registros A puede tener uno
    público y otro interno, y nada garantiza cuál elegirá el cliente HTTP.
    """
    candidate = raw.strip()
    parsed = urlparse(candidate)

    if parsed.scheme != "https":
        raise ValidationDomainError(f"Solo se admiten URLs https: {candidate}")
    host = parsed.hostname
    if not host:
        raise ValidationDomainError(f"La URL no tiene un host válido: {candidate}")
    if parsed.port is not None and parsed.port != 443:
        raise ValidationDomainError(f"Solo se admite el puerto 443: {candidate}")

    try:
        addresses = await _resolve_ips(host)
    except OSError as exc:
        raise ValidationDomainError(f"No se pudo resolver el host: {host}") from exc
    if not addresses:
        raise ValidationDomainError(f"No se pudo resolver el host: {host}")

    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError as exc:  # pragma: no cover — getaddrinfo no devuelve basura
            raise ValidationDomainError(f"Dirección no válida para {host}") from exc
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise ValidationDomainError(
                f"La URL apunta a una dirección de red interna y no se puede descargar: {host}"
            )

    return candidate


def _api_url(host: str, params: dict[str, str]) -> str:
    query = "&".join(f"{key}={quote(value, safe='')}" for key, value in params.items())
    return f"https://{host}/w/api.php?{query}"


async def _fetch_json(url: str) -> dict[str, Any]:
    """Descarga JSON de la action API de Wikimedia.

    Indirección a nivel de módulo a propósito: es el único punto que los tests
    parchean, igual que `ai/harness/router.py::_completion_fn` y
    `ai/rag/embedder.py::embed_texts`. Así el resto del pipeline (relevancia,
    ensamblado, ingesta) se ejercita de verdad sin red.

    No pasa por `validate_public_url` porque la URL no viene del usuario: se
    construye acá contra `_WIKI_SOURCES`, que es una constante del módulo.
    """
    timeout = get_settings().content_acquisition_timeout_seconds
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.get(url, headers={"User-Agent": _USER_AGENT})
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
    return payload


async def _fetch_text(url: str) -> tuple[str, str]:
    """Descarga una URL ya validada y devuelve `(content_type, cuerpo)`.

    `follow_redirects=False` no es un detalle de configuración: seguir las
    redirecciones automáticamente anularía por completo la validación previa —
    basta con que un host público responda 302 hacia 169.254.169.254. Cada salto
    vuelve a pasar por `validate_public_url`.

    Segundo seam de monkeypatch del módulo.
    """
    timeout = get_settings().content_acquisition_timeout_seconds
    current = url

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        for _ in range(_MAX_REDIRECTS + 1):
            async with client.stream(
                "GET", current, headers={"User-Agent": _USER_AGENT}
            ) as response:
                if response.is_redirect:
                    location = response.headers.get("location", "")
                    if not location:
                        raise ValidationDomainError("La URL respondió una redirección sin destino")
                    current = await validate_public_url(urljoin(current, location))
                    continue

                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                content_type = content_type.split(";")[0].strip().lower()
                if content_type not in _ALLOWED_CONTENT_TYPES:
                    raise ValidationDomainError(
                        f"Tipo de contenido no admitido: {content_type or 'desconocido'}"
                    )

                body = bytearray()
                async for piece in response.aiter_bytes():
                    body.extend(piece)
                    if len(body) >= _MAX_BYTES:
                        break
                return content_type, bytes(body[:_MAX_BYTES]).decode("utf-8", errors="replace")

    raise ValidationDomainError("La URL excedió el máximo de redirecciones permitidas")


class _TextExtractor(HTMLParser):
    """HTML → texto plano por párrafos, con la stdlib.

    No se agrega `trafilatura`/`selectolax`/`beautifulsoup4`: este es el camino
    secundario (URLs que pega el docente) y la fuente principal ya entrega texto
    plano. Una dependencia nueva no se paga sola por esto.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        elif tag in _BLOCK_TAGS:
            self._parts.append("\n\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        elif tag in _BLOCK_TAGS:
            self._parts.append("\n\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0 and data.strip():
            self._parts.append(data)

    def to_text(self) -> str:
        joined = "".join(self._parts)
        paragraphs = (" ".join(block.split()) for block in joined.split("\n\n"))
        return "\n\n".join(block for block in paragraphs if block)


def _html_to_paragraphs(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    return parser.to_text()


def _content_words(phrase: str) -> list[str]:
    words = re.findall(r"[a-záéíóúüñ]{4,}", phrase.lower())
    return [word for word in words if word not in _STOPWORDS]


def _is_relevant(topic_name: str, text: str) -> bool:
    """Filtro barato, sin llamada al modelo.

    La ingesta es $0 (embeddings locales), pero basura en el RAG degrada **todas**
    las guías que se generen después, no solo esta — y una llamada al LLM por
    fuente multiplicaría el consumo de la cuota de Groq justo en el job que ya la
    está exprimiendo. Se piden dos términos del tema y no uno: "arreglos" o
    "ciclos" aparecen sueltos en casi cualquier artículo de programación.
    """
    if len(text.strip()) < _MIN_USEFUL_CHARS:
        return False
    terms = _content_words(topic_name)
    if not terms:
        return True
    lowered = text.lower()
    matched = sum(1 for term in terms if term in lowered)
    return matched >= min(2, len(terms))


async def _search_wiki(host: str, topic_name: str, limit: int) -> list[int]:
    payload = await _fetch_json(
        _api_url(
            host,
            {
                "action": "query",
                "list": "search",
                "srsearch": topic_name,
                "srlimit": str(limit),
                "srnamespace": "0",
                "format": "json",
            },
        )
    )
    results = payload.get("query", {}).get("search", [])
    return [int(item["pageid"]) for item in results if "pageid" in item]


async def _extract_wiki(host: str, origin: str, page_ids: Sequence[int]) -> list[AcquiredSource]:
    if not page_ids:
        return []
    payload = await _fetch_json(
        _api_url(
            host,
            {
                "action": "query",
                "prop": "extracts",
                "explaintext": "1",
                "exsectionformat": "plain",
                "pageids": "|".join(str(page_id) for page_id in page_ids),
                "format": "json",
            },
        )
    )

    pages: dict[str, Any] = payload.get("query", {}).get("pages", {})
    sources: list[AcquiredSource] = []
    # `pages` es un dict indexado por pageid: se recorre en el orden que devolvió
    # la búsqueda para no perder su ranking de relevancia.
    for page_id in page_ids:
        page = pages.get(str(page_id))
        if not page:
            continue
        title = str(page.get("title", "")).strip()
        extract = str(page.get("extract", "")).strip()
        if not title or not extract:
            continue
        sources.append(
            AcquiredSource(
                title=title,
                url=f"https://{host}/?curid={page_id}",
                text=extract,
                origin=origin,
            )
        )
    return sources


async def _acquire_from_teacher_url(topic_name: str, url: str) -> AcquiredSource | None:
    validated = await validate_public_url(url)
    content_type, body = await _fetch_text(validated)
    text = _html_to_paragraphs(body) if content_type == "text/html" else body.strip()
    if not _is_relevant(topic_name, text):
        logger.info("acquired_source_discarded", url=validated, reason="irrelevante")
        return None
    parsed = urlparse(validated)
    return AcquiredSource(
        title=f"{topic_name} — {parsed.hostname or validated}",
        url=validated,
        text=text,
        origin="teacher_url",
    )


async def acquire_for_topic(
    topic_name: str,
    *,
    level: str,
    extra_urls: Sequence[str] = (),
    max_sources: int | None = None,
) -> list[AcquiredSource]:
    """Reúne material de referencia para un tema. Nunca lanza por un fallo de una
    fuente concreta: devuelve lo que sí consiguió.

    Esa tolerancia es deliberada y no pereza — `guide_writer` ya degrada bien
    cuando el RAG no devuelve nada, así que una lista vacía produce una guía algo
    más genérica, mientras que propagar la excepción tumbaría el tema entero de la
    rúbrica por un 503 de Wikipedia.

    Las URLs del docente van primero: son una señal explícita de intención y el
    material que él eligió debe entrar aunque el cupo se agote con Wikipedia.
    """
    settings = get_settings()
    if not settings.content_acquisition_enabled:
        return []

    limit = max_sources or settings.content_acquisition_max_sources_per_topic
    collected: list[AcquiredSource] = []

    for url in extra_urls:
        if len(collected) >= limit:
            break
        try:
            source = await _acquire_from_teacher_url(topic_name, url)
        except (ValidationDomainError, httpx.HTTPError, UnicodeError) as exc:
            logger.warning("acquire_teacher_url_failed", url=url, error=str(exc))
            continue
        if source is not None:
            collected.append(source)

    for origin, host in _WIKI_SOURCES:
        if len(collected) >= limit:
            break
        try:
            await asyncio.sleep(_POLITENESS_DELAY_SECONDS)
            page_ids = await _search_wiki(host, topic_name, limit)
            candidates = await _extract_wiki(host, origin, page_ids)
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            logger.warning("acquire_wiki_failed", host=host, topic=topic_name, error=str(exc))
            continue

        for candidate in candidates:
            if len(collected) >= limit:
                break
            if not _is_relevant(topic_name, candidate.text):
                logger.info("acquired_source_discarded", url=candidate.url, reason="irrelevante")
                continue
            collected.append(candidate)

    logger.info(
        "content_acquired",
        topic=topic_name,
        level=level,
        sources=len(collected),
        teacher_urls=len(extra_urls),
    )
    return collected
