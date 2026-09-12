from __future__ import annotations

import ast
import inspect
import json
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
from core.target_composer_request import (
    TargetComposerEvidenceBlock,
    TargetComposerRequest,
    TargetComposerRequestError,
    materialize_target_composer_request,
)
from contracts.target_response_policy import TargetResponsePolicyRequest
from core.doctor_schema_loader import load_doctor_catalog
from core.target_client_data import load_target_client_data
from core.target_fullcontext_content_package import assemble_target_fullcontext_content_bound_package
from core.target_response_policy import build_target_response_spec
from core.target_scoped_response_evidence import TargetScopedResponseEvidenceError
from core.target_spec_offline_response_package import (
    assemble_target_spec_offline_response_package,
)


TODAY = date(2026, 7, 22)


def _write_sources(root: Path) -> None:
    (root / "service_one.md").write_text(
        "---\n"
        "doc_id: service_one\n"
        "doc_type: service\n"
        "topic: implantation\n"
        "subtopic: overview\n"
        "suggest_h3:\n"
        "  - details\n"
        "---\n\n"
        "## Service One\n\n"
        "### Details {#details}\nSelected service detail.\n\n"
        "### Neighbor {#neighbor}\nNeighbor service detail.\n",
        encoding="utf-8",
    )
    (root / "doctor_one.md").write_text(
        "---\n"
        "doc_id: doctor_one\n"
        "doc_type: doctor\n"
        "topic: doctors\n"
        "subtopic: profile\n"
        "---\n\n"
        "## Doctor One\n\n"
        "### Profile {#profile}\nTrusted profile detail.\n\n"
        "### Private {#private}\nNeighbor doctor detail.\n",
        encoding="utf-8",
    )
    (root / "clinic.md").write_text(
        "---\n"
        "doc_id: clinic\n"
        "doc_type: info\n"
        "topic: clinic\n"
        "subtopic: payment\n"
        "---\n\n"
        "## Clinic\n\n"
        "```md\n### Fake {#one}\n```\n\n"
        "### Exact section {#one}\nSelected clinic detail.\n\n"
        "### Other section {#other}\nNeighbor clinic detail.\n",
        encoding="utf-8",
    )


@pytest.fixture
def md_root(tmp_path: Path) -> Path:
    _write_sources(tmp_path)
    return tmp_path


def _fact(*, render_mode: str = "strict") -> dict[str, object]:
    return {
        "id": "selected_fact",
        "kind": "promo",
        "catalog_label": "Selected commercial topic",
        "text_fact": "Exact selected commercial fact.",
        "render_mode": render_mode,
        "active": True,
        "allowed_service_ids": ["service_one"],
        "incompatible_with": [],
    }


def _bundle(*, fact_render_mode: str = "strict") -> ResponseSchemaBundle:
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
            "offers": [
                {
                    "offer_id": "offer_one",
                    "service_id": "service_one",
                    "option_id": None,
                    "brand_id": None,
                    "active": True,
                    "price": {
                        "mode": "fixed",
                        "amount": 100000,
                        "currency": "RUB",
                        "billing_unit": "jaw",
                    },
                    "package": {
                        "label": "Exact package",
                        "includes": ["Exact included item"],
                    },
                    "payment_stages": [
                        {
                            "label": "Stage one",
                            "amount": 60000,
                            "currency": "RUB",
                        },
                        {
                            "label": "Stage two",
                            "amount": 40000,
                            "currency": "RUB",
                        },
                    ],
                    "fact_refs": ["selected_fact"],
                    "followups": [
                        {
                            "id": "stages",
                            "label": "Payment stages",
                            "action": "price_aspect",
                        }
                    ],
                }
            ],
            "facts": {"selected_fact": _fact(render_mode=fact_render_mode)},
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


def _consultations(value: str = "Exact consultation meaning.") -> tuple[ServiceConsultationValue, ...]:
    return (
        ServiceConsultationValue(content_ref="service_one.md", value=value),
    )


