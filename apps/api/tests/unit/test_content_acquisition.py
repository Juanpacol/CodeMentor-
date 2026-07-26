"""Fase 17: la adquisición de material a $0.

Lo que se protege acá es sobre todo `validate_public_url`. Fetchear una URL que
escribe un usuario es SSRF de manual, y esta app es multi-tenant: si la
validación se relaja en un refactor, el síntoma no es un test rojo sino que el
servidor descarga el endpoint de metadatos de la nube y lo ingiere al RAG de una
institución. Por eso cada familia de direcciones internas tiene su caso.

Ninguna prueba toca la red: `_resolve_ips`, `_fetch_json` y `_fetch_text` son las
indirecciones a nivel de módulo que existen justo para esto (mismo idioma que
`ai/harness/router.py::_completion_fn`).
"""

from typing import Any

import pytest

from logica.ai.rag import acquire
from logica.core.errors import ValidationDomainError

_ARTICLE = (
    "Una estructura condicional permite que un programa ejecute instrucciones "
    "distintas según se cumpla o no una condición lógica dada. Es una de las tres "
    "estructuras de control básicas junto con la secuencia y la repetición.\n\n"
    "En pseudocódigo se escribe con Si-Entonces-SiNo-FinSi, y la condición debe "
    "evaluarse siempre a verdadero o falso. Las estructuras condicionales pueden "
    "anidarse unas dentro de otras para representar decisiones compuestas, aunque "
    "un anidamiento profundo suele indicar que conviene reescribir la lógica.\n\n"
    "La mayoría de lenguajes ofrece además una forma de selección múltiple, útil "
    "cuando se compara una misma variable contra muchos valores posibles."
)


def _stub_resolve(monkeypatch: pytest.MonkeyPatch, addresses: list[str]) -> None:
    async def fake(host: str) -> list[str]:
        return addresses

    monkeypatch.setattr(acquire, "_resolve_ips", fake)


