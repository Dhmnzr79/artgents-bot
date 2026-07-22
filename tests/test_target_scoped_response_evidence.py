from __future__ import annotations

import ast
import inspect
import re
from dataclasses import FrozenInstanceError, fields, replace
from datetime import date
from pathlib import Path

import pytest

from contracts.doctor_schema import TargetDoctorCatalog
from contracts.response_schema import ResponseSchemaBundle, TargetStrategyMatch
from contracts.response_schema_refs import ResponseSchemaExternalIndex
from contracts.service_consultation import ServiceConsultationValue
from contracts.target_response_policy import TargetResponsePolicyRequest
from core.target_response_policy import build_target_response_spec
from core.target_response_followup_materializer import TargetContentFollowup
from core.target_response_followup_policy import TargetResponseFollowupSelection
from core.target_scoped_response_evidence import (
    TargetEvidenceScopeRecord,
    TargetScopedResponseEvidence,
    TargetScopedResponseEvidenceError,
    build_target_scoped_response_evidence,
)
from core.target_spec_offline_response_package import (
    assemble_target_spec_offline_response_package,
)


TODAY = date(2026, 7, 22)


def _write_md(
    root: Path,
    name: str,
    *,
    topic: str,
    suggest: bool = False,
) -> None:
    suggestions = "suggest_h3:\n  - details\n" if suggest else ""
    (root / name).write_text(
        "---\n"
        f"doc_id: {name.removesuffix('.md')}\n"
        "doc_type: service\n"
        f"topic: {topic}\n"
        "subtopic: overview\n"
        f"{suggestions}"
        "---\n\n"
        "## Overview\n\n"
        "### Details {#details}\nExact source text.\n"
        "### Profile {#profile}\nExact profile text.\n"
        "### One {#one}\nExact external text.\n",
        encoding="utf-8",
    )


@pytest.fixture
def md_root(tmp_path: Path) -> Path:
    _write_md(tmp_path, "service_one.md", topic="implantation", suggest=True)
    _write_md(tmp_path, "doctor_one.md", topic="doctors")
    _write_md(tmp_path, "clinic.md", topic="clinic")
    return tmp_path


def _fact(fact_id: str) -> dict[str, object]:
    return {
        "id": fact_id,
        "kind": "commercial",
        "text_fact": f"Exact {fact_id}.",
        "render_mode": "strict",
        "active": True,
        "allowed_service_ids": ["service_one"],
        "incompatible_with": [],
    }


def _bundle(*, with_offer: bool = True) -> ResponseSchemaBundle:
    offers: list[dict[str, object]] = []
    if with_offer:
        offers.append(
            {
                "offer_id": "offer_one",
                "service_id": "service_one",
                "active": True,
                "price": {
                    "mode": "fixed",
                    "amount": 100000,
                    "currency": "RUB",
                    "billing_unit": "jaw",
                },
                "package": {"label": "Exact package", "includes": ["Item"]},
                "fact_refs": ["selected_fact", "candidate_fact"],
                "followups": [
                    {"id": "includes", "label": "Includes", "action": "price"}
                ],
            }
        )
    return ResponseSchemaBundle.model_validate(
        {
            "services": {
                "service_one": {
                    "name": "Service One",
                    "aliases": [],
                    "family": "implantology",
                    "roles": ["protocol"],
                    "active": True,
                    "content_ref": "service_one.md",
                    "selection": {"mode": "direct"},
                    "options": [],
                }
            },
            "brands": {"version": 1, "brands": {}},
            "offers": offers,
            "facts": {
                "selected_fact": _fact("selected_fact"),
                "candidate_fact": _fact("candidate_fact"),
            },
            "strategy": {"version": 1, "default_max_options": 3, "rules": []},
            "marketing": {
                "version": 1,
                "limits": {
                    "max_marketing_facts_per_turn": 3,
                    "max_amplifiers_per_turn": 2,
                    "max_scenarios_per_turn": 2,
                },
                "initial_commercial_blocks": {
                    "service": {"ordered_fact_refs": ["fact:selected_fact"]}
                },
                "scenario_rules": {
                    "cost": {
                        "ordered_amplifier_refs": ["kb:clinic.md#one"],
                        "allowed_semantic_contexts": ["service"],
                    },
                    "doctor_trust": {
                        "ordered_amplifier_refs": ["doctor:doctor_one"],
                        "allowed_semantic_contexts": ["service"],
                    },
                },
                "cta_contexts": {"service": "plan", "default": "callback"},
            },
        }
    )


def _doctors() -> TargetDoctorCatalog:
    return TargetDoctorCatalog.model_validate(
        {
            "doctors": {
                "doctor_one": {
                    "name": "Doctor One",
                    "position": "Implantologist",
                    "experience_years": 15,
                    "service_ids": ["service_one"],
                    "profile_ref": "kb:doctor_one.md#profile",
                }
            }
        }
    )


