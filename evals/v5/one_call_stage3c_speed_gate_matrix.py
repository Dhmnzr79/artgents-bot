"""Frozen Stage 3C speed-gate case matrix (resolver-aligned, SHA-256 pinned)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from evals.v5.one_call_stage3c_speed_gate_contract import (
    FROZEN_ALL_CASE_IDS,
    SpeedGateCaseSpec,
    SpeedGateQualitySpec,
)
from tests.one_call_stage2_fixture import case_by_id, load_stage2_cases


from tests.one_call_stage2_fixture import case_by_id, load_stage2_cases

_STAGE2_FIXTURE = (
    Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "one_call_stage2_cases.json"
)


def _stage2_raw(case_id: str) -> dict[str, object]:
    payload = json.loads(_STAGE2_FIXTURE.read_text(encoding="utf-8"))
    for row in payload.get("cases") or []:
        if str(row.get("case_id")) == case_id:
            return dict(row)
    raise KeyError(case_id)


def _quality_from_stage2(case_id: str, *, max_provider_calls: int) -> SpeedGateQualitySpec:
    row = case_by_id(case_id)
    raw = _stage2_raw(case_id)
    return SpeedGateQualitySpec(
        expected_route=row.expected_decision,
        required_all=row.required_all,
        required_any=row.required_any,
        forbidden_terms=row.forbidden_terms,
        forbidden_price_tokens=tuple(str(x) for x in raw.get("forbidden_price_tokens") or ()),
        max_provider_calls=max_provider_calls,
        execution_layer=row.execution_layer,
    )


def _build_frozen_cases() -> tuple[SpeedGateCaseSpec, ...]:
    m01 = case_by_id("m01")
    p03 = case_by_id("p03")
    p04 = case_by_id("p04")
    f01 = case_by_id("f01")
    cases: list[SpeedGateCaseSpec] = [
        SpeedGateCaseSpec(
            case_id="s01_microfact",
            user_message=m01.user_message,
            kind="latency",
            quality=_quality_from_stage2("m01", max_provider_calls=1),
            stage2_ref="m01",
            source_refs=tuple(
                str(ref)
                for ref in (
                    "clients/demo/clinic_policies.yaml",
                    "clients/demo/md/clinic__info__contacts.md",
                )
            ),
        ),
        SpeedGateCaseSpec(
            case_id="s02_service",
            user_message="Расскажите про имплантацию зубов",
            kind="latency",
            quality=SpeedGateQualitySpec(
                expected_route="answer",
                required_any=(("имплант",), ("лечени",)),
                max_provider_calls=1,
            ),
            source_refs=(
                "clients/demo/md/implantation__service__benefits.md",
                "clients/demo/md/implantation__service__classic.md",
            ),
        ),
        SpeedGateCaseSpec(
            case_id="s03_exact_price",
            user_message=p03.user_message,
            kind="latency",
            quality=_quality_from_stage2("p03", max_provider_calls=1),
            stage2_ref="p03",
            source_refs=tuple(
                str(ref)
                for ref in (
                    "clients/demo/target_response/pricebook/services/classic.one_tooth.implantium.json",
                    "clients/demo/target_response/pricebook/facts.json",
                )
            ),
        ),
        SpeedGateCaseSpec(
            case_id="s04_both_jaws",
            user_message=p04.user_message,
            kind="latency",
            quality=_quality_from_stage2("p04", max_provider_calls=1),
            stage2_ref="p04",
            source_refs=tuple(
                str(ref)
                for ref in (
                    "clients/demo/target_response/pricebook/services/all_on_4.jaw.implantium.json",
                )
            ),
        ),
        SpeedGateCaseSpec(
            case_id="s05_doctor_trust",
            user_message="Кто у вас делает имплантацию и какой у врачей опыт?",
            kind="latency",
            quality=SpeedGateQualitySpec(
                expected_route="answer",
                required_any=(("опыт", "стаж"), ("врач",), ("имплант",)),
                max_provider_calls=1,
            ),
            source_refs=(
                "clients/demo/doctor_catalog.json",
                "clients/demo/md/doctors__doctor__orlov.md",
                "clients/demo/md/implantation__service__benefits.md",
            ),
        ),
        SpeedGateCaseSpec(
            case_id="s06_pain_fear",
            user_message=f01.user_message,
            kind="latency",
            quality=_quality_from_stage2("f01", max_provider_calls=1),
            stage2_ref="f01",
            source_refs=tuple(
                str(ref)
                for ref in (
                    "clients/demo/md/implantation__faq__pain.md",
                    "clients/demo/target_response/pricebook/facts.json",
                )
            ),
        ),
    ]
    for admin_id in ("a01", "a02", "a03"):
        row = case_by_id(admin_id)
        cases.append(
            SpeedGateCaseSpec(
                case_id=admin_id,
                user_message=row.user_message,
                kind="admin",
                quality=_quality_from_stage2(admin_id, max_provider_calls=0),
                stage2_ref=admin_id,
            )
        )
    return tuple(cases)


FROZEN_SPEED_GATE_CASES: tuple[SpeedGateCaseSpec, ...] = _build_frozen_cases()


def case_by_matrix_id(case_id: str) -> SpeedGateCaseSpec:
    for case in FROZEN_SPEED_GATE_CASES:
        if case.case_id == case_id:
            return case
    raise KeyError(case_id)


def frozen_matrix_document() -> dict[str, object]:
    return {
        "schema": "one_call_stage3c_speed_gate_matrix_v1",
        "case_ids": list(FROZEN_ALL_CASE_IDS),
        "cases": [
            {
                "case_id": case.case_id,
                "user_message": case.user_message,
                "kind": case.kind,
                "stage2_ref": case.stage2_ref,
                "source_refs": list(case.source_refs),
                "quality": {
                    "expected_route": case.quality.expected_route,
                    "required_all": list(case.quality.required_all),
                    "required_any": [list(group) for group in case.quality.required_any],
                    "forbidden_terms": list(case.quality.forbidden_terms),
                    "forbidden_price_tokens": list(case.quality.forbidden_price_tokens),
                    "max_provider_calls": case.quality.max_provider_calls,
                    "execution_layer": case.quality.execution_layer,
                },
            }
            for case in FROZEN_SPEED_GATE_CASES
        ],
    }


def frozen_matrix_sha256() -> str:
    payload = json.dumps(
        frozen_matrix_document(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def assert_frozen_matrix_unchanged() -> None:
    expected_ids = set(FROZEN_ALL_CASE_IDS)
    actual_ids = {case.case_id for case in FROZEN_SPEED_GATE_CASES}
    if actual_ids != expected_ids:
        raise RuntimeError(f"matrix case id mismatch expected={sorted(expected_ids)} actual={sorted(actual_ids)}")
    stage2_ids = {row.case_id for row in load_stage2_cases()}
    for case in FROZEN_SPEED_GATE_CASES:
        if case.stage2_ref and case.stage2_ref not in stage2_ids:
            raise RuntimeError(f"missing stage2 ref {case.stage2_ref} for {case.case_id}")
