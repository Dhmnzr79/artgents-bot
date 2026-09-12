"""Canonical topic membership derived from target service catalog content_ref."""

from __future__ import annotations

from contracts.target_response_spec import CanonicalToken
from pydantic import TypeAdapter, ValidationError

_TOPIC_ADAPTER = TypeAdapter(CanonicalToken)


class TargetServiceContentTopicError(ValueError):
    """Typed failure for invalid explicit content_ref topic parsing."""

    def __init__(self, code: str, value: object) -> None:
        self.code = code
        self.value = value
        super().__init__(f"{code}: {value!r}")


def parse_service_catalog_content_topic(content_ref: str | None) -> str | None:
    """Return canonical topic token from a service ``content_ref``, or ``None`` if absent/invalid.

    Client-owned convention: ``{topic}__{rest}.md`` (for example ``implantation__service__classic.md``).
    """

    if content_ref is None:
        return None
    if type(content_ref) is not str:
        raise TargetServiceContentTopicError(
            "service_content_ref_invalid",
            content_ref,
        )
    ref = content_ref.strip()
    if not ref.endswith(".md") or "__" not in ref:
        return None
    topic, rest = ref.split("__", 1)
    if (
        not topic
        or not rest
        or "/" in topic
        or "\\" in topic
        or "/" in ref
        or "\\" in ref
    ):
        return None
    try:
        return _TOPIC_ADAPTER.validate_python(topic)
    except ValidationError as exc:
        raise TargetServiceContentTopicError(
            "service_content_topic_invalid",
            content_ref,
        ) from exc


def service_catalog_content_topic_matches(
    content_ref: str | None,
    turn_topic: str,
) -> bool:
    """True when ``content_ref`` topic prefix equals ``turn_topic`` (canonical tokens)."""

    if type(turn_topic) is not str or not turn_topic.strip():
        return False
    try:
        expected = _TOPIC_ADAPTER.validate_python(turn_topic.strip())
    except ValidationError as exc:
        raise TargetServiceContentTopicError(
            "turn_topic_invalid",
            turn_topic,
        ) from exc
    parsed = parse_service_catalog_content_topic(content_ref)
    return parsed is not None and parsed == expected