def _spec(
    components: tuple[str, ...] = ("content",),
    *,
    mode: str = "answer",
    allowed: tuple[str, ...] = ("implantation",),
    forbidden: tuple[str, ...] = ("diagnosis",),
    required_facts: tuple[str, ...] = (),
    marketing: bool = False,
    consultation: bool = False,
    cta: bool = False,
):
    primary = "content" if "content" in components and "price" in components else None
    request = TargetResponsePolicyRequest.model_validate(
        {
            "response_mode": mode,
            "service_id": "service_one",
            "tone_key": "commercial_warm",
            "allowed_topics": allowed,
            "forbidden_topics": forbidden,
            "required_fact_ids": required_facts,
            "requested_components": components,
            "primary_component": primary,
            "allow_marketing_facts": marketing,
            "allow_consultation_close": consultation,
            "allow_cta": cta,
        }
    )
    return build_target_response_spec(request)


def _bound(
    md_root: Path,
    *,
    spec=None,
    bundle: ResponseSchemaBundle | None = None,
    initial: bool = False,
    close: bool = False,
    cta: bool = False,
    scenarios: tuple[str, ...] = (),
):
    if spec is None:
        spec = _spec()
    if bundle is None:
        bundle = _bundle()
    return assemble_target_spec_offline_response_package(
        bundle,
        _doctors(),
        ResponseSchemaExternalIndex(
            kb_refs=("kb:clinic.md#one",),
            doctor_refs=("doctor:doctor_one",),
        ),
        (
            ServiceConsultationValue(
                content_ref="service_one.md",
                value="Exact consultation value.",
            ),
        ),
        spec=spec,
        brand_term=None,
        strategy_context=TargetStrategyMatch(family="implantology"),
        semantic_context="service",
        today=TODAY,
        md_root=md_root,
        include_initial_block=initial,
        include_consultation_close=close,
        include_cta=cta,
        marketing_scenarios=scenarios,
    )


def test_exact_shapes_signature_error_surface_and_frozen_slots(md_root: Path) -> None:
    bound = _bound(md_root)
    result = build_target_scoped_response_evidence(bound, md_root=md_root)

    assert [field.name for field in fields(TargetEvidenceScopeRecord)] == [
        "ref",
        "topics",
        "fact_ids",
    ]
    assert [field.name for field in fields(TargetScopedResponseEvidence)] == [
        "spec",
        "service_id",
        "primary_content_ref",
        "offer_ids",
        "doctor_ids",
        "commercial_fact_ids",
        "external_source_refs",
        "consultation_content_ref",
        "selected_followups",
        "selected_cta_key",
        "scope_records",
        "covered_fact_ids",
    ]
    assert list(inspect.signature(build_target_scoped_response_evidence).parameters) == [
        "bound_package",
        "md_root",
    ]
    with pytest.raises(FrozenInstanceError):
        result.service_id = "changed"  # type: ignore[misc]
    assert not hasattr(result, "__dict__")

    source = Path("core/target_scoped_response_evidence.py").read_text(
        encoding="utf-8"
    )
    assert set(re.findall(r'"(scoped_evidence_[a-z_]+)"', source)) == {
        "scoped_evidence_package_invalid",
        "scoped_evidence_md_root_invalid",
        "scoped_evidence_package_inconsistent",
        "scoped_evidence_component_unfulfilled",
        "scoped_evidence_source_invalid",
        "scoped_evidence_topic_forbidden",
        "scoped_evidence_topic_not_allowed",
        "scoped_evidence_required_fact_missing",
    }


def test_closed_view_contains_only_selected_plan_identities(md_root: Path) -> None:
    spec = _spec(
        ("content", "price", "doctors"),
        allowed=("implantation", "doctors"),
        required_facts=("selected_fact",),
        marketing=True,
        consultation=True,
        cta=True,
    )
    bound = _bound(md_root, spec=spec, initial=True, close=True, cta=True)
    result = build_target_scoped_response_evidence(bound, md_root=md_root)

    assert result.spec is spec
    assert result.primary_content_ref == "service_one.md"
    assert result.offer_ids == ("offer_one",)
    assert result.doctor_ids == ("doctor_one",)
    assert result.commercial_fact_ids == ("selected_fact",)
    assert result.consultation_content_ref == "service_one.md"
    assert result.selected_followups is bound.package.selected_followups
    assert result.selected_cta_key == "plan"
    assert [record.ref for record in result.scope_records] == [
        "content:service_one.md",
        "offer:offer_one",
        "doctor:doctor_one",
        "fact:selected_fact",
        "consultation:service_one.md",
    ]
    assert result.scope_records[2].topics == ("implantation", "doctors")
    assert result.covered_fact_ids == ("selected_fact",)
    assert not hasattr(result, "package")
    assert "candidate_fact" not in result.commercial_fact_ids


