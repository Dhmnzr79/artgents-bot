"""Shared e2e / metadata-first smoke case validation (backward compatible)."""
from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass
from typing import Any

import yaml

import urllib.error
import urllib.request


try:
    from composer_parity import should_skip_legacy_retrieval_checks, validate_composer_parity
except ModuleNotFoundError:  # imported as evals.v5.smoke_case_runner (pytest from repo root)
    from evals.v5.composer_parity import (
        should_skip_legacy_retrieval_checks,
        validate_composer_parity,
    )


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    status: str  # PASS | FAIL | ERROR | SKIP
    reason: str
    coverage_class: str = "UNKNOWN"


def load_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if not isinstance(obj, dict):
        raise ValueError("root must be an object")
    return obj


def here(*parts: str) -> str:
    return os.path.join(os.path.dirname(__file__), *parts)


def norm(s: str) -> str:
    return (s or "").strip().lower()


def contains_ci(haystack: str, needle: str) -> bool:
    return norm(needle) in norm(haystack)


def doc_id_from_meta(meta: dict[str, Any]) -> str:
    if meta.get("doc_id"):
        return str(meta["doc_id"]).strip()
    f = str(meta.get("file") or "").strip()
    if f.endswith(".md"):
        return f[:-3]
    return f


def doc_type_from_doc_id(doc_id: str) -> str:
    """Heuristic aligned with METADATA_FIRST_V1 doc_type rules."""
    d = (doc_id or "").strip().lower()
    if not d:
        return ""
    if d == "clinic__info__contacts" or d.endswith("__contacts"):
        return "contacts"
    if d.startswith("comparison__"):
        return "comparison"
    if d.startswith("doctors__doctor__"):
        return "doctor"
    if "__pricing__" in d:
        return "pricing"
    if "__faq__" in d:
        return "faq"
    if "__service__" in d:
        return "service"
    if "__info__" in d:
        return "info"
    return ""


def packet_aspects(meta: dict[str, Any]) -> set[str]:
    packet = meta.get("answer_packet")
    if not isinstance(packet, dict):
        return set()
    cards = packet.get("cards")
    if not isinstance(cards, list):
        return set()
    out: set[str] = set()
    for card in cards:
        if not isinstance(card, dict):
            continue
        aspect = str(card.get("aspect") or "").strip()
        if aspect:
            out.add(norm(aspect))
    return out


def plan_aspects(meta: dict[str, Any]) -> set[str]:
    plan = meta.get("answer_plan")
    if not isinstance(plan, dict):
        return set()
    raw = plan.get("aspects")
    if not isinstance(raw, list):
        return set()
    return {norm(str(x)) for x in raw if str(x).strip()}


def packet_card_kinds(meta: dict[str, Any]) -> set[str]:
    packet = meta.get("answer_packet")
    if not isinstance(packet, dict):
        return set()
    cards = packet.get("cards")
    if not isinstance(cards, list):
        return set()
    out: set[str] = set()
    for card in cards:
        if not isinstance(card, dict):
            continue
        kind = str(card.get("kind") or "").strip()
        if kind:
            out.add(norm(kind))
    return out


def str_list_field(row: dict[str, Any], key: str) -> list[str]:
    raw = row.get(key)
    if not isinstance(raw, list) or not all(isinstance(x, str) for x in raw):
        return []
    return [str(x).strip() for x in raw if str(x).strip()]


