"""Pure text renderer for frozen ResolvedResponsePlan."""

from __future__ import annotations

from contracts.response_plan import ResolvedResponsePlan

_AMPLIFIER_HEADER = "Также мы предлагаем:"


def render_response_text(plan: ResolvedResponsePlan) -> str:
    """Render visible text from a frozen resolved plan only."""

    if plan.terminal_text is not None:
        return plan.terminal_text.strip()
    if plan.route == "CLARIFY":
        return (plan.patient_text or "").strip()

    parts: list[str] = []
    if plan.d2_part_failure_blocks:
        content_by_request = {
            block.request_id: block for block in plan.information_blocks
        }
        failures_by_request = {
            block.request_id: block for block in plan.d2_part_failure_blocks
        }
        for part in plan.d2_request_parts:
            if part.status == "unavailable":
                parts.append(failures_by_request[part.request_id].display_text.strip())
            elif part.kind == "price":
                _render_d2_price_parts(plan, parts)
            else:
                parts.append(content_by_request[part.request_id].display_text.strip())
        parts.extend(_condition_display_texts(plan.required_offer_conditions))
        if plan.patient_text:
            parts.append(plan.patient_text.strip())
        parts.extend(block.display_text.strip() for block in plan.requested_fact_blocks)
        parts.extend(block.display_text.strip() for block in plan.promo_blocks)
        parts.extend(_render_amplifier_list(plan))
        parts.extend(_render_textual_cta(plan))
        return _join_parts(parts)

    if plan.is_price_answer:
        if plan.d2_request_parts:
            blocks = {block.request_id: block for block in plan.information_blocks}
            for part in plan.d2_request_parts:
                if part.kind == "content":
                    parts.append(blocks[part.request_id].display_text.strip())
                    continue
                _render_d2_price_parts(plan, parts)
        else:
            _render_d2_price_parts(plan, parts)
        parts.extend(_condition_display_texts(plan.required_offer_conditions))
        if plan.patient_text:
            parts.append(plan.patient_text.strip())
        if not plan.d2_request_parts:
            parts.extend(block.display_text.strip() for block in plan.information_blocks)
        parts.extend(block.display_text.strip() for block in plan.requested_fact_blocks)
        parts.extend(block.display_text.strip() for block in plan.promo_blocks)
        parts.extend(_render_amplifier_list(plan))
        parts.extend(_render_textual_cta(plan))
        return _join_parts(parts)

    if plan.patient_text:
        parts.append(plan.patient_text.strip())
    parts.extend(block.display_text.strip() for block in plan.information_blocks)
    if plan.authored_service_alternative_block is not None:
        parts.extend(_render_authored_service_alternative(plan))
    elif plan.service_options_block is not None:
        parts.extend(_render_service_options(plan))
    parts.extend(block.display_text.strip() for block in plan.requested_fact_blocks)
    if plan.service_value_block is not None:
        parts.append(plan.service_value_block.display_text.strip())
    parts.extend(block.display_text.strip() for block in plan.promo_blocks)
    parts.extend(_render_amplifier_list(plan))
    parts.extend(_render_textual_cta(plan))
    return _join_parts(parts)


def _render_d2_price_parts(plan: ResolvedResponsePlan, parts: list[str]) -> None:
    scope = plan.d2_price_scope_decision
    if scope is not None:
        if scope.introduction_text is not None:
            parts.append(scope.introduction_text.strip())
        if scope.reason == "overview" and scope.unknown_extent_text is not None:
            parts.append(scope.unknown_extent_text.strip())
    if plan.price_block is not None:
        parts.append(plan.price_block.display_text.strip())
        return
    assert plan.d2_price_block is not None
    for row in plan.d2_price_block.rows:
        parts.append(row.display_text.strip())
        parts.extend(text.strip() for text in row.condition_texts)


def _render_authored_service_alternative(plan: ResolvedResponsePlan) -> list[str]:
    block = plan.authored_service_alternative_block
    if block is None:
        return []
    parts = [block.approved_text.strip()]
    if block.options:
        lines = [option.display_name.strip() for option in block.options]
        parts.append("\n".join(f"- {line}" for line in lines if line))
    return parts


def _render_service_options(plan: ResolvedResponsePlan) -> list[str]:
    block = plan.service_options_block
    if block is None:
        return []
    lines = [option.display_name.strip() for option in block.options]
    return ["\n".join(f"- {line}" for line in lines if line)]


def _condition_display_texts(
    conditions: tuple,
) -> list[str]:
    texts: list[str] = []
    for block in conditions:
        if block.entries:
            for entry in block.entries:
                text = entry.display_text.strip()
                label = getattr(entry, "offer_label", None)
                if label and label.strip():
                    texts.append(f"{label.strip()}: {text}")
                else:
                    texts.append(text)
        elif block.display_text:
            texts.append(block.display_text.strip())
    return texts


def _render_amplifier_list(plan: ResolvedResponsePlan) -> list[str]:
    if not plan.automatic_amplifier_blocks:
        return []
    lines = [_AMPLIFIER_HEADER]
    lines.extend(f"- {block.display_text.strip()}" for block in plan.automatic_amplifier_blocks)
    return ["\n".join(lines)]


def _render_textual_cta(plan: ResolvedResponsePlan) -> list[str]:
    if plan.textual_cta_block is None:
        return []
    return [plan.textual_cta_block.text.strip()]


def _join_parts(parts: list[str]) -> str:
    cleaned = [part for part in parts if part]
    if not cleaned:
        return ""
    return "\n\n".join(cleaned)
