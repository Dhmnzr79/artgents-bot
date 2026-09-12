"""Hard offline quality gates for Stage 5.3 multiclient matrix."""

from __future__ import annotations

from typing import Any

from evals.v5.stage53.one_call_stage53_matrix import Stage53TurnSpec


def _normalize_price_text(text: str) -> str:
    return text.replace(" ", "").replace("\u00a0", "").lower()


def _contains_forbidden_term(term: str, answer: str) -> bool:
    token = term.strip().lower()
    if not token:
        return False
    return token in answer.lower()


def evaluate_turn_gates(
    answer: str,
    route: str,
    provider_calls: int,
    turn_spec: Stage53TurnSpec | dict[str, Any],
) -> dict[str, Any]:
    """Evaluate one matrix turn against hard gates."""

    if isinstance(turn_spec, Stage53TurnSpec):
        spec = turn_spec
        expected_calls = int(spec.provider_calls)
        required_all = spec.required_all
        required_any = spec.required_any
        forbidden = spec.forbidden
        forbidden_price_tokens = spec.forbidden_price_tokens
        envelope_route = spec.route
        service_route_contains = spec.service_route_contains
        diagnostic = spec.diagnostic
    else:
        spec = turn_spec
        expected_calls = int(spec.get("provider_calls", 0))
        required_all = tuple(str(x) for x in spec.get("required_all") or ())
        required_any = tuple(
            tuple(str(y) for y in group)
            for group in (spec.get("required_any") or ())
        )
        forbidden = tuple(str(x) for x in spec.get("forbidden") or ())
        forbidden_price_tokens = tuple(
            str(x) for x in spec.get("forbidden_price_tokens") or ()
        )
        envelope_route = str(spec["route"]) if spec.get("route") else None
        service_route_contains = (
            str(spec["service_route_contains"])
            if spec.get("service_route_contains")
            else None
        )
        diagnostic = spec.get("diagnostic")

    answer_lower = answer.lower()
    normalized_answer = _normalize_price_text(answer)
    failures: list[str] = []

    if provider_calls != expected_calls:
        failures.append(
            f"provider_calls_mismatch expected={expected_calls} actual={provider_calls}"
        )

    for token in required_all:
        if token.lower() not in answer_lower:
            failures.append(f"missing_required:{token}")

    for group in required_any:
        if not any(term.lower() in answer_lower for term in group):
            failures.append(f"missing_required_any:{','.join(group)}")

    for term in forbidden:
        if _contains_forbidden_term(term, answer):
            failures.append(f"forbidden_term:{term}")

    for price_token in forbidden_price_tokens:
        normalized_token = _normalize_price_text(price_token)
        if normalized_token and normalized_token in normalized_answer:
            failures.append(f"forbidden_price:{price_token}")

    if envelope_route:
        envelope_route_lower = envelope_route.strip().lower()
        if envelope_route_lower == "admin":
            if "admin" not in route.lower():
                failures.append(f"route_mismatch expected_admin actual={route}")
        elif envelope_route_lower == "answer":
            if "admin" in route.lower() and "sales_fast_admin" in route.lower():
                failures.append(f"route_mismatch unexpected_admin actual={route}")

    if service_route_contains:
        needle = service_route_contains.lower()
        if needle not in route.lower():
            failures.append(
                f"service_route_missing:{service_route_contains} actual={route}"
            )

    diagnostic_notes: dict[str, Any] = {}
    if diagnostic:
        diagnostic_notes = {
            "diagnostic_present": True,
            "overload_markers": _count_overload_markers(answer),
            "naturalness_manual": bool(diagnostic.get("naturalness_manual")),
        }

    return {
        "pass": not failures,
        "failures": failures,
        "provider_calls": provider_calls,
        "service_route": route,
        "diagnostic": diagnostic_notes if diagnostic else None,
    }


def _count_overload_markers(answer: str) -> int:
    """Heuristic unrelated-fact breadth for diagnostic cases only."""

    markers = (";", "—", "–", "\n")
    return sum(answer.count(marker) for marker in markers)
