import pytest

from app.chunking import chunk_text


def test_chunking_overlap_and_coverage():
    assert chunk_text("abcdefghij", chunk_size=6, overlap=2) == ["abcdef", "efghij"]


def test_empty_profile_has_no_chunks():
    assert chunk_text("  ") == []


@pytest.mark.parametrize("size,overlap", [(3, 3), (3, 4), (0, 0), (-1, 0), (5, -1)])
def test_invalid_sizes_fail(size, overlap):
    with pytest.raises(ValueError):
        chunk_text("abc", chunk_size=size, overlap=overlap)


@pytest.mark.parametrize("size,overlap", [(10, 0), (10, 3), (50, 10), (900, 120)])
def test_chunks_cover_text_respect_size_and_overlap(size, overlap):
    text = " ".join(f"word{i}" for i in range(400))
    chunks = chunk_text(text, chunk_size=size, overlap=overlap)
    assert all(len(c) <= size for c in chunks)
    # Rebuild the normalized text by dropping each chunk's overlap with the previous one.
    rebuilt = chunks[0] + "".join(c[overlap:] for c in chunks[1:])
    assert rebuilt == text
    for prev, nxt in zip(chunks, chunks[1:]):
        assert prev[-overlap:] == nxt[:overlap] if overlap else True


def test_whitespace_is_normalized():
    assert chunk_text("  Playwright\n\n\tPython   pytest  ") == ["Playwright Python pytest"]


def test_short_text_is_single_chunk():
    assert chunk_text("QA engineer") == ["QA engineer"]


def test_unicode_and_cyrillic_preserved():
    text = "Инженер по тестированию — Playwright, Python ✅ résumé"
    assert chunk_text(text) == [text]
