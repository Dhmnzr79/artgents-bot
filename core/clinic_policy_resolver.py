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
    understanding: RequestUnderstanding,
    subject_id: str | None,
) -> str | None:
    if subject_id is None:
        return None
    for subj in understanding.subjects:
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

    allowed_keys = _pack_policy_keys(client_id)
    decisions: list[ClinicPolicyRequestDecision] = []
    ledger: list[RequestLedgerEntry] = []
    suppress_booking = False
    active_booking: str | None = None

    for req in understanding.requests:
        if req.kind == "clinic_policy":
            if not req.policy_ids:
                ledger.append(
                    RequestLedgerEntry(
                        request_id=req.request_id,
                        kind=req.kind,
                        status="deferred",
                        subject_id=req.subject_id,
                    )
                )
                continue
            for policy_key in req.policy_ids:
                if policy_key not in allowed_keys:
                    decisions.append(
                        ClinicPolicyRequestDecision(
                            request_id=req.request_id,
                            policy_key=policy_key,
                            outcome="no_applicable_rule",
                            subject_id=req.subject_id,
                            reason_code="policy_not_in_pack",
                        )
                    )
                    continue
                decisions.append(
                    ClinicPolicyRequestDecision(
                        request_id=req.request_id,
                        policy_key=policy_key,
                        outcome="allowed_by_known_rules",
                        subject_id=req.subject_id,
                        reason_code="pack_policy",
                    )
                )
            ledger.append(
                RequestLedgerEntry(
                    request_id=req.request_id,
                    kind=req.kind,
                    status="answered",
                    subject_id=req.subject_id,
                )
            )
            continue

        if req.kind in {"price", "booking"}:
            age = _subject_age(understanding, req.subject_id)
            if age == "child" and "no_pediatric_dentistry" in allowed_keys:
                decisions.append(
                    ClinicPolicyRequestDecision(
                        request_id=req.request_id,
                        policy_key="no_pediatric_dentistry",
                        outcome="blocked",
                        subject_id=req.subject_id,
                        reason_code="child_patient_blocked",
                    )
                )
                ledger.append(
                    RequestLedgerEntry(
                        request_id=req.request_id,
                        kind=req.kind,
                        status="blocked",
                        subject_id=req.subject_id,
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
                    subject_id=req.subject_id,
                )
            )
            continue

        if req.kind == "contact":
            ledger.append(
                RequestLedgerEntry(
                    request_id=req.request_id,
                    kind=req.kind,
                    status="answered",
                    subject_id=req.subject_id,
                )
            )
            continue

        if req.kind in {"content", "other"}:
            ledger.append(
                RequestLedgerEntry(
                    request_id=req.request_id,
                    kind=req.kind,
                    status="answered" if req.content_text else "deferred",
                    subject_id=req.subject_id,
                )
            )
            continue

        ledger.append(
            RequestLedgerEntry(
                request_id=req.request_id,
                kind=req.kind,
                status="unsupported",
                subject_id=req.subject_id,
            )
        )

    return ClinicPolicyResolutionResult(
        decisions=tuple(decisions),
        ledger=tuple(ledger),
        suppress_forbidden_booking_cta=suppress_booking,
        active_booking_request_id=active_booking,
    )
