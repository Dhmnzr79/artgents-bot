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
    if plan.is_price_answer:
        assert plan.price_block is not None
        parts.append(plan.price_block.display_text.strip())
        parts.extend(_condition_display_texts(plan.required_offer_conditions))
        if plan.patient_text:
            parts.append(plan.patient_text.strip())
        parts.extend(block.display_text.strip() for block in plan.requested_fact_blocks)
        parts.extend(block.display_text.strip() for block in plan.promo_blocks)
        parts.extend(_render_amplifier_list(plan))
        parts.extend(_render_textual_cta(plan))
        return _join_parts(parts)

    if plan.patient_text:
        parts.append(plan.patient_text.strip())
    if plan.service_options_block is not None:
        parts.extend(_render_service_options(plan))
    parts.extend(block.display_text.strip() for block in plan.requested_fact_blocks)
    if plan.service_value_block is not None:
        parts.append(plan.service_value_block.display_text.strip())
    parts.extend(block.display_text.strip() for block in plan.promo_blocks)
    parts.extend(_render_amplifier_list(plan))
    parts.extend(_render_textual_cta(plan))
    return _join_parts(parts)


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
