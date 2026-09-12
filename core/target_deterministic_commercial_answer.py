"""Deterministic verified answers for exact price and doctor evidence.

This is deliberately adjacent to the existing structured contact/availability
paths. It never selects records itself: canonical materialization has already
selected and validated the exact evidence blocks before this formatter runs.
"""

from __future__ import annotations

import json
from typing import Any

from contracts.response_schema import ResponseSchemaBundle
from core import turn_timing
from core.target_composer_request import TargetComposerRequest
from core.target_response_verifier import TargetVerifiedComposedResponse
from core.target_spec_offline_response_package import TargetSpecBoundOfflineResponsePackage


def _rubles(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " ₽"


def _years(value: int) -> str:
    last_two = value % 100
    last = value % 10
    if 11 <= last_two <= 14:
        word = "лет"
    elif last == 1:
        word = "год"
    elif 2 <= last <= 4:
        word = "года"
    else:
        word = "лет"
    return f"{value} {word}"


def _payloads(request: TargetComposerRequest, kinds: set[str]) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for block in request.evidence_blocks:
        if block.kind not in kinds:
            continue
        value = json.loads(block.text)
        if not isinstance(value, dict):
            raise ValueError("deterministic_evidence_not_object")
        values.append(value)
    return values


def _service_name(bundle: ResponseSchemaBundle, service_id: str | None) -> str:
    service = bundle.services.get(service_id or "")
    return str(service.name) if service is not None else str(service_id or "услуга")


def _brand_name(bundle: ResponseSchemaBundle, brand_id: str | None) -> str | None:
    if not brand_id:
        return None
    brand = bundle.brands.brands.get(brand_id)
    return str(brand.canonical_name) if brand is not None else None


def _price_text(bundle: ResponseSchemaBundle, request: TargetComposerRequest) -> str | None:
    rows = _payloads(request, {"offer"})
    if not rows:
        return None

    rendered: list[tuple[str, str, bool]] = []
    for row in rows:
        price = row.get("price")
        package = row.get("package")
        if not isinstance(price, dict) or not isinstance(package, dict):
            raise ValueError("deterministic_price_shape_invalid")
        mode = price.get("mode")
        if mode == "fixed":
            value = _rubles(int(price["amount"]))
        elif mode == "from":
            value = "от " + _rubles(int(price["min_amount"]))
        elif mode == "range":
            value = f"{_rubles(int(price['min_amount']))}–{_rubles(int(price['max_amount']))}"
        elif mode == "no_public_price":
            value = str(price["approved_text"]).strip()
        else:
            raise ValueError("deterministic_price_mode_invalid")

        service_id = str(row.get("service_id") or "").strip()
        label_parts = [_service_name(bundle, service_id)]
        brand_name = _brand_name(bundle, str(row.get("brand_id") or "").strip() or None)
        if brand_name:
            label_parts.append(brand_name)
        package_label = str(package.get("label") or "").strip()
        if package_label and mode != "no_public_price":
            value = f"{value} {package_label}"
        rendered.append((" · ".join(label_parts), value, mode == "no_public_price"))

    if len(rendered) == 1:
        label, value, no_public = rendered[0]
        if no_public:
            return value
        return f"Стоимость услуги «{label}» — {value}."
    lines = ["Вот актуальные варианты стоимости:"]
    lines.extend(f"- {label} — {value}" for label, value, _no_public in rendered)
    return "\n\n".join((lines[0], "\n".join(lines[1:])))


def _doctor_text(bundle: ResponseSchemaBundle, request: TargetComposerRequest) -> str | None:
    rows = _payloads(request, {"doctor", "external_doctor"})
    if not rows:
        return None
    service_name = (
        _service_name(bundle, request.spec.service_id)
        if request.spec.service_id
        else None
    )
    lead = (
        f"С услугой «{service_name}» работают:"
        if service_name
        else "В клинике принимают следующие специалисты:"
    )
    lines = []
    for row in rows:
        name = str(row.get("name") or "").strip()
        position = str(row.get("position") or "").strip()
        experience = int(row.get("experience_years"))
        if not name or not position or experience < 0:
            raise ValueError("deterministic_doctor_shape_invalid")
        lines.append(f"- {name} — {position}, стаж {_years(experience)}.")
    return f"{lead}\n\n" + "\n".join(lines)


def materialize_deterministic_commercial_answer(
    request: TargetComposerRequest,
    bound_package: TargetSpecBoundOfflineResponsePackage,
    bundle: ResponseSchemaBundle,
) -> TargetVerifiedComposedResponse | None:
    """Return a verified local answer only for exact price/doctors-only specs.

    Any unexpected evidence shape declines the optimization and lets the normal
    Composer/Verifier path handle the turn; a fast path must never create a new
    user-visible failure mode.
    """

    components = request.spec.required_components
    try:
        if components == ("price",):
            answer = _price_text(bundle, request)
            reason = "deterministic_exact_price"
        elif components == ("doctors",):
            answer = _doctor_text(bundle, request)
            reason = "deterministic_exact_doctors"
        else:
            return None
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    if not answer:
        return None

    turn_timing.stage_skipped("composer", reason=reason)
    turn_timing.stage_skipped("verifier_deterministic", reason=reason)
    turn_timing.stage_skipped("verifier_semantic", reason=reason)
    primary = bound_package.package.plan.primary_content_ref
    refs: list[str] = []
    if primary:
        refs.append(primary)
    for block in request.evidence_blocks:
        if block.kind == "content" and block.ref.startswith("content:"):
            refs.append(block.ref.removeprefix("content:"))
    used = tuple(dict.fromkeys(refs))
    return TargetVerifiedComposedResponse(
        text=answer,
        spec=request.spec,
        selected_followups=request.selected_followups,
        selected_cta_key=request.selected_cta_key,
        navigation_followups=bound_package.package.navigation_followups,
        primary_content_ref=primary,
        used_content_refs=used,
    )