def _spec(
    components: tuple[str, ...],
    *,
    mode: str = "answer",
    allowed: tuple[str, ...] = ("implantation", "doctors", "clinic"),
    required_facts: tuple[str, ...] = (),
    marketing: bool = False,
    consultation: bool = False,
    cta: bool = False,
):
    primary = "content" if "content" in components and "price" in components else None
    return build_target_response_spec(
        TargetResponsePolicyRequest.model_validate(
            {
                "response_mode": mode,
                "service_id": "service_one",
                "tone_key": "commercial_warm",
                "allowed_topics": allowed,
                "forbidden_topics": ("diagnosis", "personal_eligibility"),
                "required_fact_ids": required_facts,
                "requested_components": components,
                "primary_component": primary,
                "allow_marketing_facts": marketing,
                "allow_consultation_close": consultation,
                "allow_cta": cta,
            }
        )
    )


def _inject_external_source_refs(
    bound,
    refs: tuple[str, ...],
):
    materials = bound.package.materials
    injected_materials = replace(
        materials,
        external_source_refs=refs,
        marketing_selection=replace(
            materials.marketing_selection,
            amplifier_refs=tuple(
                dict.fromkeys((*materials.marketing_selection.amplifier_refs, *refs))
            ),
        ),
    )
    injected_plan = replace(
        bound.package.plan,
        external_source_refs=refs,
    )
    return replace(
        bound,
        package=replace(
            bound.package,
            materials=injected_materials,
            plan=injected_plan,
        ),
    )