def test_candidate_materials_and_candidate_cta_do_not_leak(md_root: Path) -> None:
    bound = _bound(md_root, spec=_spec(("content",)), cta=False)
    assert bound.package.materials.offers
    assert bound.package.materials.doctors
    assert bound.package.plan.cta_key == "plan"

    result = build_target_scoped_response_evidence(bound, md_root=md_root)

    assert result.offer_ids == ()
    assert result.doctor_ids == ()
    assert result.commercial_fact_ids == ()
    assert result.selected_cta_key is None
    assert [record.ref for record in result.scope_records] == [
        "content:service_one.md"
    ]


@pytest.mark.parametrize(
    "plan_changes",
    [
        {"offer_ids": ("offer_one",)},
        {"primary_content_ref": "clinic.md"},
    ],
)
def test_candidate_or_primary_identity_injection_fails_exact_plan_equality(
    md_root: Path,
    plan_changes: dict[str, object],
) -> None:
    bound = _bound(md_root, spec=_spec(("content",)))
    injected_plan = replace(bound.package.plan, **plan_changes)
    injected = replace(bound, package=replace(bound.package, plan=injected_plan))

    with pytest.raises(TargetScopedResponseEvidenceError) as exc_info:
        build_target_scoped_response_evidence(injected, md_root=md_root)
    assert exc_info.value.code == "scoped_evidence_package_inconsistent"
    assert exc_info.value.value == "plan"


def test_fabricated_followup_fails_exact_s30_selection_equality(md_root: Path) -> None:
    bound = _bound(md_root, spec=_spec(("content",)))
    fabricated = TargetResponseFollowupSelection(
        source="content",
        content=(
            TargetContentFollowup(
                id="fabricated",
                label="Fabricated label",
                ref="service_one.md#fabricated",
                source_content_ref="service_one.md",
            ),
        ),
        price=(),
    )
    injected = replace(
        bound,
        package=replace(bound.package, selected_followups=fabricated),
    )

    with pytest.raises(TargetScopedResponseEvidenceError) as exc_info:
        build_target_scoped_response_evidence(injected, md_root=md_root)
    assert exc_info.value.code == "scoped_evidence_package_inconsistent"
    assert exc_info.value.value == "selected_followups"


def test_service_and_doctor_topics_apply_allowed_and_forbidden_scope(
    md_root: Path,
) -> None:
    accepted = _bound(
        md_root,
        spec=_spec(("doctors",), allowed=("implantation",)),
    )
    result = build_target_scoped_response_evidence(accepted, md_root=md_root)
    assert result.scope_records[0].topics == ("implantation", "doctors")

    forbidden = _bound(
        md_root,
        spec=_spec(
            ("doctors",),
            allowed=("implantation",),
            forbidden=("doctors",),
        ),
    )
    with pytest.raises(TargetScopedResponseEvidenceError) as exc_info:
        build_target_scoped_response_evidence(forbidden, md_root=md_root)
    assert exc_info.value.code == "scoped_evidence_topic_forbidden"
    assert exc_info.value.value == ("doctor:doctor_one", ("doctors",))

    unrelated = _bound(
        md_root,
        spec=_spec(("content",), allowed=("clinic",)),
    )
    with pytest.raises(TargetScopedResponseEvidenceError) as exc_info:
        build_target_scoped_response_evidence(unrelated, md_root=md_root)
    assert exc_info.value.code == "scoped_evidence_topic_not_allowed"
    assert exc_info.value.value == (
        "content:service_one.md",
        ("implantation",),
    )


def test_external_kb_uses_own_topic_and_external_doctor_preserves_both(
    md_root: Path,
) -> None:
    kb_bound = _bound(
        md_root,
        spec=_spec(
            ("content",),
            allowed=("implantation", "clinic"),
            marketing=True,
        ),
        scenarios=("cost",),
    )
    kb_result = build_target_scoped_response_evidence(kb_bound, md_root=md_root)
    assert kb_result.external_source_refs == ("kb:clinic.md#one",)
    assert kb_result.scope_records[-1] == TargetEvidenceScopeRecord(
        ref="kb:clinic.md#one",
        topics=("clinic",),
        fact_ids=(),
    )

    blocked = _bound(
        md_root,
        spec=_spec(("content",), allowed=("implantation",), marketing=True),
        scenarios=("cost",),
    )
    with pytest.raises(TargetScopedResponseEvidenceError) as exc_info:
        build_target_scoped_response_evidence(blocked, md_root=md_root)
    assert exc_info.value.code == "scoped_evidence_topic_not_allowed"
    assert exc_info.value.value == ("kb:clinic.md#one", ("clinic",))

    doctor_bound = _bound(
        md_root,
        spec=_spec(("content",), allowed=("implantation",), marketing=True),
        scenarios=("doctor_trust",),
    )
    doctor_result = build_target_scoped_response_evidence(
        doctor_bound,
        md_root=md_root,
    )
    assert doctor_result.scope_records[-1].ref == "doctor:doctor_one"
    assert doctor_result.scope_records[-1].topics == ("implantation", "doctors")


