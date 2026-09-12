"""Widget ref parser for tooling/linter (legacy orchestration removed in S69)."""
from __future__ import annotations

PRICE_REF_PREFIX = "price:"


def parse_price_widget_ref(ref: str) -> dict[str, str | None] | None:
    """Parse `price:classic`, `price:implantation/overview`, `price:all_on_4/includes`."""
    raw = (ref or "").strip()
    if not raw.lower().startswith(PRICE_REF_PREFIX):
        return None
    tail = raw[len(PRICE_REF_PREFIX) :].strip()
    if not tail:
        return None
    if "/" in tail:
        head, aspect = tail.split("/", 1)
        head = head.strip()
        aspect = aspect.strip().lower() or None
        if head.lower() == "implantation" and aspect == "overview":
            return {"service_id": None, "group_id": "implantation", "aspect": "overview"}
        if head:
            return {"service_id": head, "group_id": None, "aspect": aspect}
        return None
    return {"service_id": tail, "group_id": None, "aspect": None}
