from logica.ai.rag.chunking import chunk_text


def test_empty_text_returns_no_chunks() -> None:
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_short_text_becomes_single_chunk() -> None:
    chunks = chunk_text("Esto es un párrafo corto.", max_chars=800)
    assert len(chunks) == 1
    assert chunks[0].text == "Esto es un párrafo corto."
    assert chunks[0].index == 0


def test_splits_on_paragraph_boundaries_when_possible() -> None:
    text = "Párrafo uno." + "\n\n" + "Párrafo dos." + "\n\n" + "Párrafo tres."
    chunks = chunk_text(text, max_chars=20, overlap_chars=0)
    assert [c.text for c in chunks] == ["Párrafo uno.", "Párrafo dos.", "Párrafo tres."]


def test_long_single_paragraph_is_hard_split_under_budget() -> None:
    text = "a" * 2500
    chunks = chunk_text(text, max_chars=800, overlap_chars=100)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.text) <= 800


def test_chunks_are_sequentially_indexed() -> None:
    text = "\n\n".join(f"Párrafo número {i} con algo de contenido de relleno." for i in range(20))
    chunks = chunk_text(text, max_chars=100, overlap_chars=10)
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_overlap_carries_context_between_chunks() -> None:
    text = "\n\n".join(f"Frase {i}." * 5 for i in range(10))
    chunks = chunk_text(text, max_chars=60, overlap_chars=15)
    assert len(chunks) > 1
    # The tail of one chunk should reappear at the start of the next.
    tail = chunks[0].text[-15:]
    assert tail in chunks[1].text