class TestValidatePublicUrl:
    async def test_acepta_https_publico(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stub_resolve(monkeypatch, ["93.184.216.34"])
        assert await acquire.validate_public_url("  https://ejemplo.org/tema  ") == (
            "https://ejemplo.org/tema"
        )

    @pytest.mark.parametrize(
        "url",
        [
            "http://ejemplo.org/tema",  # sin TLS
            "file:///etc/passwd",
            "gopher://ejemplo.org/",
            "https://",  # sin host
        ],
    )
    async def test_rechaza_esquemas_y_urls_invalidas(
        self, monkeypatch: pytest.MonkeyPatch, url: str
    ) -> None:
        _stub_resolve(monkeypatch, ["93.184.216.34"])
        with pytest.raises(ValidationDomainError):
            await acquire.validate_public_url(url)

    async def test_rechaza_puerto_distinto_de_443(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Un puerto arbitrario es la vía directa a un servicio interno que
        # escucha en el mismo host público.
        _stub_resolve(monkeypatch, ["93.184.216.34"])
        with pytest.raises(ValidationDomainError):
            await acquire.validate_public_url("https://ejemplo.org:8080/")

    @pytest.mark.parametrize(
        ("address", "familia"),
        [
            ("127.0.0.1", "loopback"),
            ("10.0.0.5", "privada clase A"),
            ("172.16.3.9", "privada clase B"),
            ("192.168.1.10", "privada clase C"),
            ("169.254.169.254", "metadatos de la nube"),
            ("0.0.0.0", "no especificada"),  # noqa: S104 — es el dato bajo prueba, no un bind
            ("224.0.0.1", "multicast"),
            ("::1", "loopback IPv6"),
            ("fd00::1", "privada IPv6"),
        ],
    )
    async def test_rechaza_direcciones_internas(
        self, monkeypatch: pytest.MonkeyPatch, address: str, familia: str
    ) -> None:
        _stub_resolve(monkeypatch, [address])
        with pytest.raises(ValidationDomainError, match="red interna"):
            await acquire.validate_public_url("https://interno.ejemplo.org/")

    async def test_rechaza_si_cualquiera_de_las_ips_es_interna(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Un host con varios registros A puede tener uno público y uno interno, y
        # nada garantiza cuál elegirá el cliente HTTP: basta uno malo para negar.
        _stub_resolve(monkeypatch, ["93.184.216.34", "10.1.2.3"])
        with pytest.raises(ValidationDomainError, match="red interna"):
            await acquire.validate_public_url("https://mixto.ejemplo.org/")

    async def test_host_que_no_resuelve(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def fake(host: str) -> list[str]:
            raise OSError("nombre no resuelto")

        monkeypatch.setattr(acquire, "_resolve_ips", fake)
        with pytest.raises(ValidationDomainError, match="resolver"):
            await acquire.validate_public_url("https://inexistente.ejemplo.org/")


class TestExtraccionDeTexto:
    def test_descarta_script_style_y_navegacion(self) -> None:
        html = (
            "<html><head><style>p{color:red}</style></head><body>"
            "<nav>Inicio Contacto</nav>"
            "<p>Primer párrafo del artículo.</p>"
            "<script>alert('x')</script>"
            "<p>Segundo párrafo del artículo.</p>"
            "<footer>Pie de página</footer></body></html>"
        )
        texto = acquire._html_to_paragraphs(html)
        assert texto == "Primer párrafo del artículo.\n\nSegundo párrafo del artículo."

    def test_separa_bloques_con_doble_salto(self) -> None:
        # El contrato con `chunking.chunk_text`, que parte exactamente en "\n\n".
        texto = acquire._html_to_paragraphs("<div>Uno</div><li>Dos</li><h2>Tres</h2>")
        assert texto.split("\n\n") == ["Uno", "Dos", "Tres"]

    def test_colapsa_espacios_y_saltos_internos(self) -> None:
        texto = acquire._html_to_paragraphs("<p>Hola\n   mundo\t  cruel</p>")
        assert texto == "Hola mundo cruel"


class TestRelevancia:
    def test_acepta_texto_largo_y_pertinente(self) -> None:
        assert acquire._is_relevant("Estructuras condicionales", _ARTICLE)

    def test_rechaza_texto_demasiado_corto(self) -> None:
        # Una desambiguación o una entradilla: cae en el filtro de longitud.
        assert not acquire._is_relevant(
            "Estructuras condicionales", "Condicional puede referirse a"
        )

    def test_rechaza_un_solo_termino_coincidente(self) -> None:
        # "estructuras" aparece suelta en casi cualquier artículo de programación;
        # por eso se exigen dos términos del tema y no uno.
        texto = (
            "Las estructuras de datos organizan la información en memoria de formas "
            "distintas según el problema. Un árbol binario ordena sus nodos y permite "
            "búsquedas rápidas, mientras que una lista enlazada favorece la inserción. "
            "La elección adecuada depende del patrón de acceso previsto por el programa."
        )
        assert not acquire._is_relevant("Estructuras condicionales", texto)

    def test_tema_de_una_sola_palabra_necesita_una_coincidencia(self) -> None:
        assert acquire._is_relevant("Arreglos", _ARTICLE.replace("estructura", "arreglo"))


class TestAcquireForTopic:
    def _stub_wiki(self, monkeypatch: pytest.MonkeyPatch, extract: str = _ARTICLE) -> list[str]:
        llamadas: list[str] = []

        async def fake_fetch_json(url: str) -> dict[str, Any]:
            llamadas.append(url)
            if "list=search" in url:
                return {"query": {"search": [{"pageid": 11}, {"pageid": 22}]}}
            return {
                "query": {
                    "pages": {
                        "11": {"title": "Estructura condicional", "extract": extract},
                        "22": {"title": "Sentencia if", "extract": extract},
                    }
                }
            }

        monkeypatch.setattr(acquire, "_fetch_json", fake_fetch_json)
        monkeypatch.setattr(acquire, "_POLITENESS_DELAY_SECONDS", 0)
        return llamadas

    async def test_trae_articulos_de_wikipedia(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._stub_wiki(monkeypatch)
        fuentes = await acquire.acquire_for_topic(
            "Estructuras condicionales", level="basico", max_sources=2
        )
        assert [f.title for f in fuentes] == ["Estructura condicional", "Sentencia if"]
        assert all(f.origin == "wikipedia" for f in fuentes)
        assert all(f.url.startswith("https://es.wikipedia.org/") for f in fuentes)

    async def test_respeta_el_tope_de_fuentes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._stub_wiki(monkeypatch)
        fuentes = await acquire.acquire_for_topic(
            "Estructuras condicionales", level="basico", max_sources=1
        )
        assert len(fuentes) == 1

    async def test_descarta_extractos_irrelevantes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._stub_wiki(monkeypatch, extract="Breve.")
        fuentes = await acquire.acquire_for_topic("Estructuras condicionales", level="basico")
        assert fuentes == []

    async def test_las_urls_del_docente_van_primero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Son una señal explícita de intención: su material entra aunque el cupo
        # se agotara con Wikipedia.
        self._stub_wiki(monkeypatch)
        _stub_resolve(monkeypatch, ["93.184.216.34"])

        async def fake_fetch_text(url: str) -> tuple[str, str]:
            return "text/html", f"<p>{_ARTICLE}</p>"

        monkeypatch.setattr(acquire, "_fetch_text", fake_fetch_text)

        fuentes = await acquire.acquire_for_topic(
            "Estructuras condicionales",
            level="basico",
            extra_urls=["https://docente.ejemplo.org/apunte"],
            max_sources=2,
        )
        assert fuentes[0].origin == "teacher_url"
        assert fuentes[1].origin == "wikipedia"

    async def test_un_fallo_de_fuente_no_tumba_el_tema(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # `guide_writer` degrada bien con el RAG vacío: propagar el error
        # tumbaría el tema entero de la rúbrica por un 503 de Wikipedia.
        async def fake_fetch_json(url: str) -> dict[str, Any]:
            raise ValueError("respuesta ilegible")

        monkeypatch.setattr(acquire, "_fetch_json", fake_fetch_json)
        monkeypatch.setattr(acquire, "_POLITENESS_DELAY_SECONDS", 0)
        assert await acquire.acquire_for_topic("Ciclos anidados", level="intermedio") == []

    async def test_url_interna_del_docente_se_descarta_sin_tumbar_el_resto(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._stub_wiki(monkeypatch)
        _stub_resolve(monkeypatch, ["169.254.169.254"])
        fuentes = await acquire.acquire_for_topic(
            "Estructuras condicionales",
            level="basico",
            extra_urls=["https://interno.ejemplo.org/"],
            max_sources=1,
        )
        assert [f.origin for f in fuentes] == ["wikipedia"]

    async def test_bandera_apagada_no_hace_red(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from logica.config import get_settings

        get_settings.cache_clear()
        monkeypatch.setenv("CONTENT_ACQUISITION_ENABLED", "false")
        try:
            assert await acquire.acquire_for_topic("Arreglos", level="basico") == []
        finally:
            get_settings.cache_clear()