def _inputs(
    md_root: Path,
    *,
    spec=None,
    bundle: ResponseSchemaBundle | None = None,
    doctors: TargetDoctorCatalog | None = None,
    consultations: tuple[ServiceConsultationValue, ...] | None = None,
    initial: bool = False,
    close: bool = False,
    cta: bool = False,
    scenarios: tuple[str, ...] = (),
    external_kb_ref: str = "kb:clinic.md#one",
    external_source_refs: tuple[str, ...] | None = None,
) -> dict[str, object]:
    bundle = bundle or _bundle()
    doctors = doctors or _doctors()
    consultations = consultations or _consultations()
    spec = spec or _spec(("content",))
    bound = assemble_target_spec_offline_response_package(
        bundle,
        doctors,
        ResponseSchemaExternalIndex(
            kb_refs=(external_kb_ref,),
            doctor_refs=("doctor:doctor_one",),
        ),
        consultations,
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
    if external_source_refs is None and scenarios:
        refs: list[str] = []
        if "cost" in scenarios:
            refs.append(external_kb_ref)
        if "doctor_trust" in scenarios:
            refs.append("doctor:doctor_one")
        external_source_refs = tuple(dict.fromkeys(refs))
    if external_source_refs:
        bound = _inject_external_source_refs(bound, external_source_refs)
    return {
        "bound_package": bound,
        "bundle": bundle,
        "doctor_catalog": doctors,
        "consultation_values": consultations,
        "user_message": "Tell me about Service One",
        "md_root": md_root,
    }


def _materialize(inputs: dict[str, object]) -> TargetComposerRequest:
    return materialize_target_composer_request(**inputs)  # type: ignore[arg-type]


def test_exact_shapes_signature_errors_and_frozen_slots(md_root: Path) -> None:
    result = _materialize(_inputs(md_root))
    assert [field.name for field in fields(TargetComposerEvidenceBlock)] == [
        "kind",
        "ref",
        "topics",
        "fact_ids",
        "text",
        "must_preserve_exact",
    ]
    assert [field.name for field in fields(TargetComposerRequest)] == [
        "user_message",
        "spec",
        "evidence_blocks",
        "selected_followups",
        "selected_cta_key",
        "action_context",
        "response_length_profile",
    ]
    assert list(inspect.signature(materialize_target_composer_request).parameters) == [
        "bound_package",
        "bundle",
        "doctor_catalog",
        "consultation_values",
        "user_message",
        "md_root",
        "contact_fields",
        "client_id",
        "response_length_profile",
    ]
    with pytest.raises(FrozenInstanceError):
        result.user_message = "changed"  # type: ignore[misc]
    assert not hasattr(result, "__dict__")

    source = Path("core/target_composer_request.py").read_text(encoding="utf-8")
    assert set(re.findall(r'"(composer_request_[a-z_]+)"', source)) == {
        "composer_request_package_invalid",
        "composer_request_sources_invalid",
        "composer_request_message_invalid",
        "composer_request_source_mismatch",
        "composer_request_material_invalid",
        "composer_request_output_inconsistent",
    }


def test_main_request_materializes_closed_exact_blocks_and_sidecars(md_root: Path) -> None:
    spec = _spec(
        ("content", "price", "doctors"),
        required_facts=("selected_fact",),
        marketing=True,
        consultation=True,
        cta=True,
    )
    inputs = _inputs(md_root, spec=spec, initial=True, close=True, cta=True)
    bound = inputs["bound_package"]
    result = _materialize(inputs)

    assert result.user_message == "Tell me about Service One"
    assert result.spec is spec
    assert result.selected_followups is bound.package.selected_followups  # type: ignore[union-attr]
    assert result.selected_cta_key == "plan"
    assert [block.kind for block in result.evidence_blocks] == [
        "content",
        "offer",
        "doctor",
        "commercial_fact",
        "consultation",
    ]
    assert [block.must_preserve_exact for block in result.evidence_blocks] == [
        False,
        True,
        True,
        True,
        False,
    ]
    assert not hasattr(result, "package")

    content = result.evidence_blocks[0]
    assert content.ref == "content:service_one.md"
    assert not content.text.startswith("---")
    assert "topic: implantation" not in content.text
    assert "Selected service detail." in content.text

    offer_payload = json.loads(result.evidence_blocks[1].text)
    assert list(offer_payload) == [
        "offer_id",
        "service_id",
        "option_id",
        "brand_id",
        "price",
        "package",
        "payment_stages",
    ]
    assert offer_payload["price"]["amount"] == 100000
    assert [stage["amount"] for stage in offer_payload["payment_stages"]] == [
        60000,
        40000,
    ]
    assert "fact_refs" not in offer_payload
    assert "followups" not in offer_payload

    doctor_payload = json.loads(result.evidence_blocks[2].text)
    assert list(doctor_payload) == [
        "doctor_id",
        "name",
        "position",
        "experience_years",
        "profile_text",
    ]
    assert doctor_payload["experience_years"] == 15
    assert "Trusted profile detail." in doctor_payload["profile_text"]
    assert "Neighbor doctor detail." not in doctor_payload["profile_text"]
    for forbidden in ("education", "photo", "schedule", "active"):
        assert forbidden not in doctor_payload

    assert result.evidence_blocks[3].text == "Exact selected commercial fact."
    assert result.evidence_blocks[3].fact_ids == ("selected_fact",)
    assert result.evidence_blocks[4].text == "Exact consultation meaning."


def test_external_refs_materialize_only_exact_sections_and_matrix(md_root: Path) -> None:
    inputs = _inputs(
        md_root,
        spec=_spec(("content",), marketing=True),
        scenarios=("cost", "doctor_trust"),
    )
    result = _materialize(inputs)
    assert [block.kind for block in result.evidence_blocks] == [
        "content",
        "external_kb",
        "external_doctor",
    ]
    assert [block.must_preserve_exact for block in result.evidence_blocks] == [
        False,
        False,
        True,
    ]
    kb_text = result.evidence_blocks[1].text
    assert "### Exact section {#one}" in kb_text
    assert "Selected clinic detail." in kb_text
    assert "Neighbor clinic detail." not in kb_text
    assert "Fake" not in kb_text
    doctor_payload = json.loads(result.evidence_blocks[2].text)
    assert doctor_payload["profile_text"].startswith("### Profile {#profile}")
    assert "Neighbor doctor detail." not in doctor_payload["profile_text"]


def test_unicode_exact_anchor_is_materialized_without_alphabet_inference(
    md_root: Path,
) -> None:
    clinic = md_root / "clinic.md"
    clinic.write_text(
        clinic.read_text(encoding="utf-8").replace("{#one}", "{#раздел}"),
        encoding="utf-8",
    )
    result = _materialize(
        _inputs(
            md_root,
            spec=_spec(("content",), marketing=True),
            scenarios=("cost",),
            external_kb_ref="kb:clinic.md#раздел",
        )
    )
    external = next(
        block for block in result.evidence_blocks if block.kind == "external_kb"
    )
    assert external.ref == "kb:clinic.md#раздел"
    assert "Selected clinic detail." in external.text


def test_natural_fact_has_false_preservation_flag(md_root: Path) -> None:
    bundle = _bundle(fact_render_mode="natural")
    inputs = _inputs(
        md_root,
        bundle=bundle,
        spec=_spec(("content",), marketing=True),
        initial=True,
    )
    result = _materialize(inputs)
    fact = next(block for block in result.evidence_blocks if block.kind == "commercial_fact")
    assert fact.text == "Exact selected commercial fact."
    assert fact.must_preserve_exact is False


@pytest.mark.parametrize(
    "field_value",
    [
        ("bound_package", object()),
        ("bundle", object()),
        ("consultation_values", "invalid"),
        ("user_message", " message "),
        ("user_message", ""),
    ],
)
def test_validation_precedence_and_exact_inputs(
    md_root: Path,
    field_value: tuple[str, object],
) -> None:
    field, value = field_value
    inputs = _inputs(md_root)
    inputs[field] = value
    expected = {
        "bound_package": "composer_request_package_invalid",
        "bundle": "composer_request_sources_invalid",
        "consultation_values": "composer_request_sources_invalid",
        "user_message": "composer_request_message_invalid",
    }[field]
    with pytest.raises(TargetComposerRequestError) as exc_info:
        _materialize(inputs)
    assert exc_info.value.code == expected


def test_s35_error_propagates_unchanged_after_message_validation(md_root: Path) -> None:
    inputs = _inputs(md_root)
    inputs["md_root"] = md_root / "missing"
    with pytest.raises(TargetScopedResponseEvidenceError) as exc_info:
        _materialize(inputs)
    assert exc_info.value.code == "scoped_evidence_md_root_invalid"


@pytest.mark.parametrize(
    "mutation",
    ["service", "offer", "fact", "doctor_profile", "doctor_link", "consultation"],
)
def test_same_id_changed_source_objects_fail_closed(
    md_root: Path,
    mutation: str,
) -> None:
    spec = _spec(
        ("content", "price", "doctors"),
        required_facts=("selected_fact",),
        marketing=True,
        consultation=True,
    )
    inputs = _inputs(md_root, spec=spec, initial=True, close=True)
    if mutation in {"service", "offer", "fact"}:
        changed = inputs["bundle"].model_copy(deep=True)  # type: ignore[union-attr]
        if mutation == "service":
            changed.services["service_one"].content_ref = "clinic.md"
        elif mutation == "offer":
            changed.offers[0].price.amount = 999999  # type: ignore[union-attr]
        else:
            changed.facts["selected_fact"].text_fact = "Changed fact."
        inputs["bundle"] = changed
    elif mutation in {"doctor_profile", "doctor_link"}:
        changed = inputs["doctor_catalog"].model_copy(deep=True)  # type: ignore[union-attr]
        if mutation == "doctor_profile":
            changed.doctors["doctor_one"].profile_ref = "kb:clinic.md#one"
        else:
            changed.doctors["doctor_one"].service_ids = ["other_service"]
        inputs["doctor_catalog"] = changed
    else:
        inputs["consultation_values"] = _consultations("Changed consultation.")

    with pytest.raises(TargetComposerRequestError) as exc_info:
        _materialize(inputs)
    assert exc_info.value.code == "composer_request_source_mismatch"


def test_missing_selected_anchor_fails_without_neighbor_fallback(md_root: Path) -> None:
    inputs = _inputs(
        md_root,
        spec=_spec(("content",), marketing=True),
        scenarios=("cost",),
    )
    clinic = md_root / "clinic.md"
    clinic.write_text(
        clinic.read_text(encoding="utf-8").replace("{#one}", "{#removed}"),
        encoding="utf-8",
    )
    with pytest.raises(TargetComposerRequestError) as exc_info:
        _materialize(inputs)
    assert exc_info.value.code == "composer_request_material_invalid"
    assert exc_info.value.value == "kb:clinic.md#one"


@pytest.mark.parametrize("mutation", ["duplicate", "empty"])
def test_duplicate_or_empty_selected_anchor_fails_without_partial_output(
    md_root: Path,
    mutation: str,
) -> None:
    inputs = _inputs(
        md_root,
        spec=_spec(("content",), marketing=True),
        scenarios=("cost",),
    )
    clinic = md_root / "clinic.md"
    text = clinic.read_text(encoding="utf-8")
    if mutation == "duplicate":
        text = text.replace("{#other}", "{#one}")
    else:
        text = text.replace("Selected clinic detail.", "")
    clinic.write_text(text, encoding="utf-8")

    with pytest.raises(TargetComposerRequestError) as exc_info:
        _materialize(inputs)
    assert exc_info.value.code == "composer_request_material_invalid"
    assert exc_info.value.value == "kb:clinic.md#one"


def test_escaping_selected_md_ref_propagates_s35_fail_closed(md_root: Path) -> None:
    inputs = _inputs(
        md_root,
        spec=_spec(("content",), marketing=True),
        external_source_refs=("kb:../outside.md#one",),
        external_kb_ref="kb:../outside.md#one",
    )
    with pytest.raises(TargetScopedResponseEvidenceError) as exc_info:
        _materialize(inputs)
    assert exc_info.value.code == "scoped_evidence_source_invalid"
    assert exc_info.value.value == "kb:../outside.md#one"


def test_medical_handoff_is_preserved_without_generating_prose(md_root: Path) -> None:
    spec = _spec(
        ("content",),
        mode="medical_handoff",
        allowed=("implantation",),
    )
    result = _materialize(_inputs(md_root, spec=spec))
    assert result.spec is spec
    assert result.spec.response_mode == "medical_handoff"
    assert result.evidence_blocks[0].kind == "content"
    assert not hasattr(result, "answer")


def _tomography_bundle() -> ResponseSchemaBundle:
    return ResponseSchemaBundle.model_validate(
        {
            "services": {
                "tomography": {
                    "name": "КТ",
                    "aliases": ["кт"],
                    "family": "diagnostics",
                    "roles": ["supporting"],
                    "active": True,
                    "selection": {"mode": "direct"},
                    "options": [],
                }
            },
            "brands": {"version": 1, "brands": {}},
            "offers": [
                {
                    "offer_id": "tomography.default",
                    "service_id": "tomography",
                    "option_id": None,
                    "brand_id": None,
                    "active": True,
                    "price": {
                        "mode": "fixed",
                        "amount": 3000,
                        "currency": "RUB",
                        "billing_unit": "procedure",
                    },
                    "package": {"label": "procedure", "includes": []},
                    "fact_refs": [],
                    "followups": [],
                }
            ],
            "facts": {},
            "strategy": {"version": 1, "default_max_options": 3, "rules": []},
            "marketing": {
                "version": 1,
                "limits": {
                    "max_marketing_facts_per_turn": 0,
                    "max_amplifiers_per_turn": 0,
                    "max_scenarios_per_turn": 0,
                },
                "initial_commercial_blocks": {},
                "scenario_rules": {},
                "cta_contexts": {"default": "callback"},
            },
        }
    )


def _tomography_inputs(md_root: Path) -> dict[str, object]:
    bundle = _tomography_bundle()
    doctors = _doctors()
    spec = build_target_response_spec(
        TargetResponsePolicyRequest.model_validate(
            {
                "response_mode": "answer",
                "service_id": "tomography",
                "tone_key": "commercial_warm",
                "allowed_topics": ("implantation", "clinic"),
                "forbidden_topics": ("diagnosis", "personal_eligibility"),
                "required_fact_ids": (),
                "requested_components": ("price",),
                "primary_component": None,
                "allow_marketing_facts": False,
                "allow_consultation_close": False,
                "allow_cta": True,
            }
        )
    )
    bound = assemble_target_spec_offline_response_package(
        bundle,
        doctors,
        ResponseSchemaExternalIndex(kb_refs=(), doctor_refs=()),
        (),
        spec=spec,
        brand_term=None,
        strategy_context=TargetStrategyMatch(family="diagnostics"),
        semantic_context="service",
        today=TODAY,
        md_root=md_root,
        include_initial_block=False,
        include_consultation_close=False,
        include_cta=True,
    )
    return {
        "bound_package": bound,
        "bundle": bundle,
        "doctor_catalog": doctors,
        "consultation_values": (),
        "user_message": "Сколько стоит КТ?",
        "md_root": md_root,
    }


def test_tomography_price_only_without_content_ref_materializes_offer_evidence(
    md_root: Path,
) -> None:
    result = _materialize(_tomography_inputs(md_root))
    assert [block.kind for block in result.evidence_blocks] == ["offer"]
    assert result.evidence_blocks[0].ref == "offer:tomography.default"
    payload = json.loads(result.evidence_blocks[0].text)
    assert payload["price"]["amount"] == 3000


def test_s35_called_once_and_import_firewall(md_root: Path, monkeypatch) -> None:
    import core.target_composer_request as module

    original = module.build_target_scoped_response_evidence
    calls = 0

    def counted(*args: object, **kwargs: object):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(module, "build_target_scoped_response_evidence", counted)
    _materialize(_inputs(md_root))
    assert calls == 1

    source = Path("core/target_composer_request.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert not any(
        module_name.startswith(
            (
                "app",
                "clients",
                "config",
                "handlers",
                "orchestration",
                "routes",
                "session",
                "core.answer_packet",
                "core.knowledge_base",
                "core.llm",
                "core.md_chunks",
            )
        )
        for module_name in imported_modules
    )
    forbidden_calls = {"skip", "skipif", "xfail", "search", "query", "chat", "complete"}
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in forbidden_calls
        for node in ast.walk(tree)
    )


