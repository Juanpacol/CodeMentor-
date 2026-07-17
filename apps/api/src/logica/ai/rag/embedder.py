"""Local embeddings via sentence-transformers (§9.4 "modelo autoalojado para
tareas simples"): free, no external API call, no student data leaving the
server just to compute a similarity score. Model loads lazily and once —
importing this module must stay cheap so it doesn't slow down every test
collection, only the first call that actually needs it.

`embed_texts`/`embed_query` are the indirection points tests monkeypatch to
avoid loading the real (large) model in CI — mirrors the pattern in
ai.harness.router._completion_fn."""

from typing import cast

EMBEDDING_DIMENSIONS = 384
_MODEL_NAME = "intfloat/multilingual-e5-small"

_model: object | None = None


def _get_model() -> object:
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embeds passages for storage. e5 models expect a "passage: " prefix on
    indexed text and "query: " on search queries — mixing them up silently
    degrades retrieval quality without erroring, so both prefixes are applied
    here rather than left to callers to remember."""
    model = _get_model()
    prefixed = [f"passage: {t}" for t in texts]
    vectors = model.encode(prefixed, normalize_embeddings=True).tolist()  # type: ignore[attr-defined]
    return cast(list[list[float]], vectors)


def embed_query(text: str) -> list[float]:
    model = _get_model()
    result = model.encode([f"query: {text}"], normalize_embeddings=True)  # type: ignore[attr-defined]
    return list(result[0])
