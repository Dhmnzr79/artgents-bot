"""Apply AnswerPlan append kinds to deterministic answer tail (no LLM)."""

from __future__ import annotations

from typing import Any

from contracts.answer_plan import AnswerPlan, PlanAppendKind
from core.answer_planner import payment_terms_ref
from core.price_offers import build_price_append_for_lookup
from retriever import get_chunk_by_ref

_PAYMENT_STAGE_MARKERS = (
    "оплата по этапам",
)

_PAYMENT_TERMS_DUPLICATE_MARKERS = (
    "рассроч",
    "налоговый вычет",
    "беспроцентн",
)


def append_text_has_payment_stages(text: str | None) -> bool:
    low = (text or "").strip().lower()
    if not low:
        return False
    return any(m in low for m in _PAYMENT_STAGE_MARKERS)


def append_text_covers_payment_terms(text: str | None) -> bool:
    low = (text or "").strip().lower()
    if not low:
        return False
    return any(m in low for m in _PAYMENT_TERMS_DUPLICATE_MARKERS)


def price_meta_has_installment_fact(meta: dict[str, Any] | None) -> bool:
    if not isinstance(meta, dict):
        return False
    facts = meta.get("pricebook_natural_facts") or meta.get("pricebook_fact_refs") or []
    if not isinstance(facts, list):
        return False
    return any("installment" in str(x).lower() for x in facts)


def suppress_payment_terms(
    *,
    existing_append: str | None,
    price_offer_meta: dict[str, Any] | None,
    answer_body: str | None = None,
) -> bool:
    combined = "\n".join(
        p for p in (answer_body, existing_append) if (p or "").strip()
    )
    if append_text_covers_payment_terms(combined):
        return True
    if price_meta_has_installment_fact(price_offer_meta):
        return True
    return False


def _korotko_body(chunk: dict) -> str:
    parts: list[str] = []
    h3 = str(chunk.get("h3") or "").strip()
    body = str(chunk.get("text") or "").strip()
    if h3:
        parts.append(h3)
    if body:
        parts.append(body)
    return "\n\n".join(parts).strip()


def should_suppress_payment_terms_quick_ref(
    *,
    plan_meta: dict[str, Any] | None = None,
    doc_id: str | None = None,
    answer_body: str | None = None,
) -> bool:
    """Hide payment_terms quick-reply when the answer already covers that topic."""
    if doc_id and doc_id.strip().lower() == "clinic__info__payment_terms":
        return True
    if append_text_covers_payment_terms(answer_body):
        return True
    if not isinstance(plan_meta, dict):
        return False
    apply_meta = plan_meta.get("answer_plan_apply")
    if isinstance(apply_meta, dict):
        kinds = {
            str(x).strip()
            for x in (apply_meta.get("applied") or []) + (apply_meta.get("suppressed") or [])
            if str(x).strip()
        }
        if "payment_terms" in kinds:
            return True
    plan = plan_meta.get("answer_plan")
    if isinstance(plan, dict) and "payment_terms" in (plan.get("append") or []):
        if append_text_covers_payment_terms(answer_body):
            return True
    return False


def payment_terms_suppress_refs(
    *,
    plan_meta: dict[str, Any] | None = None,
    doc_id: str | None = None,
    answer_body: str | None = None,
) -> list[str]:
    if should_suppress_payment_terms_quick_ref(
        plan_meta=plan_meta,
        doc_id=doc_id,
        answer_body=answer_body,
    ):
        return [payment_terms_ref()]
    return []


def render_payment_terms_append(*, client_id: str | None) -> str | None:
    ch = get_chunk_by_ref(payment_terms_ref(), client_id=client_id)
    if not ch:
        return None
    body = _korotko_body(ch)
    if not body:
        return None
    return f"**Условия оплаты:**\n{body}"


def _merge_append_parts(*parts: str | None) -> str | None:
    merged: list[str] = []
    for p in parts:
        t = (p or "").strip()
        if not t:
            continue
        if any(t in x or x in t for x in merged):
            continue
        merged.append(t)
    return "\n\n".join(merged) if merged else None


def apply_answer_plan_append(
    plan: AnswerPlan | None,
    *,
    client_id: str | None,
    service_id: str | None,
    q: str,
    existing_append: str | None,
    price_offer_meta: dict[str, Any] | None,
    answer_body: str | None = None,
) -> tuple[str | None, dict[str, Any]]:
    """Return merged append text + telemetry for meta.answer_plan_apply."""
    telemetry: dict[str, Any] = {
        "requested": [],
        "applied": [],
        "suppressed": list(plan.suppressed_append) if plan else [],
    }
    if plan is None or not plan.append:
        return (existing_append or None), telemetry

    svc = (service_id or plan.service_id or "").strip()
    parts: list[str | None] = [(existing_append or "").strip() or None]
    suppressed: list[PlanAppendKind] = list(plan.suppressed_append)

    for kind in plan.append:
        telemetry["requested"].append(kind)
        if kind == "price_offer":
            if not svc:
                continue
            body_text = (answer_body or "").strip()
            if body_text and ("₽" in body_text or "руб" in body_text.lower()):
                continue
            if append_text_has_payment_stages(existing_append):
                continue
            extra, _meta = build_price_append_for_lookup(
                client_id=client_id,
                service_id=svc,
                q=q,
            )
            if extra and not any((extra or "").strip() in (p or "") for p in parts):
                parts.append(extra)
                telemetry["applied"].append(kind)
            continue
        if kind == "payment_terms":
            if suppress_payment_terms(
                existing_append=_merge_append_parts(*parts),
                price_offer_meta=price_offer_meta,
                answer_body=answer_body,
            ):
                if kind not in suppressed:
                    suppressed.append(kind)
                continue
            pt = render_payment_terms_append(client_id=client_id)
            if pt and not any("условия оплаты" in (p or "").lower() for p in parts):
                parts.append(pt)
                telemetry["applied"].append(kind)
            continue
        if kind == "boundary":
            continue

    telemetry["suppressed"] = suppressed
    return _merge_append_parts(*parts), telemetry
