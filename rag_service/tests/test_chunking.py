import pytest
from app.chunking import chunk_text


def test_chunking_overlap_and_coverage():
    assert chunk_text("abcdefghij", chunk_size=6, overlap=2) == ["abcdef", "efghij"]


def test_empty_profile_has_no_chunks():
    assert chunk_text("  ") == []


def test_invalid_overlap_fails():
    with pytest.raises(ValueError):
        chunk_text("abc", chunk_size=3, overlap=3)
