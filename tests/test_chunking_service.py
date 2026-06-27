from app.services.chunking_service import chunk_text


def test_chunk_text_splits_into_multiple_chunks():
    text = " ".join(f"word{i}" for i in range(1200))
    chunks = chunk_text(text, chunk_size=500, overlap=50)
    assert len(chunks) > 1


def test_chunk_text_respects_chunk_size():
    text = " ".join(f"word{i}" for i in range(1000))
    chunks = chunk_text(text, chunk_size=500, overlap=50)
    for chunk in chunks[:-1]:  # the last chunk is allowed to be shorter
        assert len(chunk.split()) == 500


def test_chunk_text_overlap_repeats_boundary_words():
    text = " ".join(f"word{i}" for i in range(1000))
    chunks = chunk_text(text, chunk_size=500, overlap=50)
    first_words = chunks[0].split()
    second_words = chunks[1].split()
    assert first_words[-50:] == second_words[:50]


def test_chunk_text_short_text_returns_single_chunk():
    text = "This is a short piece of text."
    chunks = chunk_text(text, chunk_size=500, overlap=50)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_text_empty_string_returns_empty_list():
    assert chunk_text("", chunk_size=500, overlap=50) == []


def test_chunk_text_whitespace_only_returns_empty_list():
    assert chunk_text("   \n\t  ", chunk_size=500, overlap=50) == []


def test_chunk_text_no_overlap_reconstructs_original_text():
    text = " ".join(f"word{i}" for i in range(1000))
    chunks = chunk_text(text, chunk_size=500, overlap=0)
    assert len(chunks) == 2
    combined = chunks[0].split() + chunks[1].split()
    assert combined == text.split()