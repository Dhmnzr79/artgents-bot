"""Pure clinic policy resolver from validated request_understanding (D1R)."""

from __future__ import annotations

from contracts.clinic_policy_resolution import (
    ClinicPolicyRequestDecision,
    ClinicPolicyResolutionResult,
    RequestLedgerEntry,
)
from contracts.request_understanding import RequestUnderstanding
from core.clinic_policies_loader import load_clinic_policies
from core.client_config_loader import resolve_pack_client_id


def _subject_age(
    subjects,
    subject_id: str | None,
) -> str | None:
    if subject_id is None:
        return None
    for subj in subjects:
        if subj.subject_id == subject_id:
            return subj.age_group
    return None


def _pack_policy_keys(client_id: str) -> frozenset[str]:
    pack = resolve_pack_client_id(client_id)
    bundle = load_clinic_policies(pack)
    if bundle is None:
        return frozenset()
    return frozenset(p.key for p in bundle.policies if p.answer.strip())


def resolve_clinic_policies(
    *,
    client_id: str,
    understanding: RequestUnderstanding,
) -> ClinicPolicyResolutionResult:
    """Map understanding requests to policy decisions without regex on user text."""

    return resolve_clinic_policy_operations(client_id=client_id,
        operations=understanding.requests, request_ages={r.request_id: _subject_age(understanding.subjects, r.subject_id) for r in understanding.requests})


def resolve_clinic_policy_operations(*, client_id, operations, request_ages=None):
    """Apply existing clinic rules to narrow operations, without model envelope."""
    allowed_keys = _pack_policy_keys(client_id)
    decisions: list[ClinicPolicyRequestDecision] = []
    ledger: list[RequestLedgerEntry] = []
    suppress_booking = False
    active_booking: str | None = None

    for req in operations:
        age = getattr(req, "age_group", "unknown") if request_ages is None else request_ages.get(req.request_id)
        if req.kind == "clinic_policy":
            inferred: list[str] = list(req.policy_ids)
            if req.payment_scheme_intent == "eligibility_question":
                payment_key = {"oms": "no_oms", "dms": "no_dms"}.get(req.payment_scheme)
                if payment_key and payment_key not in inferred:
                    inferred.append(payment_key)
            if (req.context != "past_history" and age == "child"
                    and "no_pediatric_dentistry" not in inferred):
                inferred.append("no_pediatric_dentistry")
            answered = False
            for policy_key in inferred:
                if policy_key not in allowed_keys:
                    decisions.append(
                        ClinicPolicyRequestDecision(
                            request_id=req.request_id,
                            policy_key=policy_key,
                            outcome="no_applicable_rule",
                            subject_id=getattr(req, "subject_id", None),
                            reason_code="policy_not_in_pack",
                        )
                    )
                    continue
                answered = True
                if policy_key == "no_pediatric_dentistry" and req.context != "past_history":
                    suppress_booking = True
                decisions.append(
                    ClinicPolicyRequestDecision(
                        request_id=req.request_id,
                        policy_key=policy_key,
                        outcome="allowed_by_known_rules",
                        subject_id=getattr(req, "subject_id", None),
                        reason_code="pack_policy",
                    )
                )
            if not inferred:
                decisions.append(ClinicPolicyRequestDecision(
                    request_id=req.request_id, policy_key=None,
                    outcome="no_applicable_rule", subject_id=getattr(req, "subject_id", None),
                    reason_code="policy_rule_absent",
                ))
            ledger.append(
                RequestLedgerEntry(
                    request_id=req.request_id,
                    kind=req.kind,
                    status="answered" if answered else "unsupported",
                    subject_id=getattr(req, "subject_id", None),
                )
            )
            continue

        if req.kind in {"price", "booking"}:
            if req.kind == "booking" and req.context == "past_history":
                decisions.append(ClinicPolicyRequestDecision(
                    request_id=req.request_id, policy_key=None,
                    outcome="needs_clarification", subject_id=getattr(req, "subject_id", None),
                    reason_code="booking_in_past_context",
                ))
                ledger.append(RequestLedgerEntry(
                    request_id=req.request_id, kind=req.kind,
                    status="clarification_needed", subject_id=getattr(req, "subject_id", None),
                ))
                continue
            blocked: list[tuple[str, str]] = []
            if req.context != "past_history" and age == "child" and "no_pediatric_dentistry" in allowed_keys:
                blocked.append(("no_pediatric_dentistry", "child_patient_blocked"))
            if req.payment_scheme_intent == "requested_payment":
                payment_key = {"oms": "no_oms", "dms": "no_dms"}.get(req.payment_scheme)
                if payment_key in allowed_keys:
                    blocked.append((payment_key, "requested_payment_unavailable"))
                elif payment_key is not None and not blocked:
                    decisions.append(ClinicPolicyRequestDecision(
                        request_id=req.request_id, policy_key=None,
                        outcome="needs_clarification", subject_id=getattr(req, "subject_id", None),
                        reason_code="payment_rule_absent",
                    ))
                    ledger.append(RequestLedgerEntry(
                        request_id=req.request_id, kind=req.kind,
                        status="clarification_needed", subject_id=getattr(req, "subject_id", None),
                    ))
                    continue
            if blocked:
                for block_key, reason in blocked:
                    decisions.append(
                    ClinicPolicyRequestDecision(
                        request_id=req.request_id,
                        policy_key=block_key,
                        outcome="blocked",
                        subject_id=getattr(req, "subject_id", None),
                        reason_code=reason,
                    ))
                ledger.append(
                    RequestLedgerEntry(
                        request_id=req.request_id,
                        kind=req.kind,
                        status="blocked",
                        subject_id=getattr(req, "subject_id", None),
                    )
                )
                suppress_booking = True
                continue
            if req.kind == "booking":
                active_booking = req.request_id
            ledger.append(
                RequestLedgerEntry(
                    request_id=req.request_id,
                    kind=req.kind,
                    status="deferred",
                    subject_id=getattr(req, "subject_id", None),
                )
            )
            continue

        if req.kind == "contact":
            ledger.append(
                RequestLedgerEntry(
                    request_id=req.request_id,
                    kind=req.kind,
                    status="answered",
                    subject_id=getattr(req, "subject_id", None),
                )
            )
            continue

        if req.kind in {"content", "other"}:
            ledger.append(
                RequestLedgerEntry(
                    request_id=req.request_id,
                    kind=req.kind,
                    status="answered" if req.content_text else "deferred",
                    subject_id=getattr(req, "subject_id", None),
                )
            )
            continue

        ledger.append(
            RequestLedgerEntry(
                request_id=req.request_id,
                kind=req.kind,
                status="unsupported",
                subject_id=getattr(req, "subject_id", None),
            )
        )

    return ClinicPolicyResolutionResult(
        decisions=tuple(decisions),
        ledger=tuple(ledger),
        suppress_forbidden_booking_cta=suppress_booking,
        active_booking_request_id=active_booking,
    )
