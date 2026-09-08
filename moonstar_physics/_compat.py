"""Minimal local stand-ins for the (now-removed) Python `moonstar_core`
package's `SessionContext` and `NonRetryableTransformError`.

moonstar-physics's deterministic transforms were originally written
against the Python `moonstar` gateway's transform contract (a
`SessionContext` type hint none of them actually reads, and
`NonRetryableTransformError` for malformed-input rejection). That gateway
no longer exists in this workspace — moonstar-rs replaced it, and it has
no runtime plugin mechanism these transforms could register into anyway.
They now run locally, in-process, via `local_pipeline.py`, rather than
through any gateway transform registry. This module keeps the transform
functions' existing signatures/behavior unchanged without depending on the
deleted package.
"""
from __future__ import annotations


class SessionContext:
    """Placeholder — none of moonstar-physics's transforms read ctx."""


class NonRetryableTransformError(Exception):
    """Raised by a transform that should fail immediately, no retry."""