_NIKADENT_ROOT = Path(__file__).resolve().parents[1] / "clients" / "nikadent"
_NIKADENT_MD = _NIKADENT_ROOT / "md"


def _nikadent_content_only_policy() -> TargetResponsePolicyRequest:
    return TargetResponsePolicyRequest.model_validate(
        {
            "response_mode": "answer",
            "service_id": None,
            "tone_key": "commercial_warm",
            "allowed_topics": ("clinic", "implantation", "prosthetics"),
            "forbidden_topics": ("diagnosis", "personal_eligibility"),
            "required_fact_ids": (),
            "requested_components": ("content",),
            "primary_component": None,
            "allow_marketing_facts": False,
            "allow_consultation_close": False,
            "allow_cta": False,
        }
    )


def _materialize_nikadent_contact_composer_request(user_message: str) -> TargetComposerRequest:
    data = load_target_client_data("nikadent")
    doctors = load_doctor_catalog(_NIKADENT_ROOT / "doctor_catalog.json")
    spec = build_target_response_spec(_nikadent_content_only_policy())
    bound = assemble_target_fullcontext_content_bound_package(spec, bundle=data.bundle)
    return materialize_target_composer_request(
        bound,
        data.bundle,
        doctors,
        (),
        user_message=user_message,
        md_root=_NIKADENT_MD,
        contact_fields=("phone",),
        client_id="nikadent",
    )


