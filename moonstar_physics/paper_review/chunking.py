"""Splits long paper text into bounded word-count chunks for map-reduce
summarization. Pure, deterministic — no LLM calls here.
"""
from __future__ import annotations


class ChunkingError(ValueError):
    """Raised when a paper's text would produce more chunks than allowed."""


_DEFAULT_WORDS_PER_CHUNK = 3000
_DEFAULT_MAX_CHUNKS = 20


def chunk_text(
    text: str,
    words_per_chunk: int = _DEFAULT_WORDS_PER_CHUNK,
    max_chunks: int = _DEFAULT_MAX_CHUNKS,
) -> list[str]:
    words = text.split()
    if not words:
        return []

    chunks = [
        " ".join(words[i : i + words_per_chunk])
        for i in range(0, len(words), words_per_chunk)
    ]
    if len(chunks) > max_chunks:
        raise ChunkingError(
            f"paper text produced {len(chunks)} chunks of {words_per_chunk} words "
            f"({len(words)} words total), exceeding max_chunks={max_chunks}"
        )
    return chunks
