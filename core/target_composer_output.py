"""Strict Composer JSON envelope parsing (product path)."""

from __future__ import annotations

import json
from typing import Any

from contracts.target_composer_source_identity import TargetComposerSourceIdentity
from core.target_presentation_source_identity import normalize_content_ref


class TargetComposerOutputError(ValueError):
    def __init__(self, code: str, value: object) -> None:
        self.code = code
        self.value = value
        super().__init__(f"{code}: {value!r}")


def _error(code: str, value: object) -> None:
    raise TargetComposerOutputError(code, value)


def _normalize_refs(raw_refs: object) -> tuple[str, ...]:
    if not isinstance(raw_refs, list):
        return ()
    refs: list[str] = []
    seen: set[str] = set()
    for item in raw_refs:
        ref = normalize_content_ref(item)
        if ref is None or ref in seen:
            continue
        seen.add(ref)
        refs.append(ref)
    return tuple(refs)


def parse_composer_backend_output(raw: object) -> tuple[str, TargetComposerSourceIdentity | None, tuple[str, ...]]:
    """Parse live Composer JSON. Missing/unparseable answer is fail-closed upstream."""

    if not isinstance(raw, str) or not raw.strip():
        _error("composer_output_empty", raw)
    text = raw.strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        _error("composer_output_not_json", type(exc).__name__)

    if not isinstance(payload, dict):
        _error("composer_output_not_object", type(payload).__name__)

    answer = payload.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        _error("composer_output_answer_missing", payload.get("answer"))

    warnings: list[str] = []
    identity_raw = payload.get("source_identity")
    if identity_raw is None:
        warnings.append("source_identity_missing")
        return answer.strip(), None, tuple(warnings)

    if not isinstance(identity_raw, dict):
        warnings.append("source_identity_invalid_type")
        return answer.strip(), None, tuple(warnings)

    primary = normalize_content_ref(identity_raw.get("primary_content_ref"))
    used = _normalize_refs(identity_raw.get("used_content_refs"))
    if primary is not None and primary not in used:
        if used:
            used = (primary, *tuple(ref for ref in used if ref != primary))
        else:
            used = (primary,)
    if primary is None and not used:
        warnings.append("source_identity_empty")
        return answer.strip(), None, tuple(warnings)

    return (
        answer.strip(),
        TargetComposerSourceIdentity(
            primary_content_ref=primary,
            used_content_refs=used,
        ),
        tuple(warnings),
    )


def compose_composer_json_payload(
    *,
    answer: str,
    primary_content_ref: str | None = None,
    used_content_refs: tuple[str, ...] = (),
) -> str:
    """Test/recording helper for strict JSON envelope."""

    refs = list(used_content_refs)
    primary = normalize_content_ref(primary_content_ref)
    if primary is not None and primary not in refs:
        refs.insert(0, primary)
    payload: dict[str, Any] = {
        "answer": answer,
        "source_identity": {
            "primary_content_ref": primary,
            "used_content_refs": refs,
        },
    }
    return json.dumps(payload, ensure_ascii=False)


def composer_test_json(answer: str, *, primary_content_ref: str | None = None) -> str:
    """Wrap plain answer text for offline Composer test backends."""

    return compose_composer_json_payload(
        answer=answer,
        primary_content_ref=primary_content_ref,
    )
