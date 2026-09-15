"""Eval-only incremental probe for patient_text inside streamed JSON envelopes."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class PatientTextStreamProbe:
    """Track patient_text field timing without logging decoded text."""

    raw_json: str = ""
    _buffer: str = ""
    _phase: str = "seek_key"
    _escape: bool = False
    _value_chars: list[str] = field(default_factory=list)
    first_raw_chunk_at: float | None = None
    patient_text_value_start_at: float | None = None
    patient_text_value_end_at: float | None = None
    patient_text_chunk_count: int = 0
    _chunk_had_value_chars: bool = False

    def feed(self, chunk: str, arrival_monotonic: float) -> None:
        if not chunk:
            return
        self.raw_json += chunk
        if self.first_raw_chunk_at is None:
            self.first_raw_chunk_at = arrival_monotonic
        self._chunk_had_value_chars = False
        for char in chunk:
            self._consume(char, arrival_monotonic)
        if self._chunk_had_value_chars:
            self.patient_text_chunk_count += 1

    @property
    def streamed_patient_text(self) -> str:
        return "".join(self._value_chars)

    @property
    def two_plus_value_chunks(self) -> bool:
        return self.patient_text_chunk_count >= 2

    def _consume(self, char: str, arrival_monotonic: float) -> None:
        self._buffer += char
        if self._phase == "seek_key":
            if self._buffer.endswith('"patient_text"'):
                self._phase = "after_key"
            if len(self._buffer) > 64:
                self._buffer = self._buffer[-48:]
            return
        if self._phase == "after_key":
            if char.isspace() or char == ":":
                return
            if char == "n" and self._buffer.rstrip().endswith("null"):
                self._phase = "done"
                return
            if char == '"':
                self._phase = "in_value"
            return
        if self._phase == "in_value":
            if self._escape:
                self._escape = False
                self._value_chars.append(char)
                self._chunk_had_value_chars = True
                if self.patient_text_value_start_at is None:
                    self.patient_text_value_start_at = arrival_monotonic
                return
            if char == "\\":
                self._escape = True
                return
            if char == '"':
                self._phase = "done"
                return
            self._value_chars.append(char)
            self._chunk_had_value_chars = True
            if self.patient_text_value_start_at is None:
                self.patient_text_value_start_at = arrival_monotonic

    def finalize_timing(self, stream_completed_at: float) -> None:
        if self.patient_text_value_end_at is None and self._phase == "done":
            self.patient_text_value_end_at = stream_completed_at
