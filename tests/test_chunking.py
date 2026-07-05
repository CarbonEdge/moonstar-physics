"""Tests for moonstar_physics.paper_review.chunking."""
from __future__ import annotations

import pytest

from moonstar_physics.paper_review.chunking import ChunkingError, chunk_text


def test_empty_text_returns_empty_list():
    assert chunk_text("") == []
    assert chunk_text("   \n  ") == []


def test_short_text_is_one_chunk():
    text = " ".join(["word"] * 100)
    chunks = chunk_text(text, words_per_chunk=3000)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_splits_into_expected_number_of_chunks():
    text = " ".join(["word"] * 250)
    chunks = chunk_text(text, words_per_chunk=100)
    assert len(chunks) == 3
    assert chunks[0] == " ".join(["word"] * 100)
    assert chunks[1] == " ".join(["word"] * 100)
    assert chunks[2] == " ".join(["word"] * 50)


def test_exceeding_max_chunks_raises_chunking_error():
    text = " ".join(["word"] * 1000)
    with pytest.raises(ChunkingError, match="exceeding max_chunks=5"):
        chunk_text(text, words_per_chunk=100, max_chunks=5)


def test_exactly_max_chunks_is_allowed():
    text = " ".join(["word"] * 500)
    chunks = chunk_text(text, words_per_chunk=100, max_chunks=5)
    assert len(chunks) == 5
