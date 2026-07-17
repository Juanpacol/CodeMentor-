"""Pure text chunking — no model, no I/O — so it's cheap to unit test
exhaustively regardless of what embedding backend `embedder.py` uses."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    index: int
    text: str


def chunk_text(text: str, *, max_chars: int = 800, overlap_chars: int = 100) -> list[Chunk]:
    """Splits on paragraph boundaries first, then greedily packs paragraphs
    into chunks up to `max_chars`, carrying `overlap_chars` of trailing
    context into the next chunk so a fact split across a boundary isn't lost
    entirely to either chunk."""
    if not text.strip():
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [text.strip()]

    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
            continue

        if current:
            chunks.append(current)
            current = current[-overlap_chars:] + "\n\n" + paragraph if overlap_chars else paragraph
        else:
            current = paragraph

        # A single paragraph longer than max_chars still gets hard-split so
        # no chunk ever exceeds the budget by an unbounded amount.
        while len(current) > max_chars:
            chunks.append(current[:max_chars])
            current = current[max_chars - overlap_chars :] if overlap_chars else current[max_chars:]

    if current:
        chunks.append(current)

    return [Chunk(index=i, text=c) for i, c in enumerate(chunks)]
