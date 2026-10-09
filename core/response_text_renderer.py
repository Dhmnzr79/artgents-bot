"""Pure text renderer for frozen ResolvedResponsePlan."""

from __future__ import annotations

from contracts.response_plan import D2FrozenPriceRow, ResolvedResponsePlan

_AMPLIFIER_HEADER = "Также мы предлагаем:"


def render_response_text(plan: ResolvedResponsePlan) -> str:
    """Render visible text from a frozen resolved plan only."""

    if plan.terminal_text is not None:
        return plan.terminal_text.strip()
    if plan.route == "CLARIFY":
        return (plan.patient_text or "").strip()

    parts: list[str] = []
    if plan.d2_request_parts:
        content_by_request = {
            block.request_id: block for block in plan.information_blocks
        }
        contacts_by_request = {
            block.request_id: block for block in plan.d2_contact_blocks
        }
        policies_by_request = {
            block.request_id: block for block in plan.d2_policy_blocks
        }
        failures_by_request = {
            block.request_id: block for block in plan.d2_part_failure_blocks
        }
        deferred_by_request = {
            block.request_id: block for block in plan.d2_part_deferred_blocks
        }
        exact_by_request = {b.request_id: b for b in plan.d2_exact_text_blocks}
        # Closing clinic references/clarifications follow the whole answer,
        # including price-owned conditions and commercial additions.
        body_end = len(plan.d2_request_parts)
        while body_end and (
            plan.d2_request_parts[body_end - 1].status == "answered"
            and plan.d2_request_parts[body_end - 1].kind in {"reference", "clarification"}
            and plan.d2_request_parts[body_end - 1].scope == "clinic"
        ):
            body_end -= 1
        for part in plan.d2_request_parts[:body_end]:
            if part.status == "unavailable":
                parts.append(failures_by_request[part.request_id].display_text.strip())
            elif part.status == "deferred":
                parts.append(deferred_by_request[part.request_id].display_text.strip())
            elif part.kind in {"clarification", "reference", "doctors", "commercial_fact", "price_clarification", "price_reference"}:
                parts.append(exact_by_request[part.request_id].display_text.strip())
            elif part.kind == "price":
                if plan.d2_price_block is not None and plan.patient_text:
                    parts.append(plan.patient_text.strip())
                _render_d2_price_parts(plan, parts)
            elif part.kind == "price_detail":
                _render_d2_price_detail(next(block for block in plan.d2_price_detail_blocks
                    if block.request_id == part.request_id), parts)
            elif part.kind == "contact":
                parts.append(contacts_by_request[part.request_id].display_text.strip())
            elif part.kind == "clinic_policy":
                parts.append(policies_by_request[part.request_id].display_text.strip())
            else:
                block = content_by_request.get(part.request_id)
                if block is not None:
                    parts.append(block.display_text.strip())
        parts.extend(_condition_display_texts(plan.required_offer_conditions))
        if plan.patient_text and plan.d2_price_block is None:
            parts.append(plan.patient_text.strip())
        parts.extend(block.display_text.strip() for block in plan.requested_fact_blocks)
        parts.extend(block.display_text.strip() for block in plan.promo_blocks)
        parts.extend(_render_d2_commercial_packages(plan))
        parts.extend(_render_amplifier_list(plan))
        parts.extend(_render_textual_cta(plan))
        parts.extend(exact_by_request[part.request_id].display_text.strip()
                     for part in plan.d2_request_parts[body_end:])
        return _join_parts(parts)

    if plan.is_price_answer:
        if plan.d2_price_block is not None and plan.patient_text:
            parts.append(plan.patient_text.strip())
        _render_d2_price_parts(plan, parts)
        parts.extend(_condition_display_texts(plan.required_offer_conditions))
        if plan.patient_text and plan.d2_price_block is None:
            parts.append(plan.patient_text.strip())
        if not plan.d2_request_parts:
            parts.extend(block.display_text.strip() for block in plan.information_blocks)
        parts.extend(block.display_text.strip() for block in plan.requested_fact_blocks)
        parts.extend(block.display_text.strip() for block in plan.promo_blocks)
        parts.extend(_render_d2_commercial_packages(plan))
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
    parts.extend(_render_d2_commercial_packages(plan))
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
    rows = plan.d2_price_block.rows
    if any(row.service_name is None or row.price_display_text is None for row in rows):
        # Older frozen plans retain their original display text on replay.
        for row in rows:
            parts.append(row.display_text.strip())
            parts.extend(text.strip() for text in row.condition_texts)
        return
    if scope is not None:
        _render_compact_price_group(
            rows, parts,
            show_service_in_each_row=len({row.service_id for row in rows}) > 1,
        )
        return
    start = 0
    while start < len(rows):
        end = start + 1
        while end < len(rows) and rows[end].service_id == rows[start].service_id:
            end += 1
        _render_compact_price_group(rows[start:end], parts, show_service_in_each_row=False)
        start = end