def test_required_fact_coverage_counts_only_selected_commercial_facts(
    md_root: Path,
) -> None:
    selected = _bound(
        md_root,
        spec=_spec(
            ("price",),
            required_facts=("selected_fact",),
            marketing=True,
        ),
        initial=True,
    )
    result = build_target_scoped_response_evidence(selected, md_root=md_root)
    assert result.covered_fact_ids == ("selected_fact",)

    for required in ("candidate_fact", "unknown_fact"):
        candidate_only = _bound(
            md_root,
            spec=_spec(("price",), required_facts=(required,)),
        )
        with pytest.raises(TargetScopedResponseEvidenceError) as exc_info:
            build_target_scoped_response_evidence(candidate_only, md_root=md_root)
        assert exc_info.value.code == "scoped_evidence_required_fact_missing"
        assert exc_info.value.value == (required,)


def test_unfulfilled_component_precedes_selected_source_reads(md_root: Path) -> None:
    bound = _bound(
        md_root,
        spec=_spec(("price",)),
        bundle=_bundle(with_offer=False),
    )
    (md_root / "service_one.md").unlink()

    with pytest.raises(TargetScopedResponseEvidenceError) as exc_info:
        build_target_scoped_response_evidence(bound, md_root=md_root)
    assert exc_info.value.code == "scoped_evidence_component_unfulfilled"
    assert exc_info.value.value == ("price",)


def test_root_package_consistency_and_source_fail_closed(md_root: Path) -> None:
    bound = _bound(md_root)
    for bad_root in ("not-a-path", md_root / "missing"):
        with pytest.raises(TargetScopedResponseEvidenceError) as exc_info:
            build_target_scoped_response_evidence(bound, md_root=bad_root)  # type: ignore[arg-type]
        assert exc_info.value.code == "scoped_evidence_md_root_invalid"

    bad_plan = replace(bound.package.plan, service_id="other")
    inconsistent = replace(bound, package=replace(bound.package, plan=bad_plan))
    with pytest.raises(TargetScopedResponseEvidenceError) as exc_info:
        build_target_scoped_response_evidence(inconsistent, md_root=md_root)
    assert exc_info.value.code == "scoped_evidence_package_inconsistent"

    (md_root / "service_one.md").write_text(
        "---\ntopic: ' implantation'\n---\n",
        encoding="utf-8",
    )
    with pytest.raises(TargetScopedResponseEvidenceError) as exc_info:
        build_target_scoped_response_evidence(bound, md_root=md_root)
    assert exc_info.value.code == "scoped_evidence_source_invalid"
    assert exc_info.value.value == "service_one.md"


def test_medical_handoff_preserves_mode_and_uses_same_scope_checks(
    md_root: Path,
) -> None:
    medical_spec = _spec(
        ("doctors",),
        mode="medical_handoff",
        allowed=("implantation",),
        forbidden=("diagnosis",),
    )
    accepted = build_target_scoped_response_evidence(
        _bound(md_root, spec=medical_spec),
        md_root=md_root,
    )
    assert accepted.spec is medical_spec
    assert accepted.spec.response_mode == "medical_handoff"

    blocked_spec = _spec(
        ("doctors",),
        mode="medical_handoff",
        allowed=("implantation",),
        forbidden=("diagnosis", "doctors"),
    )
    with pytest.raises(TargetScopedResponseEvidenceError) as exc_info:
        build_target_scoped_response_evidence(
            _bound(md_root, spec=blocked_spec),
            md_root=md_root,
        )
    assert exc_info.value.code == "scoped_evidence_topic_forbidden"


def test_wrong_package_precedes_root_and_import_firewall(md_root: Path) -> None:
    with pytest.raises(TargetScopedResponseEvidenceError) as exc_info:
        build_target_scoped_response_evidence(object(), md_root=md_root)  # type: ignore[arg-type]
    assert exc_info.value.code == "scoped_evidence_package_invalid"

    source = Path("core/target_scoped_response_evidence.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert not any(
        module.startswith(
            ("app", "clients", "config", "handlers", "orchestration", "routes", "session")
        )
        for module in imported_modules
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"skip", "skipif", "xfail"}
        for node in ast.walk(tree)
    )
