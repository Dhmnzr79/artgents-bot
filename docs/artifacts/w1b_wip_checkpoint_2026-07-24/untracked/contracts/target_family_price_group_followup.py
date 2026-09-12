"""Target navigation refs for family price situation groups (W1b)."""

from __future__ import annotations

from dataclasses import dataclass

_FAMILY_PRICE_GROUP_REF_PREFIX = "target:family_price_group/"


@dataclass(frozen=True, slots=True)
class TargetFamilyPriceGroupFollowup:
    topic: str
    group_id: str
    label: str
    ref: str


def build_family_price_group_ref(*, topic: str, group_id: str) -> str:
    topic_eff = topic.strip()
    group_eff = group_id.strip()
    if not topic_eff or not group_eff:
        raise ValueError("family_price_group_ref_invalid")
    return f"{_FAMILY_PRICE_GROUP_REF_PREFIX}{topic_eff}/{group_eff}"


def parse_family_price_group_ref(ref: str) -> tuple[str, str] | None:
    text = ref.strip()
    if not text.startswith(_FAMILY_PRICE_GROUP_REF_PREFIX):
        return None
    tail = text.removeprefix(_FAMILY_PRICE_GROUP_REF_PREFIX)
    if "/" not in tail:
        return None
    topic, group_id = tail.split("/", 1)
    topic = topic.strip()
    group_id = group_id.strip()
    if not topic or not group_id or "/" in group_id:
        return None
    return topic, group_id


def build_family_price_group_followup(
    *,
    topic: str,
    group_id: str,
    label: str,
) -> TargetFamilyPriceGroupFollowup:
    label_eff = label.strip()
    if not label_eff:
        raise ValueError("family_price_group_label_invalid")
    ref = build_family_price_group_ref(topic=topic, group_id=group_id)
    return TargetFamilyPriceGroupFollowup(
        topic=topic.strip(),
        group_id=group_id.strip(),
        label=label_eff,
        ref=ref,
    )