def expand_cases(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Duplicate rows with `clients: [...]` into per-client runs."""
    out: list[dict[str, Any]] = []
    for row in cases:
        if not isinstance(row, dict):
            continue
        clients = row.get("clients")
        if isinstance(clients, list) and all(isinstance(x, str) for x in clients):
            base_id = str(row.get("id") or "").strip() or "case"
            for cid in clients:
                cid_s = str(cid).strip()
                if not cid_s:
                    continue
                copy = {k: v for k, v in row.items() if k != "clients"}
                copy["client_id"] = cid_s
                copy["id"] = f"{base_id}@{cid_s}"
                copy["_template_id"] = base_id
                out.append(copy)
        else:
            out.append(dict(row))
    return out


def infer_route_from_response(resp: dict[str, Any]) -> str:
    meta = resp.get("meta") or {}
    if not isinstance(meta, dict):
        meta = {}
    quick_replies = resp.get("quick_replies") or []

    svc = str(meta.get("service_route") or "").strip().lower()
    if svc:
        return svc

    orch = str(meta.get("orch_route") or "").strip().lower()
    if orch:
        return orch

    ingress_route = str(meta.get("ingress_route") or "").strip().lower()
    if ingress_route and ingress_route != "normal":
        return f"ingress_{ingress_route}"

    if bool(meta.get("handoff_filter")):
        return "handoff_filter"
    if bool(meta.get("lead_flow")) or bool(meta.get("booking_intent")):
        return "lead_flow"
    if bool(meta.get("low_score")):
        return "low_score_fallback"
    if str(meta.get("error") or "") == "rate_limited":
        return "rate_limited"

    intent = str(meta.get("intent") or "").strip().lower()
    if intent in {"price_lookup", "price_concern"}:
        return intent
    if intent == "offtopic":
        return "offtopic"
    if intent == "catalog_facts":
        return "catalog_facts"

    file = str(meta.get("file") or "").strip()
    if file == "clinic__info__contacts.md":
        return "contacts_chunk"
    if "__pricing__" in file:
        return "price_lookup"
    if file:
        return "retrieval_chunk"

    if isinstance(quick_replies, list) and len(quick_replies) > 0:
        return "guided"

    return ""


def _routing_provenance_dict(row: dict[str, Any], key: str) -> dict[str, Any]:
    raw = row.get(key)
    return raw if isinstance(raw, dict) else {}


# Baseline matrix: assert stable final route only (not flaky intermediate signals).
_STABLE_BASELINE_PROVENANCE_FIELDS: tuple[str, ...] = (
    "route_intent",
    "source",
    "answer_path",
    "orch_route",
)
_DIAGNOSTIC_PROVENANCE_FIELDS: frozenset[str] = frozenset({"turn_planner_used", "resolver_used"})


def extract_routing_provenance(resp: dict[str, Any]) -> dict[str, Any]:
    """Decision provenance from /ask meta (requires E2E_USE_TEST_CLIENT=1 for full slice)."""
    meta = resp.get("meta") if isinstance(resp.get("meta"), dict) else {}
    mf = meta.get("metadata_first") if isinstance(meta.get("metadata_first"), dict) else {}
    srd = mf.get("source_route_decision")
    if not isinstance(srd, dict):
        srd = (
            meta.get("source_route_decision")
            if isinstance(meta.get("source_route_decision"), dict)
            else {}
        )
    source = str(srd.get("source") or "").strip().lower()
    if not source:
        family = str(meta.get("ui_source_family") or "").strip().lower()
        if family == "trust":
            source = "trust"
    route_intent = str(mf.get("route_intent") or meta.get("intent") or "").strip().lower()
    return {
        "turn_planner_used": mf.get("turn_planner_used"),
        "route_intent": route_intent,
        "source": source,
        "answer_path": str(meta.get("answer_path") or "").strip().lower(),
        "orch_route": infer_route_from_response(resp),
    }


def _provenance_value_ok(*, field: str, got: Any, want: Any) -> bool:
    if want is None:
        return True
    if field == "turn_planner_used":
        return bool(got) == bool(want)
    got_s = norm(str(got or ""))
    if isinstance(want, list) and all(isinstance(x, str) for x in want):
        return got_s in {norm(str(x)) for x in want if str(x).strip()}
    return got_s == norm(str(want))


def _provenance_fields_to_check(spec: dict[str, Any], *, baseline: bool) -> list[str]:
    """Fields to assert. Baseline: stable route only; target: all except diagnostics."""
    if baseline:
        return [f for f in _STABLE_BASELINE_PROVENANCE_FIELDS if f in spec or f"{f}_any" in spec]
    return [
        f
        for f in spec
        if not f.endswith("_any") and f not in _DIAGNOSTIC_PROVENANCE_FIELDS
    ]


def validate_routing_provenance(
    *,
    row: dict[str, Any],
    provenance: dict[str, Any],
    baseline: bool = False,
) -> str | None:
    """Return fail reason or None.

    baseline=True (routing_matrix): assert stable ``current`` provenance (final route).
    ``turn_planner_used`` is diagnostic only — never pass/fail.
    baseline=False: assert ``target`` provenance (P1 gate); diagnostics also skipped.
    """
    spec = _routing_provenance_dict(row, "current" if baseline else "target")
    if not spec:
        return None

    for field in _provenance_fields_to_check(spec, baseline=baseline):
        want = spec.get(field)
        if want is None:
            continue
        got = provenance.get(field)
        if not _provenance_value_ok(field=field, got=got, want=want):
            label = "current" if baseline else "target"
            return f"provenance.{label}.{field}: got={got!r} want={want!r}"

    for field in ("route_intent", "source", "answer_path", "orch_route"):
        if baseline and field not in _STABLE_BASELINE_PROVENANCE_FIELDS:
            continue
        want_any = spec.get(f"{field}_any")
        if isinstance(want_any, list) and all(isinstance(x, str) for x in want_any):
            got = provenance.get(field)
            if norm(str(got or "")) not in {norm(str(x)) for x in want_any if str(x).strip()}:
                label = "current" if baseline else "target"
                return f"provenance.{label}.{field}: got={got!r} want_any={want_any!r}"

    if baseline:
        return None

    forbidden = _routing_provenance_dict(row, "target_forbidden")
    for field, forbidden_vals in forbidden.items():
        if not isinstance(forbidden_vals, list):
            continue
        got = provenance.get(field)
        if norm(str(got or "")) in {norm(str(x)) for x in forbidden_vals if str(x).strip()}:
            return f"provenance_forbidden.{field}: got={got!r} forbidden={forbidden_vals!r}"

    return None


def validate_smoke_case(
    *,
    row: dict[str, Any],
    resp: dict[str, Any],
    answer: str,
    route: str,
    routing_matrix: bool = False,
) -> CaseResult | None:
    """
    Return CaseResult on FAIL/SKIP, or None if all checks pass.
    """
    case_id = str(row.get("id") or "").strip()
    cov = str(row.get("coverage_class") or row.get("testability") or "UNKNOWN").strip().upper()

    if row.get("skip"):
        return CaseResult(case_id=case_id, status="SKIP", reason="marked skip", coverage_class=cov)

    provenance = extract_routing_provenance(resp)
    prov_reason = validate_routing_provenance(
        row=row, provenance=provenance, baseline=routing_matrix
    )
    if prov_reason:
        return CaseResult(
            case_id=case_id,
            status="FAIL",
            reason=prov_reason,
            coverage_class=cov,
        )

    if row.get("aspect_planner_llm_required"):
        if not (os.getenv("ASPECT_PLANNER_LLM_ON") or "").strip().lower() in {
            "1",
            "true",
            "yes",
        }:
            return CaseResult(
                case_id=case_id,
                status="SKIP",
                reason="aspect_planner_llm_required (set ASPECT_PLANNER_LLM_ON=1)",
                coverage_class=cov,
            )

    expected_route = row.get("expected_route")
    if expected_route is not None:
        expected_route = str(expected_route).strip()
    expected_route_any = row.get("expected_route_any")
    if expected_route_any is not None:
        if isinstance(expected_route_any, list) and all(isinstance(x, str) for x in expected_route_any):
            expected_route_any = [str(x).strip() for x in expected_route_any if str(x).strip()]
        else:
            expected_route_any = None

    meta = resp.get("meta") if isinstance(resp.get("meta"), dict) else {}
    skip_legacy_doc = should_skip_legacy_retrieval_checks(meta=meta, row=row)

    # Route asserts describe legacy retrieval paths; on the composer path the
    # route is validated via composer_parity (expected_answer_path).
    if not skip_legacy_doc:
        if expected_route_any:
            if norm(route) not in {norm(x) for x in expected_route_any}:
                return CaseResult(
                    case_id=case_id,
                    status="FAIL",
                    reason=f"route: got={route!r} want_any={expected_route_any!r}",
                    coverage_class=cov,
                )
        elif expected_route and norm(route) != norm(expected_route):
            return CaseResult(
                case_id=case_id,
                status="FAIL",
                reason=f"route: got={route!r} want={expected_route!r}",
                coverage_class=cov,
            )

    forbidden_routes = str_list_field(row, "forbidden_routes")
    if forbidden_routes and norm(route) in {norm(x) for x in forbidden_routes}:
        return CaseResult(
            case_id=case_id,
            status="FAIL",
            reason=f"forbidden route: got={route!r} forbidden={forbidden_routes!r}",
            coverage_class=cov,
        )

    parity_reason = validate_composer_parity(row=row, answer=answer, meta=meta)
    if parity_reason:
        return CaseResult(
            case_id=case_id,
            status="FAIL",
            reason=parity_reason,
            coverage_class=cov,
        )
    got_doc_id = doc_id_from_meta(meta)
    got_doc_type = doc_type_from_doc_id(got_doc_id)

    expected_doc_id = row.get("expected_doc_id")
    if not skip_legacy_doc and expected_doc_id is not None:
        want = str(expected_doc_id).strip()
        if want and norm(got_doc_id) != norm(want):
            return CaseResult(
                case_id=case_id,
                status="FAIL",
                reason=f"doc_id: got={got_doc_id!r} want={want!r}",
                coverage_class=cov,
            )

    expected_doc_id_any = str_list_field(row, "expected_doc_id_any")
    if (
        not skip_legacy_doc
        and expected_doc_id_any
        and norm(got_doc_id) not in {norm(x) for x in expected_doc_id_any}
    ):
        return CaseResult(
            case_id=case_id,
            status="FAIL",
            reason=f"doc_id: got={got_doc_id!r} want_any={expected_doc_id_any!r}",
            coverage_class=cov,
        )

    got_service_id = str(meta.get("matched_service_id") or meta.get("service_id") or "").strip()
    expected_service_id = row.get("expected_service_id")
    if expected_service_id is not None:
        want_svc = str(expected_service_id).strip()
        if want_svc and norm(got_service_id) != norm(want_svc):
            return CaseResult(
                case_id=case_id,
                status="FAIL",
                reason=f"service_id: got={got_service_id!r} want={want_svc!r}",
                coverage_class=cov,
            )

    expected_service_id_any = str_list_field(row, "expected_service_id_any")
    if expected_service_id_any and norm(got_service_id) not in {norm(x) for x in expected_service_id_any}:
        return CaseResult(
            case_id=case_id,
            status="FAIL",
            reason=f"service_id: got={got_service_id!r} want_any={expected_service_id_any!r}",
            coverage_class=cov,
        )

    forbidden_service_id = str_list_field(row, "forbidden_service_id")
    if forbidden_service_id and got_service_id and norm(got_service_id) in {norm(x) for x in forbidden_service_id}:
        return CaseResult(
            case_id=case_id,
            status="FAIL",
            reason=f"forbidden_service_id hit: {got_service_id!r}",
            coverage_class=cov,
        )

    expected_pricebook_group_id = row.get("expected_pricebook_group_id")
    if expected_pricebook_group_id is not None:
        want_gid = str(expected_pricebook_group_id).strip()
        got_gid = str(meta.get("pricebook_group_id") or "").strip()
        if want_gid and norm(got_gid) != norm(want_gid):
            return CaseResult(
                case_id=case_id,
                status="FAIL",
                reason=f"pricebook_group_id: got={got_gid!r} want={want_gid!r}",
                coverage_class=cov,
            )

    expected_price_status = row.get("expected_price_status")
    if expected_price_status is not None:
        want_ps = str(expected_price_status).strip()
        got_ps = str(meta.get("price_status") or "").strip()
        if want_ps and norm(got_ps) != norm(want_ps):
            return CaseResult(
                case_id=case_id,
                status="FAIL",
                reason=f"price_status: got={got_ps!r} want={want_ps!r}",
                coverage_class=cov,
            )

    forbidden_doc_id = str_list_field(row, "forbidden_doc_id")
    if (
        not skip_legacy_doc
        and forbidden_doc_id
        and norm(got_doc_id) in {norm(x) for x in forbidden_doc_id}
    ):
        return CaseResult(
            case_id=case_id,
            status="FAIL",
            reason=f"forbidden_doc_id hit: {got_doc_id!r}",
            coverage_class=cov,
        )

    forbidden_doc_type = str_list_field(row, "forbidden_doc_type")
    if (
        not skip_legacy_doc
        and forbidden_doc_type
        and got_doc_type
        and norm(got_doc_type) in {norm(x) for x in forbidden_doc_type}
    ):
        return CaseResult(
            case_id=case_id,
            status="FAIL",
            reason=f"forbidden_doc_type hit: {got_doc_type!r}",
            coverage_class=cov,
        )

    # Phase 2+: only when test hook exposes metadata_first telemetry on response meta
    if row.get("expected_fallback_used") is not None:
        mf = meta.get("metadata_first")
        if not isinstance(mf, dict):
            return CaseResult(
                case_id=case_id,
                status="SKIP",
                reason="expected_fallback_used requires meta.metadata_first (test hook)",
                coverage_class=cov,
            )
        want_fb = bool(row.get("expected_fallback_used"))
        got_fb = bool(mf.get("fallback_used"))
        if got_fb != want_fb:
            return CaseResult(
                case_id=case_id,
                status="FAIL",
                reason=f"fallback_used: got={got_fb} want={want_fb}",
                coverage_class=cov,
            )

    if not skip_legacy_doc and row.get("expected_doc_type") is not None:
        want_dt = str(row.get("expected_doc_type") or "").strip().lower()
        mf = meta.get("metadata_first")
        if isinstance(mf, dict) and str(mf.get("selected_doc_type") or "").strip():
            got_dt = str(mf.get("selected_doc_type") or "").strip().lower()
        else:
            got_dt = norm(got_doc_type)
        if want_dt and got_dt != want_dt:
            return CaseResult(
                case_id=case_id,
                status="FAIL",
                reason=f"doc_type: got={got_dt!r} want={want_dt!r}",
                coverage_class=cov,
            )

    must_contain = str_list_field(row, "must_contain")
    missing = [x for x in must_contain if x and not contains_ci(answer, x)]
    if missing:
        return CaseResult(
            case_id=case_id,
            status="FAIL",
            reason=f"must_contain_missing: {missing[:3]}",
            coverage_class=cov,
        )

    answer_signals_any = str_list_field(row, "answer_signals_any")
    if answer_signals_any and not any(contains_ci(answer, x) for x in answer_signals_any):
        return CaseResult(
            case_id=case_id,
            status="FAIL",
            reason=f"answer_signals_any: none of {answer_signals_any[:4]!r}",
            coverage_class=cov,
        )

    answer_signals_all = str_list_field(row, "answer_signals_all")
    missing_all = [x for x in answer_signals_all if x and not contains_ci(answer, x)]
    if missing_all:
        return CaseResult(
            case_id=case_id,
            status="FAIL",
            reason=f"answer_signals_all missing: {missing_all[:4]!r}",
            coverage_class=cov,
        )

    must_match_any_regex = str_list_field(row, "must_match_any_regex")
    if must_match_any_regex:
        if not any(re.search(pat, answer, re.IGNORECASE) for pat in must_match_any_regex):
            return CaseResult(
                case_id=case_id,
                status="FAIL",
                reason=f"must_match_any_regex: no match in {must_match_any_regex[:2]!r}",
                coverage_class=cov,
            )

    must_not_contain = str_list_field(row, "must_not_contain") + str_list_field(row, "forbidden_signals")
    forbidden_hit = [x for x in must_not_contain if x and contains_ci(answer, x)]
    if forbidden_hit:
        return CaseResult(
            case_id=case_id,
            status="FAIL",
            reason=f"must_not_contain_hit: {forbidden_hit[:3]}",
            coverage_class=cov,
        )

    expected_plan_aspects = str_list_field(row, "expected_plan_aspects")
    if expected_plan_aspects:
        got_aspects = plan_aspects(meta)
        missing_aspects = [x for x in expected_plan_aspects if norm(x) not in got_aspects]
        if missing_aspects:
            return CaseResult(
                case_id=case_id,
                status="FAIL",
                reason=f"expected_plan_aspects missing: {missing_aspects!r} got={sorted(got_aspects)!r}",
                coverage_class=cov,
            )

    expected_packet_aspects = str_list_field(row, "expected_packet_aspects")
    if expected_packet_aspects:
        got_packet_aspects = packet_aspects(meta)
        missing_packet = [x for x in expected_packet_aspects if norm(x) not in got_packet_aspects]
        if missing_packet:
            return CaseResult(
                case_id=case_id,
                status="FAIL",
                reason=(
                    f"expected_packet_aspects missing: {missing_packet!r} "
                    f"got={sorted(got_packet_aspects)!r}"
                ),
                coverage_class=cov,
            )

    expected_packet_card_kinds = str_list_field(row, "expected_packet_card_kinds")
    if expected_packet_card_kinds:
        got_kinds = packet_card_kinds(meta)
        missing_kinds = [x for x in expected_packet_card_kinds if norm(x) not in got_kinds]
        if missing_kinds:
            return CaseResult(
                case_id=case_id,
                status="FAIL",
                reason=f"expected_packet_card_kinds missing: {missing_kinds!r} got={sorted(got_kinds)!r}",
                coverage_class=cov,
            )

    if row.get("require_answer_packet") is True:
        packet = meta.get("answer_packet")
        if not isinstance(packet, dict) or not isinstance(packet.get("cards"), list):
            return CaseResult(
                case_id=case_id,
                status="FAIL",
                reason="require_answer_packet: meta.answer_packet.cards missing",
                coverage_class=cov,
            )

    forbidden_packet_card_kinds = str_list_field(row, "forbidden_packet_card_kinds")
    if forbidden_packet_card_kinds:
        got_kinds = packet_card_kinds(meta)
        hit = [x for x in forbidden_packet_card_kinds if norm(x) in got_kinds]
        if hit:
            return CaseResult(
                case_id=case_id,
                status="FAIL",
                reason=f"forbidden_packet_card_kinds hit: {hit!r}",
                coverage_class=cov,
            )

    expected_fb = row.get("expected_fallback_reason")
    if expected_fb is not None:
        got_fb = str(meta.get("fallback_reason") or "").strip()
        if norm(got_fb) != norm(str(expected_fb)):
            return CaseResult(
                case_id=case_id,
                status="FAIL",
                reason=f"fallback_reason: got={got_fb!r} want={expected_fb!r}",
                coverage_class=cov,
            )

    expected_price_unit = row.get("expected_price_unit")
    if expected_price_unit is not None:
        got_unit = str(meta.get("price_offer_unit") or "").strip().lower()
        want_unit = str(expected_price_unit).strip().lower()
        if want_unit and got_unit != want_unit:
            jaw_hint = "318 000" in answer or "368 000" in answer
            tooth_hint = "76 200" in answer or "85 200" in answer
            unit_ok = (want_unit == "jaw" and jaw_hint and "76 200" not in answer) or (
                want_unit == "one_tooth" and tooth_hint and "318 000" not in answer
            )
            if not unit_ok:
                return CaseResult(
                    case_id=case_id,
                    status="FAIL",
                    reason=f"price_offer_unit: meta={got_unit!r} want={want_unit!r}",
                    coverage_class=cov,
                )

    expected_brands = str_list_field(row, "expected_price_offer_brands")
    if expected_brands:
        missing_brands = [b for b in expected_brands if b and not contains_ci(answer, b.split()[0])]
        if missing_brands:
            return CaseResult(
                case_id=case_id,
                status="FAIL",
                reason=f"expected_price_offer_brands missing: {missing_brands[:3]!r}",
                coverage_class=cov,
            )

    forbidden_brands = str_list_field(row, "forbidden_price_offer_brands")
    if forbidden_brands:
        hit_br = [b for b in forbidden_brands if b and contains_ci(answer, b.split()[0])]
        if hit_br:
            return CaseResult(
                case_id=case_id,
                status="FAIL",
                reason=f"forbidden_price_offer_brands hit: {hit_br!r}",
                coverage_class=cov,
            )

    if row.get("expected_price_offers_applied") is True:
        if not meta.get("price_offers_applied"):
            return CaseResult(
                case_id=case_id,
                status="FAIL",
                reason="expected price_offers_applied in meta but missing",
                coverage_class=cov,
            )

    expected_offer_ids = str_list_field(row, "expected_price_offer_ids")
    if expected_offer_ids:
        got_ids_raw = meta.get("price_offer_ids")
        got_ids = got_ids_raw if isinstance(got_ids_raw, list) else []
        got_norm = {norm(str(x)) for x in got_ids if str(x).strip()}
        missing_ids = [x for x in expected_offer_ids if norm(x) not in got_norm]
        if missing_ids:
            return CaseResult(
                case_id=case_id,
                status="FAIL",
                reason=f"expected_price_offer_ids missing: {missing_ids!r} got={got_ids!r}",
                coverage_class=cov,
            )

    pres_reason = validate_preservation_contract(row=row, resp=resp, answer=answer, route=route)
    if pres_reason:
        return CaseResult(
            case_id=case_id,
            status="FAIL",
            reason=pres_reason,
            coverage_class=cov,
        )

    return None


_PROTECTED_UI_CONTRACT_KEYS: frozenset[str] = frozenset(
    {
        "note",
        "composer_must_not_substitute_contacts_boundary",
        "followup_source",
        "source_doc_id",
        "turn_scope",
        "source_catalog_refs_ordered",
        "source_catalog_labels_ordered",
        "expected_visible_followup_refs_ordered",
        "expected_visible_followup_labels_ordered",
        "expected_video_key",
        "surface",
        "pricebook_source",
        "expected_unit",
        "allowed_optional_amounts",
        "required_amounts",
        "forbidden_amounts",
        "expected_price_followup_actions_ordered",
    }
)

_MARKETING_CONTRACT_KEYS: frozenset[str] = frozenset(
    {
        "promo_overlay_required",
        "core_answer_independent_of_promo",
        "blocked_promo_aspect_source",
        "blocked_promo_aspect",
        "core_must_pass_without_promo_cards",
        "must_not_block_on_promo_absence",
        "verification_scope",
        "expected_promo_absent",
        "core_answer_required",
    }
)

_KNOWN_TURN_SCOPES: frozenset[str] = frozenset({"fresh_session_first_turn"})
_KNOWN_FOLLOWUP_SOURCES: frozenset[str] = frozenset({"suggest_h3"})
_KNOWN_VERIFICATION_SCOPES: frozenset[str] = frozenset({"natural_absence_only"})
_KNOWN_UI_SURFACES: frozenset[str] = frozenset({"meta.followups", "quick_replies"})


def _contract_unknown_keys(contract: dict[str, Any], allowed: frozenset[str]) -> list[str]:
    return sorted(k for k in contract if k not in allowed)


def _doc_id_from_ref(ref: str) -> str:
    r = (ref or "").strip()
    if not r:
        return ""
    base = r.split("#", 1)[0].strip()
    if base.endswith(".md"):
        base = base[:-3]
    return base


def _int_list_field(obj: dict[str, Any], key: str) -> list[int]:
    raw = obj.get(key)
    if not isinstance(raw, list):
        return []
    out: list[int] = []
    for x in raw:
        try:
            out.append(int(x))
        except (TypeError, ValueError):
            continue
    return out


def _ordered_str_lists_equal(got: list[str], want: list[str]) -> bool:
    if len(got) != len(want):
        return False
    return all(str(a) == str(b) for a, b in zip(got, want))


def _followup_items(resp: dict[str, Any], *, surface: str) -> list[dict[str, str]]:
    if surface == "quick_replies":
        raw = resp.get("quick_replies") or []
    elif surface == "meta.followups":
        meta = resp.get("meta") if isinstance(resp.get("meta"), dict) else {}
        raw = meta.get("followups") or []
    else:
        return []
    out: list[dict[str, str]] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        ref = str(item.get("ref") or "").strip()
        if label and ref:
            out.append({"label": label, "ref": ref})
    return out


def extract_evidence_source_doc_id(resp: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return (doc_id, provenance_field) from explicit response telemetry only."""
    meta = resp.get("meta") if isinstance(resp.get("meta"), dict) else {}
    mf = meta.get("metadata_first") if isinstance(meta.get("metadata_first"), dict) else {}

    packet = meta.get("answer_packet")
    if isinstance(packet, dict):
        for card in packet.get("cards") or []:
            if not isinstance(card, dict) or str(card.get("kind") or "") != "content":
                continue
            ref = str(card.get("source_ref") or "").strip()
            doc_id = _doc_id_from_ref(ref)
            if doc_id:
                return doc_id, "answer_packet.cards.source_ref"

    gen = meta.get("generator_input") if isinstance(meta.get("generator_input"), dict) else {}
    gen_doc = str(gen.get("doc_id") or "").strip()
    if gen_doc:
        return gen_doc, "generator_input.doc_id"

    sel = str(mf.get("selected_doc_id") or "").strip()
    if sel:
        return sel, "metadata_first.selected_doc_id"

    doc_id = str(meta.get("doc_id") or "").strip()
    if not doc_id:
        f = str(meta.get("file") or "").strip()
        if f.endswith(".md"):
            doc_id = f[:-3]
    answer_path = str(meta.get("answer_path") or "").strip().lower()
    if doc_id and answer_path in {"composer", "single_source", "contacts"}:
        return doc_id, "meta.doc_id"

    srd = mf.get("source_route_decision")
    if isinstance(srd, dict):
        ref = str(srd.get("ref") or "").strip()
        doc_id = _doc_id_from_ref(ref)
        if doc_id:
            return doc_id, "metadata_first.source_route_decision.ref"

    return None, None


def _build_source_catalog_from_doc(
    *,
    client_id: str,
    source_doc_id: str,
    followup_source: str,
) -> tuple[tuple[list[str], list[str]] | None, str | None]:
    if followup_source not in _KNOWN_FOLLOWUP_SOURCES:
        return None, f"unsupported followup_source: {followup_source!r}"
    doc_name = f"{source_doc_id.strip()}.md"
    ensure_repo_on_path()
    from meta_loader import get_doc_meta
    from ux_builder import heading_label

    meta = get_doc_meta(doc_name, client_id=client_id)
    if not meta:
        return None, f"source doc not found: {doc_name!r}"
    suggest = meta.get("suggest_h3") or []
    if not isinstance(suggest, list):
        return None, f"suggest_h3 missing in {doc_name!r}"
    refs: list[str] = []
    labels: list[str] = []
    for raw in suggest:
        h_id = raw if isinstance(raw, str) else (raw.get("h3_id") or raw.get("id"))
        h_id_s = str(h_id or "").strip()
        if not h_id_s:
            continue
        refs.append(f"{doc_name}#{h_id_s}")
        labels.append(heading_label(doc_name, h_id_s, client_id=client_id))
    return (refs, labels), None


def _parse_yaml_anchor_ref(ref: str) -> tuple[str, str]:
    raw = (ref or "").strip()
    if "#" not in raw:
        return raw, ""
    path, anchor = raw.split("#", 1)
    return path.strip(), anchor.strip()


def _promo_present_in_response(resp: dict[str, Any]) -> bool:
    meta = resp.get("meta") if isinstance(resp.get("meta"), dict) else {}
    packet = meta.get("answer_packet")
    if isinstance(packet, dict):
        for card in packet.get("cards") or []:
            if isinstance(card, dict) and str(card.get("kind") or "") == "promo":
                return True
        for dec in packet.get("promo_decisions") or []:
            if isinstance(dec, dict) and bool(dec.get("allowed")):
                return True
    applied = meta.get("marketing_promos_applied")
    if isinstance(applied, list) and applied:
        return True
    return False


def _core_answer_blocked(resp: dict[str, Any], answer: str) -> bool:
    if not str(answer or "").strip():
        return True
    meta = resp.get("meta") if isinstance(resp.get("meta"), dict) else {}
    if bool(meta.get("low_score")):
        return True
    if str(meta.get("error") or "").strip():
        return True
    fb = str(meta.get("fallback_reason") or "").strip().lower()
    if fb in {
        "ask_failed",
        "retrieval_no_candidates",
        "low_score_fallback",
        "price_not_in_catalog",
    }:
        return True
    return False


def _load_pricebook_service(rel_path: str) -> dict[str, Any]:
    root = ensure_repo_on_path()
    path = os.path.join(root, rel_path.replace("/", os.sep))
    with open(path, encoding="utf-8") as f:
        obj = json.load(f)
    if not isinstance(obj, dict):
        raise ValueError("pricebook service must be an object")
    return obj


def _pricebook_variant_totals(pb: dict[str, Any]) -> set[int]:
    totals: set[int] = set()
    variants = pb.get("variants")
    if not isinstance(variants, list):
        return totals
    for variant in variants:
        if not isinstance(variant, dict):
            continue
        try:
            totals.add(int(variant.get("total")))
        except (TypeError, ValueError):
            continue
    return totals


def _price_unit_amount_hint_ok(*, want_unit: str, answer: str) -> bool:
    """Amount-only fallback for protected_ui.expected_unit (smoke parity, no prose hints)."""
    jaw_hint = "318 000" in answer or "368 000" in answer
    tooth_hint = "76 200" in answer or "85 200" in answer
    if want_unit == "jaw":
        return jaw_hint and "76 200" not in answer
    if want_unit == "one_tooth":
        return tooth_hint and "318 000" not in answer
    return False


def _validate_pricebook_amounts(
    *,
    ui: dict[str, Any],
    pb: dict[str, Any],
    answer: str,
) -> str | None:
    try:
        from composer_parity import amount_in_text
    except ModuleNotFoundError:
        from evals.v5.composer_parity import amount_in_text

    pb_totals = _pricebook_variant_totals(pb)
    required = set(_int_list_field(ui, "required_amounts"))
    optional = set(_int_list_field(ui, "allowed_optional_amounts"))
    forbidden = set(_int_list_field(ui, "forbidden_amounts"))
    declared_allowed = required | optional

    for amt in declared_allowed:
        if amt not in pb_totals:
            return f"protected_ui.amount_not_in_pricebook: {amt}"

    for req in sorted(required):
        if not amount_in_text(req, answer):
            return f"protected_ui.required_amount missing: {req}"

    for forb in sorted(forbidden):
        if amount_in_text(forb, answer):
            return f"protected_ui.forbidden_amount present: {forb}"

    for total in sorted(pb_totals):
        if total in forbidden:
            continue
        if amount_in_text(total, answer) and total not in declared_allowed:
            return f"protected_ui.undeclared_pricebook_total: {total}"

    return None


def validate_price_followup_contract(
    *,
    expected_actions: list[dict[str, Any]],
    pb_followups: list[dict[str, Any]],
    quick_replies: list[dict[str, str]],
) -> str | None:
    if len(quick_replies) != len(expected_actions):
        return (
            f"protected_ui.price_quick_reply_count: got={len(quick_replies)} "
            f"want={len(expected_actions)}"
        )
    if len(pb_followups) < len(expected_actions):
        return (
            f"protected_ui.price_followup_source_count: got={len(pb_followups)} "
            f"want={len(expected_actions)}"
        )

    for idx, exp in enumerate(expected_actions):
        if not isinstance(exp, dict):
            return f"protected_ui.price_followup[{idx}]: expected object"
        label = str(exp.get("label") or "").strip()
        ref = str(exp.get("ref") or "").strip()
        action = str(exp.get("action") or "").strip()
        aspect = str(exp.get("aspect") or "").strip()

        pb_fu = pb_followups[idx]
        if not isinstance(pb_fu, dict):
            return f"protected_ui.price_followup_source[{idx}]: missing PriceBook entry"
        pb_label = str(pb_fu.get("label") or "").strip()
        pb_action = str(pb_fu.get("action") or "").strip()
        pb_aspect = str(pb_fu.get("aspect") or "").strip()
        if pb_label != label:
            return (
                f"protected_ui.price_followup_source[{idx}].label: "
                f"got={pb_label!r} want={label!r}"
            )
        if pb_action != action:
            return (
                f"protected_ui.price_followup_source[{idx}].action: "
                f"got={pb_action!r} want={action!r}"
            )
        if pb_aspect != aspect:
            return (
                f"protected_ui.price_followup_source[{idx}].aspect: "
                f"got={pb_aspect!r} want={aspect!r}"
            )

        if quick_replies[idx]["label"] != label:
            return (
                f"protected_ui.price_quick_reply[{idx}].label: "
                f"got={quick_replies[idx]['label']!r} want={label!r}"
            )
        if quick_replies[idx]["ref"] != ref:
            return (
                f"protected_ui.price_quick_reply[{idx}].ref: "
                f"got={quick_replies[idx]['ref']!r} want={ref!r}"
            )

    return None


def validate_preservation_contract(
    *,
    row: dict[str, Any],
    resp: dict[str, Any],
    answer: str,
    route: str,
) -> str | None:
    """Universal A0 preservation contract checks (spec-driven, no per-case ids)."""
    meta = resp.get("meta") if isinstance(resp.get("meta"), dict) else {}
    client_id = str(row.get("client_id") or meta.get("client_id") or "demo").strip()

    expected_evidence = row.get("expected_evidence_source_doc_id")
    if expected_evidence is not None:
        want = str(expected_evidence).strip()
        got, prov = extract_evidence_source_doc_id(resp)
        if not got:
            return (
                "evidence_source: provenance missing in response "
                "(need answer_packet.cards.source_ref, generator_input.doc_id, "
                "metadata_first.selected_doc_id, meta.doc_id, or source_route_decision.ref)"
            )
        if norm(got) != norm(want):
            return f"evidence_source: got={got!r} via {prov!r} want={want!r}"

    ui = row.get("protected_ui_contract")
    if isinstance(ui, dict) and ui:
        unknown = _contract_unknown_keys(ui, _PROTECTED_UI_CONTRACT_KEYS)
        if unknown:
            return f"protected_ui_contract unknown fields: {unknown!r}"

        if ui.get("composer_must_not_substitute_contacts_boundary") is True:
            ap = str(meta.get("answer_path") or "").strip().lower()
            if ap == "composer":
                return "protected_ui.contacts_boundary: composer substituted contacts route"

        followup_source = ui.get("followup_source")
        source_doc_id = ui.get("source_doc_id")
        if followup_source is not None and str(followup_source).strip() not in _KNOWN_FOLLOWUP_SOURCES:
            return f"protected_ui.followup_source unsupported: {followup_source!r}"

        turn_scope = ui.get("turn_scope")
        if turn_scope is not None and str(turn_scope).strip() not in _KNOWN_TURN_SCOPES:
            return f"protected_ui.turn_scope unsupported: {turn_scope!r}"

        if source_doc_id and followup_source:
            catalog, err = _build_source_catalog_from_doc(
                client_id=client_id,
                source_doc_id=str(source_doc_id).strip(),
                followup_source=str(followup_source).strip(),
            )
            if err:
                return f"protected_ui.source_catalog: {err}"
            assert catalog is not None
            refs, labels = catalog
            want_refs = str_list_field(ui, "source_catalog_refs_ordered")
            want_labels = str_list_field(ui, "source_catalog_labels_ordered")
            if want_refs and not _ordered_str_lists_equal(refs, want_refs):
                return f"protected_ui.source_catalog_refs: got={refs!r} want={want_refs!r}"
            if want_labels and not _ordered_str_lists_equal(labels, want_labels):
                return f"protected_ui.source_catalog_labels: got={labels!r} want={want_labels!r}"

        surface = str(ui.get("surface") or "meta.followups").strip()
        if ui.get("expected_visible_followup_refs_ordered") or ui.get("expected_visible_followup_labels_ordered"):
            if surface not in _KNOWN_UI_SURFACES:
                return f"protected_ui.surface unsupported: {surface!r}"
            visible = _followup_items(resp, surface=surface)
            got_refs = [x["ref"] for x in visible]
            got_labels = [x["label"] for x in visible]
            want_refs = str_list_field(ui, "expected_visible_followup_refs_ordered")
            want_labels = str_list_field(ui, "expected_visible_followup_labels_ordered")
            if want_refs and not _ordered_str_lists_equal(got_refs, want_refs):
                return f"protected_ui.visible_followup_refs: got={got_refs!r} want={want_refs!r}"
            if want_labels and not _ordered_str_lists_equal(got_labels, want_labels):
                return f"protected_ui.visible_followup_labels: got={got_labels!r} want={want_labels!r}"

        if ui.get("expected_video_key") is not None:
            want_vk = str(ui.get("expected_video_key") or "").strip()
            video = resp.get("video") if isinstance(resp.get("video"), dict) else {}
            got_vk = str(video.get("key") or "").strip()
            if want_vk and got_vk != want_vk:
                return f"protected_ui.video_key: got={got_vk!r} want={want_vk!r}"

        if ui.get("pricebook_source"):
            pb_path = str(ui.get("pricebook_source") or "").strip()
            try:
                pb = _load_pricebook_service(pb_path)
            except OSError as e:
                return f"protected_ui.pricebook_source unreadable: {pb_path!r} ({e})"
            want_unit = str(ui.get("expected_unit") or "").strip().lower()
            if want_unit:
                got_unit = str(meta.get("price_offer_unit") or "").strip().lower()
                unit_ok = bool(got_unit) and got_unit == want_unit
                if not unit_ok:
                    unit_ok = _price_unit_amount_hint_ok(want_unit=want_unit, answer=answer)
                if not unit_ok:
                    return f"protected_ui.expected_unit: got={got_unit!r} want={want_unit!r}"

            amount_reason = _validate_pricebook_amounts(ui=ui, pb=pb, answer=answer)
            if amount_reason:
                return amount_reason

            expected_actions = ui.get("expected_price_followup_actions_ordered")
            if isinstance(expected_actions, list) and expected_actions:
                quick = _followup_items(resp, surface="quick_replies")
                pb_followups = pb.get("followups") or []
                if not isinstance(pb_followups, list):
                    pb_followups = []
                followup_reason = validate_price_followup_contract(
                    expected_actions=expected_actions,
                    pb_followups=pb_followups,
                    quick_replies=quick,
                )
                if followup_reason:
                    return followup_reason

    marketing = row.get("marketing_contract")
    if isinstance(marketing, dict) and marketing:
        unknown = _contract_unknown_keys(marketing, _MARKETING_CONTRACT_KEYS)
        if unknown:
            return f"marketing_contract unknown fields: {unknown!r}"

        if marketing.get("verification_scope") is not None:
            vs = str(marketing.get("verification_scope") or "").strip()
            if vs not in _KNOWN_VERIFICATION_SCOPES:
                return f"marketing.verification_scope unsupported: {vs!r}"

        aspect_source = str(marketing.get("blocked_promo_aspect_source") or "").strip()
        blocked_aspect = str(marketing.get("blocked_promo_aspect") or "").strip()
        if aspect_source and blocked_aspect:
            rel_path, anchor = _parse_yaml_anchor_ref(aspect_source)
            root = ensure_repo_on_path()
            yaml_path = os.path.join(root, rel_path.replace("/", os.sep))
            try:
                with open(yaml_path, encoding="utf-8") as f:
                    yaml_obj = yaml.safe_load(f) or {}
            except OSError as e:
                return f"marketing.blocked_promo_aspect_source unreadable: {aspect_source!r} ({e})"
            if not isinstance(yaml_obj, dict):
                return f"marketing.blocked_promo_aspect_source invalid yaml: {aspect_source!r}"
            key = anchor or "blocked_aspects_for_promo"
            aspects_raw = yaml_obj.get(key)
            if not isinstance(aspects_raw, list):
                return f"marketing.blocked_promo_aspect_source missing anchor {key!r}"
            aspects = {norm(str(x)) for x in aspects_raw if str(x).strip()}
            if norm(blocked_aspect) not in aspects:
                return (
                    f"marketing.blocked_promo_aspect: {blocked_aspect!r} "
                    f"not listed in {aspect_source!r}"
                )

        if marketing.get("promo_overlay_required") is not False and marketing.get("promo_overlay_required") is not None:
            if bool(marketing.get("promo_overlay_required")):
                return "marketing.promo_overlay_required=true is not supported in A0 harness"

        promo_absent = marketing.get("expected_promo_absent")
        if promo_absent is True and _promo_present_in_response(resp):
            return "marketing.expected_promo_absent: promo card/decision present"

        if marketing.get("core_answer_required") is True and _core_answer_blocked(resp, answer):
            return "marketing.core_answer_required: empty or fallback-blocking answer"

        if marketing.get("core_must_pass_without_promo_cards") is True:
            if _promo_present_in_response(resp):
                return "marketing.core_must_pass_without_promo_cards: promo cards present"
            if _core_answer_blocked(resp, answer):
                return "marketing.core_must_pass_without_promo_cards: core answer blocked"

        if marketing.get("must_not_block_on_promo_absence") is True:
            if not _promo_present_in_response(resp) and _core_answer_blocked(resp, answer):
                return "marketing.must_not_block_on_promo_absence: answer blocked without promo"

        if marketing.get("core_answer_independent_of_promo") is True:
            if _core_answer_blocked(resp, answer):
                return "marketing.core_answer_independent_of_promo: core answer blocked"

    return None


def uses_test_client() -> bool:
    return (os.getenv("E2E_USE_TEST_CLIENT") or "").strip().lower() in {"1", "true", "yes"}


def ensure_repo_on_path() -> str:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    return repo_root


def reset_smoke_session(sid: str) -> None:
    ensure_repo_on_path()
    from session import mem_reset

    mem_reset(sid)


def apply_session_seed(sid: str, seed: dict[str, Any]) -> None:
    ensure_repo_on_path()
    from session import set_pending_lead_offer

    if seed.get("pending_lead_offer"):
        set_pending_lead_offer(sid, True)


def http_post_json(url: str, payload: dict[str, Any], timeout_sec: float) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    out = json.loads(raw)
    if not isinstance(out, dict):
        raise ValueError("response is not a JSON object")
    return out


def parse_sse_ui_payload(body: str) -> dict[str, Any]:
    """Parse final ``ui`` event JSON from /ask/stream SSE body (last ui wins)."""
    event_name: str | None = None
    last_ui: dict[str, Any] | None = None
    for line in (body or "").splitlines():
        if line.startswith("event: "):
            event_name = line[7:].strip()
        elif line.startswith("data: ") and event_name == "ui":
            raw = json.loads(line[6:])
            if not isinstance(raw, dict):
                raise ValueError("ui payload is not a JSON object")
            last_ui = raw
    if last_ui is None:
        raise ValueError("no ui event in SSE body")
    return last_ui


def ask_stream_url(bot_url: str) -> str:
    u = (bot_url or "").strip().rstrip("/")
    if u.endswith("/ask"):
        return f"{u}/stream"
    return f"{u}/ask/stream"


def post_ask_stream(bot_url: str, payload: dict[str, Any], timeout_sec: float) -> dict[str, Any]:
    """POST /ask/stream and return full payload from the ``ui`` SSE event."""
    if uses_test_client():
        ensure_repo_on_path()
        from app import app

        _ = bot_url
        _ = timeout_sec
        client = app.test_client()
        resp = client.post("/ask/stream", json=payload)
        return parse_sse_ui_payload(resp.get_data(as_text=True))

    url = ask_stream_url(bot_url)
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return parse_sse_ui_payload(raw)


def post_ask_json(bot_url: str, payload: dict[str, Any], timeout_sec: float) -> dict[str, Any]:
    if uses_test_client():
        ensure_repo_on_path()
        from app import app

        _ = bot_url
        _ = timeout_sec
        client = app.test_client()
        resp = client.post("/ask", json=payload)
        out = resp.get_json()
        if not isinstance(out, dict):
            raise ValueError("response is not a JSON object")
        return out
    return http_post_json(bot_url, payload, timeout_sec=timeout_sec)


def debug_fail_must_contain(
    *,
    case_id: str,
    route: str,
    must_contain: list[str],
    missing: list[str],
    answer: str,
    resp: dict[str, Any],
) -> None:
    print("\n--- SMOKE_DEBUG_FAIL (must_contain) ---", flush=True)
    print(f"case_id: {case_id!r}", flush=True)
    print(f"route: {route!r}", flush=True)
    print(f"must_contain (declared): {must_contain!r}", flush=True)
    print(f"missing needles repr: {[repr(x) for x in missing]}", flush=True)
    print(f"answer[:300] repr: {answer[:300]!r}", flush=True)
    meta = resp.get("meta")
    if isinstance(meta, dict) and meta.get("file"):
        print(f"meta.file: {meta.get('file')!r}", flush=True)
    print("--- end SMOKE_DEBUG_FAIL ---\n", flush=True)


def print_table(rows: list[CaseResult]) -> None:
    w_id = max(10, max((len(r.case_id) for r in rows), default=10))
    w_status = 6
    w_reason = max(20, min(80, max((len(r.reason) for r in rows), default=20)))

    def line(a: str, b: str, c: str) -> str:
        return f"| {a:<{w_id}} | {b:<{w_status}} | {c:<{w_reason}} |"

    sep = f"+-{'-' * w_id}-+-{'-' * w_status}-+-{'-' * w_reason}-+"
    print(sep)
    print(line("id", "status", "reason (если fail)"))
    print(sep)
    for r in rows:
        print(line(r.case_id, r.status, r.reason[:w_reason]))
    print(sep)


def print_coverage_summary(results: list[CaseResult]) -> None:
    classes = ["STRONG", "MEDIUM", "WEAK", "TEMPLATE", "UNKNOWN"]
    by_tot = {c: 0 for c in classes}
    by_ok = {c: 0 for c in classes}
    for r in results:
        cc = r.coverage_class if r.coverage_class in by_tot else "UNKNOWN"
        by_tot[cc] = by_tot.get(cc, 0) + 1
        if r.status == "PASS":
            by_ok[cc] = by_ok.get(cc, 0) + 1
    print("+--------------+---------+---------+")
    print("| class        | passed  | total   |")
    print("+--------------+---------+---------+")
    for c in classes:
        if by_tot[c]:
            print(f"| {c:<12} | {by_ok[c]:>7} | {by_tot[c]:>7} |")
    print("+--------------+---------+---------")


def run_smoke_suite(
    *,
    spec_path: str,
    bot_url: str,
    timeout_sec: float,
    client_filter: str | None,
    filter_ids: set[str] | None,
    expand_multiclient: bool = True,
) -> int:
    spec = load_json(spec_path)
    baseline = spec.get("baseline")
    cases = spec.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("cases must be a non-empty array")
    if baseline is not None and not isinstance(baseline, int):
        raise ValueError("baseline must be null or int")
    known_raw = spec.get("known_failures")
    known_fail_ids: set[str] = set()
    if isinstance(known_raw, list):
        known_fail_ids = {str(x).strip() for x in known_raw if str(x).strip()}
    routing_matrix = bool(spec.get("routing_matrix"))
    pipeline_contract = spec.get("pipeline_contract")
    use_stream = (
        isinstance(pipeline_contract, dict)
        and str(pipeline_contract.get("endpoint") or "").strip() == "/ask/stream"
    )

    if expand_multiclient:
        cases = expand_cases([r for r in cases if isinstance(r, dict)])

    if filter_ids is not None:
        cases = [r for r in cases if str(r.get("id") or "").strip() in filter_ids]
        if not cases:
            raise ValueError(f"no cases match filter {sorted(filter_ids)!r}")

    default_client = (os.getenv("CLIENT_ID") or "demo").strip().lower()
    if client_filter is not None:
        cases = [
            r
            for r in cases
            if str(r.get("client_id") or default_client).strip().lower() == client_filter
        ]
        if not cases:
            raise ValueError(f"no cases for client {client_filter!r}")

    results: list[CaseResult] = []
    passed = failed = errors = skipped = 0
    ts = int(time.time())
    run_tag = uuid.uuid4().hex[:8]

    for row in cases:
        case_id = str(row.get("id") or "").strip() or f"case_{uuid.uuid4().hex[:8]}"
        history = row.get("history") or []
        question = str(row.get("question") or "")
        client_id = str(row.get("client_id") or "").strip() or os.getenv("CLIENT_ID") or "demo"
        cov = str(row.get("coverage_class") or row.get("testability") or "UNKNOWN").strip().upper()

        sid = f"smoke_{case_id}_{ts}_{run_tag}"
        if uses_test_client():
            reset_smoke_session(sid)

        ui_contract = row.get("protected_ui_contract")
        if isinstance(ui_contract, dict) and str(ui_contract.get("turn_scope") or "").strip() == "fresh_session_first_turn":
            sid = f"smoke_{case_id}_{ts}_{run_tag}_fresh"
            if uses_test_client():
                reset_smoke_session(sid)

        if isinstance(history, list):
            for h in history:
                if isinstance(h, dict) and str(h.get("question") or "").strip():
                    try:
                        post_ask_json(
                            bot_url,
                            {"q": str(h.get("question")), "sid": sid, "client_id": client_id},
                            timeout_sec,
                        )
                    except Exception:
                        pass

        session_seed = row.get("session_seed")
        if isinstance(session_seed, dict) and session_seed:
            if not uses_test_client():
                errors += 1
                results.append(
                    CaseResult(
                        case_id=case_id,
                        status="ERROR",
                        reason="session_seed requires E2E_USE_TEST_CLIENT=1",
                        coverage_class=cov,
                    )
                )
                continue
            apply_session_seed(sid, session_seed)

        try:
            ask_payload = {"q": question, "sid": sid, "client_id": client_id}
            if use_stream:
                resp = post_ask_stream(bot_url, ask_payload, timeout_sec)
            else:
                resp = post_ask_json(bot_url, ask_payload, timeout_sec)
        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            errors += 1
            results.append(
                CaseResult(case_id=case_id, status="ERROR", reason=f"http_error: {e!s}"[:120], coverage_class=cov)
            )
            continue
        except Exception as e:
            errors += 1
            results.append(
                CaseResult(
                    case_id=case_id, status="ERROR", reason=f"request_failed: {e!s}"[:120], coverage_class=cov
                )
            )
            continue

        answer = str(resp.get("answer") or "")
        route = infer_route_from_response(resp)
        fail = validate_smoke_case(
            row=row, resp=resp, answer=answer, route=route, routing_matrix=routing_matrix
        )
        if fail is not None:
            if fail.status == "SKIP":
                skipped += 1
            elif case_id in known_fail_ids and fail.status == "FAIL":
                skipped += 1
                results.append(
                    CaseResult(
                        case_id=case_id,
                        status="SKIP",
                        reason=f"known_failure: {fail.reason}",
                        coverage_class=cov,
                    )
                )
                continue
            else:
                if "must_contain_missing" in fail.reason:
                    debug_fail_must_contain(
                        case_id=case_id,
                        route=route,
                        must_contain=str_list_field(row, "must_contain"),
                        missing=str_list_field(row, "must_contain"),
                        answer=answer,
                        resp=resp,
                    )
                failed += 1
            results.append(fail)
            continue

        passed += 1
        results.append(CaseResult(case_id=case_id, status="PASS", reason="ok", coverage_class=cov))

    print_table(results)
    total = passed + failed + errors + skipped
    acc = (passed / total) if total else 0.0
    print(
        f"SUMMARY: passed={passed}, failed={failed}, errors={errors}, skipped={skipped}, "
        f"total={total} (accuracy={acc:.1%})"
    )
    print()
    print_coverage_summary(results)

    if filter_ids is not None:
        return 0 if errors == 0 and failed == 0 else (2 if errors > 0 else 1)
    if routing_matrix:
        return 0 if errors == 0 and failed == 0 else (2 if errors > 0 else 1)
    if baseline is None:
        return 0 if errors == 0 else 2
    min_ok = max(0, int(baseline) - 2)
    return 0 if passed >= min_ok else 1
