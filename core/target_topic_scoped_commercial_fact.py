"""Topic-scoped commercial fact selection for service-less FullContext turns (S56)."""

from __future__ import annotations

from datetime import date

from contracts.response_schema import ResponseSchemaBundle, TargetCommercialFact


class TargetTopicScopedCommercialFactError(ValueError):
    """Typed error for invalid topic-scoped fact selection inputs."""

    def __init__(self, code: str, value: object) -> None:
        self.code = code
        self.value = value
        super().__init__(f"{code}: {value!r}")


def _fact_is_topic_eligible(
    fact: TargetCommercialFact,
    *,
    turn_topic: str,
    today_iso: str,
    shown_fact_ids: frozenset[str],
) -> bool:
    if not fact.allowed_topics or turn_topic not in fact.allowed_topics:
        return False
    if not fact.active or fact.id in shown_fact_ids:
        return False
    if fact.active_from is not None and today_iso < fact.active_from:
        return False
    if fact.active_until is not None and today_iso > fact.active_until:
        return False
    return True


def select_topic_scoped_consultation_fact(
    bundle: ResponseSchemaBundle,
    *,
    turn_topic: str | None,
    today: date,
    shown_fact_ids: frozenset[str] = frozenset(),
) -> TargetCommercialFact | None:
    """Select at most one topic-applicable commercial fact when service_id is None."""

    if type(bundle) is not ResponseSchemaBundle:
        raise TargetTopicScopedCommercialFactError(
            "topic_scoped_fact_bundle_invalid",
            bundle,
        )
    if type(today) is not date:
        raise TargetTopicScopedCommercialFactError("topic_scoped_fact_today_invalid", today)
    if turn_topic is None or not isinstance(turn_topic, str) or not turn_topic.strip():
        return None
    if not isinstance(shown_fact_ids, frozenset):
        raise TargetTopicScopedCommercialFactError(
            "topic_scoped_fact_shown_invalid",
            shown_fact_ids,
        )

    today_iso = today.isoformat()
    for fact_id in sorted(bundle.facts):
        fact = bundle.facts[fact_id]
        if _fact_is_topic_eligible(
            fact,
            turn_topic=turn_topic,
            today_iso=today_iso,
            shown_fact_ids=shown_fact_ids,
        ):
            return fact
    return None
