"""Buffered fail-closed JSON envelope accumulator for production streaming."""

from __future__ import annotations

from collections.abc import Callable

from contracts.one_call_envelope import OneCallEnvelope
from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot
from core.one_call_envelope_protocol import (
    MAX_ENVELOPE_UTF8_BYTES,
    OneCallEnvelopeProtocolError,
    envelope_utf8_byte_length,
    parse_production_envelope_json,
)


class SalesOnePlusStreamParser:
    """Accumulate raw provider JSON until finalize; no patient callback before validation."""

    def __init__(
        self,
        on_delta: Callable[[str], None],
        *,
        active_service_catalog: ActiveServiceCatalogSnapshot,
    ) -> None:
        self._on_delta = on_delta
        self._active_service_catalog = active_service_catalog
        self._buffer = ""
        self._buffer_bytes = 0
        self._validated_envelope: OneCallEnvelope | None = None

    @property
    def has_partial_content(self) -> bool:
        return bool(self._buffer)

    @property
    def answer_text(self) -> str:
        if self._validated_envelope is None:
            return ""
        return self._validated_envelope.patient_text or ""

    @property
    def validated_envelope(self) -> OneCallEnvelope | None:
        return self._validated_envelope

    def ingest(self, raw: object) -> None:
        if not isinstance(raw, str) or not raw:
            return
        chunk_bytes = envelope_utf8_byte_length(raw)
        if self._buffer_bytes + chunk_bytes > MAX_ENVELOPE_UTF8_BYTES:
            raise OneCallEnvelopeProtocolError("envelope_oversized")
        self._buffer += raw
        self._buffer_bytes += chunk_bytes

    def finalize(self) -> OneCallEnvelope:
        envelope = parse_production_envelope_json(
            self._buffer,
            active_service_catalog=self._active_service_catalog,
        )
        self._validated_envelope = envelope
        if envelope.route in {"ANSWER", "CLARIFY"}:
            patient_text = envelope.patient_text
            if patient_text is None or not patient_text.strip():
                raise OneCallEnvelopeProtocolError("patient_text_required")
            self._on_delta(patient_text)
        return envelope
