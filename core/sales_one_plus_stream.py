"""Incremental marker filter for the dormant one-Plus candidate.

The provider emits raw text chunks.  This parser withholds control markers
until they are complete, then streams only the answer body to the patient
callback.  ``@ADMIN`` and everything after it stay internal.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from core.sales_one_plus_protocol import SalesOnePlusMarkerScanner

SalesOnePlusStreamDecision = Literal["answer", "admin"]


class SalesOnePlusStreamParser:
    """Parse arbitrary provider chunk boundaries without leaking control text."""

    def __init__(self, on_delta: Callable[[str], None]) -> None:
        self._scanner = SalesOnePlusMarkerScanner(on_delta)

    @property
    def answer_text(self) -> str:
        return self._scanner.answer_text

    def ingest(self, raw: object) -> None:
        self._scanner.ingest(raw)

    def finalize(self) -> tuple[SalesOnePlusStreamDecision, str | None]:
        return self._scanner.finalize()