def _render_d2_price_detail(detail, parts: list[str]) -> None:
    rows = detail.rows
    if len(rows) == 1:
        parts.append(f"**{rows[0].label}**")
    else:
        heading = (f"Что входит в стоимость: {rows[0].service_name}"
                   if detail.aspect == "includes" else f"Как оплачивается: {rows[0].service_name}")
        parts.append(f"**{heading}**")
    if detail.aspect == "stages":
        schedules = tuple(row.stages for row in rows)
        if all(not row.missing for row in rows) and all(item == schedules[0] for item in schedules):
            heading = ("Порядок оплаты одинаковый для всех этих вариантов:\n"
                       if len(rows) > 1 else "Оплата по этапам:\n")
            parts.append(heading + "\n".join(f"- {line}" for line in schedules[0]))
        else:
            for row in rows:
                if len(rows) > 1:
                    parts.append(f"**{row.label}**")
                parts.append(
                    "Для этого варианта порядок оплаты не указан."
                    if row.missing else "Оплата по этапам:\n" + "\n".join(f"- {line}" for line in row.stages)
                )
        return
    complete = tuple(row for row in rows if not row.missing)
    common_includes = tuple(
        item for item in complete[0].includes
        if len(complete) == len(rows) and all(item in row.includes for row in complete[1:])
    ) if complete else ()
    common_excludes = tuple(
        item for item in complete[0].excludes
        if len(complete) == len(rows) and all(item in row.excludes for row in complete[1:])
    ) if complete else ()
    if common_includes:
        identical = all(
            all(item in common_includes for item in row.includes)
            and all(item in common_excludes for item in row.excludes)
            for row in rows
        )
        heading = (("Состав одинаковый для всех этих вариантов:\n" if identical
                    else "Во все эти варианты входят:\n")
                   if len(rows) > 1 else "В стоимость входят:\n")
        parts.append(heading + "\n".join(f"- {line}" for line in common_includes))
    if common_excludes:
        heading = ("Ни в один из этих вариантов не входят:\n" if len(rows) > 1
                   else "В эту стоимость не входят:\n")
        parts.append(heading + "\n".join(f"- {line}" for line in common_excludes))
    for row in rows:
        local_includes = tuple(item for item in row.includes if item not in common_includes)
        local_excludes = tuple(item for item in row.excludes if item not in common_excludes)
        if not row.missing and not local_includes and not local_excludes:
            continue
        if len(rows) > 1:
            parts.append(f"**{row.label}**")
        if row.missing:
            parts.append("Для этого варианта состав не указан.")
            continue
        if local_includes:
            heading = "Также входят:\n" if common_includes else "В стоимость входят:\n"
            parts.append(heading + "\n".join(f"- {line}" for line in local_includes))
        if local_excludes:
            parts.append("В его стоимость не входят:\n" + "\n".join(f"- {line}" for line in local_excludes))


def _render_compact_price_group(
    rows: tuple[D2FrozenPriceRow, ...], parts: list[str], *, show_service_in_each_row: bool,
) -> None:
    details = tuple(
        tuple(dict.fromkeys(
            (*((row.scope_text,) if row.scope_text else ()), *row.condition_texts)
        ))
        for row in rows
    )
    common = tuple(text for text in details[0] if all(text in item for item in details[1:]))

    def price_text(row: D2FrozenPriceRow) -> str:
        assert row.price_display_text is not None
        return (
            row.price_display_text
            if row.mode == "no_public_price" else f"**{row.price_display_text}**"
        )

    if len(rows) == 1:
        row = rows[0]
        assert row.service_name is not None
        name = f"**{row.service_name}**"
        if row.variant_label:
            name += f" — {row.variant_label}"
        scope = f" {row.scope_text}" if row.scope_text else ""
        parts.append(f"{name} — {price_text(row)}{scope}")
        conditions = tuple(text for text in common if text != row.scope_text)
        if conditions:
            parts.append(" ".join(text if text.endswith((".", "!", "?")) else text + "." for text in conditions))
        return

    if not show_service_in_each_row:
        assert rows[0].service_name is not None
        parts.append(f"**{rows[0].service_name}**")
    lines: list[str] = []
    for row, item in zip(rows, details):
        label = (
            f"{row.service_name} — {row.variant_label}" if row.variant_label else row.service_name
        ) if show_service_in_each_row else row.variant_label
        local = tuple(text for text in item if text != row.scope_text and text not in common)
        prefix = f"{label} — " if label else ""
        scope = f" {row.scope_text}" if row.scope_text else ""
        suffix = " · " + " ".join(text if text.endswith((".", "!", "?")) else text + "." for text in local) if local else ""
        lines.append(f"- {prefix}{price_text(row)}{scope}{suffix}")
    parts.append("\n".join(lines))
    conditions = tuple(text for text in common if not all(text == row.scope_text for row in rows))
    if conditions:
        parts.append(" ".join(text if text.endswith((".", "!", "?")) else text + "." for text in conditions))


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


def _render_d2_commercial_packages(plan: ResolvedResponsePlan) -> list[str]:
    parts: list[str] = []
    if plan.d2_price_booster_block is not None:
        parts.append(plan.d2_price_booster_block.body_text.strip())
    if plan.d2_also_list_block is not None:
        parts.append(plan.d2_also_list_block.body_text.strip())
    parts.extend(block.explanation_text.strip() for block in plan.d2_compatibility_blocks)
    return parts


def _render_amplifier_list(plan: ResolvedResponsePlan) -> list[str]:
    if not plan.automatic_amplifier_blocks:
        return []
    lines = [_AMPLIFIER_HEADER]
    lines.extend(f"- {block.display_text.strip()}" for block in plan.automatic_amplifier_blocks)
    return ["\n".join(lines)]


def _render_textual_cta(plan: ResolvedResponsePlan) -> list[str]:
    if plan.textual_cta_block is None:
        return []
    if plan.d2_price_block is not None and any(
        button.action_kind == "cta" for button in plan.ui_plan.buttons
    ):
        # The visible booking button already invites the visitor. Preserve
        # model prose and mandatory price caveats without adding another footer.
        return []
    return [plan.textual_cta_block.text.strip()]


def _join_parts(parts: list[str]) -> str:
    cleaned = [part for part in parts if part]
    if not cleaned:
        return ""
    return "\n\n".join(cleaned)