@pytest.mark.parametrize(
    ("user_message", "expect_filial_1", "expect_filial_2"),
    [
        ("Дайте телефон филиала на Пограничной", False, True),
        ("Дайте телефон клиники", True, True),
    ],
)
def test_nikadent_composer_prepends_contact_evidence_without_name_error(
    user_message: str,
    expect_filial_1: bool,
    expect_filial_2: bool,
) -> None:
    request = _materialize_nikadent_contact_composer_request(user_message)
    contact_blocks = [block for block in request.evidence_blocks if block.kind == "clinic_contact"]
    assert contact_blocks
    combined = "\n".join(block.text for block in contact_blocks)
    if expect_filial_1:
        assert "Филиал 1" in combined
        assert "+7 (900) 444-69-97" in combined
    else:
        assert "Филиал 1" not in combined
        assert "+7 (900) 444-69-97" not in combined
    if expect_filial_2:
        assert "Филиал 2" in combined
        assert "+7 (914) 995-78-82" in combined
    else:
        assert "Филиал 2" not in combined
        assert "+7 (914) 995-78-82" not in combined
    if expect_filial_1 and expect_filial_2:
        assert "+7 (900) 444-69-97" in combined
        assert "+7 (914) 995-78-82" in combined


def test_demo_promotion_general_composer_emits_three_commercial_fact_blocks() -> None:
    from tests.test_target_scoped_response_evidence import _demo_general_promotion_bound

    demo_root = Path(__file__).resolve().parents[1] / "clients" / "demo"
    demo_md = demo_root / "md"
    data = load_target_client_data("demo")
    doctors = load_doctor_catalog(demo_root / "doctor_catalog.json")
    bound = _demo_general_promotion_bound()
    request = materialize_target_composer_request(
        bound,
        data.bundle,
        doctors,
        (),
        user_message="Какие акции у вас есть?",
        md_root=demo_md,
        client_id="demo",
    )
    expected_refs = (
        "fact:implant_same_day_discount",
        "fact:professional_whitening_discount",
        "fact:free_implant_consult",
    )
    commercial_blocks = [
        block for block in request.evidence_blocks if block.kind == "commercial_fact"
    ]
    assert tuple(block.ref for block in commercial_blocks) == expected_refs
    assert len(commercial_blocks) == 3
    for block, fact_id in zip(commercial_blocks, expected_refs, strict=True):
        fact = data.bundle.facts[block.ref.removeprefix("fact:")]
        assert block.text == str(fact.text_fact)
