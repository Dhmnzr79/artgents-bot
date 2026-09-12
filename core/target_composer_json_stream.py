"""Incremental extraction of the patient-facing ``answer`` JSON string."""

from __future__ import annotations

import re
from dataclasses import dataclass


_ANSWER_START = re.compile(r'"answer"\s*:\s*"')
_SIMPLE_ESCAPES = {
    '"': '"',
    "\\": "\\",
    "/": "/",
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
}


def decoded_answer_prefix(raw_json: str) -> str:
    """Decode every complete character currently available in ``answer``.

    An incomplete escape sequence or an unfinished JSON string is normal while
    streaming and simply leaves the incomplete tail buffered for the next chunk.
    """

    match = _ANSWER_START.search(raw_json)
    if match is None:
        return ""
    source = raw_json[match.end() :]
    out: list[str] = []
    index = 0
    while index < len(source):
        char = source[index]
        if char == '"':
            break
        if char != "\\":
            out.append(char)
            index += 1
            continue
        if index + 1 >= len(source):
            break
        escape = source[index + 1]
        if escape in _SIMPLE_ESCAPES:
            out.append(_SIMPLE_ESCAPES[escape])
            index += 2
            continue
        if escape == "u":
            code = source[index + 2 : index + 6]
            if len(code) < 4 or any(ch not in "0123456789abcdefABCDEF" for ch in code):
                break
            value = int(code, 16)
            if 0xD800 <= value <= 0xDBFF:
                tail = source[index + 6 : index + 12]
                if len(tail) < 6 or not tail.startswith("\\u"):
                    break
                low_code = tail[2:]
                if any(ch not in "0123456789abcdefABCDEF" for ch in low_code):
                    break
                low = int(low_code, 16)
                if not 0xDC00 <= low <= 0xDFFF:
                    break
                out.append(chr(0x10000 + ((value - 0xD800) << 10) + low - 0xDC00))
                index += 12
                continue
            if 0xDC00 <= value <= 0xDFFF:
                break
            out.append(chr(value))
            index += 6
            continue
        # Invalid JSON is handled by the canonical final parser. Never expose an
        # invalid escaped byte speculatively.
        break
    return "".join(out)


@dataclass(slots=True)
class TargetComposerJsonStream:
    raw_json: str = ""
    answer_sent_chars: int = 0

    def ingest(self, raw_delta: str) -> str:
        self.raw_json += raw_delta or ""
        decoded = decoded_answer_prefix(self.raw_json)
        delta = decoded[self.answer_sent_chars :]
        self.answer_sent_chars = len(decoded)
        return delta
