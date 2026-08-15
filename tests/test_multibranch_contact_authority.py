"""Offline tests for backward-compatible multibranch clinic contacts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from contracts.ingress_route import IngressRouteResult
from contracts.planner_attempt import PlannerAttempt
from contracts.target_turn_frame_dispatch import TargetTurnFrameBoundMaterializeResponse
from core.clinic_contact_policies import (
    ClinicContactBranch,
    ClinicContactFacts,
    collect_manual_contact_phone_lines,
    format_manual_contact_phone_suffix,
    load_clinic_contact_facts_from_policies_path,
    resolve_contact_branch_id_from_facts,
    selection_token_matches_hint,
    validate_clinic_contact_section,
)
from core.clinic_policies_loader import load_clinic_policies
from core.response_schema_loader import load_response_schema_bundle
from core.target_contact_authority import (
    canonical_contact_phone,
    canonical_contact_scalar,
    format_manual_contact_phone_suffix_for_client,
    load_clinic_contact_facts,
    materialize_clinic_contact_primary_evidence,
    parse_contact_evidence_ref,
    resolve_contact_branch_id,
)
from core.target_response_verifier import (
    TargetResponseVerificationError,
    verify_target_composed_response,
)
from core.target_structured_answer import materialize_structured_contact_answer_text
from core.turn_frame_from_raw import build_turn_frame_from_raw
from ingress_gate import build_ingress_payload
from scripts.validate_client_pack import validate_client_pack
from tests.test_final_fullcontext_dialogue_runtime_convergence_harness import (
    build_frame,
    default_backends,
    install_turn_frame,
    run_runtime_turn,
)
from tests.test_target_response_verifier import (
    RecordingBackend,
    _cached_context,
    _request,
    _response,
    _spec,
)

_NIKADENT_ROOT = Path(__file__).resolve().parents[1] / "clients" / "nikadent"
_NIKADENT_TARGET = _NIKADENT_ROOT / "target_response"
_NIKADENT_BUNDLE = load_response_schema_bundle(_NIKADENT_TARGET)
_NIKADENT_SERVICES = frozenset(_NIKADENT_BUNDLE.services.keys())
_NIKADENT_TOPICS = frozenset({"clinic", "implantation", "prosthetics", "therapy"})


def _ingress_manual(question: str = "", *, urgent: bool = False) -> dict[str, object]:
    result = IngressRouteResult(
        route="manual_contact",
        confidence=1.0,
        reason="test",
        is_urgent=urgent,
    )
    return build_ingress_payload(
        result,
        sid="ingress-test",
        client_id="nikadent",
        question=question,
    )


def test_demo_legacy_scalar_contact_loads_without_branches() -> None:
    facts = load_clinic_contact_facts("demo")
    assert facts.branches == ()
    assert facts.phone_display == "+7 (495) 128-47-60"
    assert facts.address_display
    assert "Тверская" in facts.address_display
    assert facts.hours_display
    assert facts.whatsapp_display


def test_demo_legacy_contact_evidence_refs_and_scalars() -> None:
    blocks = materialize_clinic_contact_primary_evidence("demo", aspect="contacts")
    refs = {block.ref for block in blocks}
    assert refs == {
        "clinic_contact:phone",
        "clinic_contact:whatsapp",
        "clinic_contact:address",
        "clinic_contact:hours",
        "clinic_contact:parking",
    }
    assert canonical_contact_scalar("address", "demo") == load_clinic_contact_facts("demo").address_display


def test_nikadent_multibranch_loads_two_branches() -> None:
    facts = load_clinic_contact_facts("nikadent")
    assert len(facts.branches) == 2
    branch_ids = {branch.branch_id for branch in facts.branches}
    assert branch_ids == {"ryabikova", "pogranichnaya"}


def test_nikadent_branch_phone_lists_are_nonempty_and_separated() -> None:
    facts = load_clinic_contact_facts("nikadent")
    ryabikova = next(b for b in facts.branches if b.branch_id == "ryabikova")
    pogranichnaya = next(b for b in facts.branches if b.branch_id == "pogranichnaya")
    assert ryabikova.phone_displays == ("+7 (900) 444-69-97", "+7 (984) 164-52-89")
    assert pogranichnaya.phone_displays == ("+7 (914) 995-78-82", "+7 (900) 437-57-46")
    assert set(ryabikova.phone_displays).isdisjoint(set(pogranichnaya.phone_displays))


def test_nikadent_general_contact_materialization_lists_both_branches() -> None:
    answer = materialize_structured_contact_answer_text(
        "nikadent",
        contact_fields=("phone", "address", "hours"),
    )
    assert "Филиал 1" in answer
    assert "Филиал 2" in answer
    assert "+7 (900) 444-69-97" in answer
    assert "+7 (914) 995-78-82" in answer
    ryabikova_phone_line = next(
        line for line in answer.splitlines() if "+7 (900) 444-69-97" in line
    )
    assert "Пограничная" not in ryabikova_phone_line


def test_nikadent_branch_specific_selection_by_alias() -> None:
    assert resolve_contact_branch_id("nikadent", "телефон филиала на Рябикова") == "ryabikova"
    assert resolve_contact_branch_id("nikadent", "как работает филиал на Пограничной") == "pogranichnaya"
    assert resolve_contact_branch_id("nikadent", "адрес первого филиала") == "ryabikova"
    assert resolve_contact_branch_id("nikadent", "адрес второго филиала") == "pogranichnaya"
    assert resolve_contact_branch_id("nikadent", "филиал 10") is None
    facts = load_clinic_contact_facts("nikadent")
    assert resolve_contact_branch_id_from_facts(facts, "филиал 1") == "ryabikova"
    assert resolve_contact_branch_id_from_facts(facts, "филиал 10") is None
    assert selection_token_matches_hint("филиал 1", "филиал 1")
    assert not selection_token_matches_hint("филиал 10", "филиал 1")


def test_nikadent_branch_specific_materialization_filters_fields() -> None:
    answer = materialize_structured_contact_answer_text(
        "nikadent",
        contact_fields=("phone", "address"),
        branch_hint_text="филиал на Рябикова",
    )
    assert "Филиал 1" in answer
    assert "Филиал 2" not in answer
    assert "+7 (914) 995-78-82" not in answer
    assert "Пограничная" not in answer


def test_nikadent_branch_evidence_refs_are_stable_and_parseable() -> None:
    blocks = materialize_clinic_contact_primary_evidence(
        "nikadent",
        fields=("phone",),
        branch_hint_text="пограничная",
    )
    assert len(blocks) == 1
    field, branch_id = parse_contact_evidence_ref(blocks[0].ref)
    assert field == "phone"
    assert branch_id == "pogranichnaya"
    assert blocks[0].ref == "clinic_contact:branch:pogranichnaya:phone"


def test_demo_manual_contact_phone_fallback_unchanged() -> None:
    bundle = load_clinic_policies("demo")
    assert bundle is not None
    assert bundle.contact_phone_display == "+7 (495) 128-47-60"
    suffix = format_manual_contact_phone_suffix_for_client("demo")
    assert suffix == f" по номеру {bundle.contact_phone_display}"


def test_nikadent_manual_contact_ingress_payload_is_signed_and_capped() -> None:
    payload = _ingress_manual()
    answer = str(payload["answer"])
    assert "по номеру" not in answer.casefold()
    assert "- Филиал 1:" in answer
    assert answer.count("+7") == 2
    assert "+7 (900) 444-69-97" in answer
    assert "+7 (984) 164-52-89" in answer
    assert "+7 (914) 995-78-82" not in answer


def test_nikadent_manual_contact_with_branch_hint_uses_only_that_branch() -> None:
    payload = _ingress_manual("телефон филиала на Пограничной")
    answer = str(payload["answer"])
    assert "Филиал 2" in answer
    assert "Филиал 1" not in answer
    assert answer.count("+7") == 2
    assert "+7 (914) 995-78-82" in answer
    assert "+7 (900) 444-69-97" not in answer


def test_nikadent_manual_contact_three_phones_returns_only_two() -> None:
    facts = load_clinic_contact_facts("nikadent")
    triple = ClinicContactBranch(
        branch_id="triple",
        label="Филиал X",
        aliases=(),
        address_display="адрес",
        phone_displays=("+7 (111) 111-11-11", "+7 (222) 222-22-22", "+7 (333) 333-33-33"),
        hours_display="9-18",
    )
    augmented = ClinicContactFacts(
        phone_display="",
        whatsapp_display=facts.whatsapp_display,
        address_display=None,
        hours_display=None,
        parking_display=None,
        branches=(triple,),
    )
    lines = collect_manual_contact_phone_lines(augmented)
    assert len(lines) == 2
    assert lines[0][1] == "+7 (111) 111-11-11"
    assert lines[1][1] == "+7 (222) 222-22-22"


def test_manual_contact_follows_authored_yaml_branch_order() -> None:
    facts = load_clinic_contact_facts("nikadent")
    lines = collect_manual_contact_phone_lines(facts)
    assert lines[0][0] == "Филиал 1"
    assert "+7 (900) 444-69-97" in lines[0][1]
    assert lines[1][0] == "Филиал 1"
    assert "+7 (984) 164-52-89" in lines[1][1]


def test_manual_contact_five_branches_returns_max_two_phones() -> None:
    branches = tuple(
        ClinicContactBranch(
            branch_id=f"b{i}",
            label=f"Филиал {i}",
            aliases=(),
            address_display=f"адрес {i}",
            phone_displays=(f"+7 (900) 000-00-{i:02d}",),
            hours_display="9-18",
        )
        for i in range(5)
    )
    facts = ClinicContactFacts(
        phone_display="",
        whatsapp_display=None,
        address_display=None,
        hours_display=None,
        parking_display=None,
        branches=branches,
    )
    lines = collect_manual_contact_phone_lines(facts)
    assert len(lines) == 2
    assert lines[0][0] == "Филиал 0"
    assert lines[1][0] == "Филиал 1"


def test_manual_contact_duplicate_phone_across_branches_once() -> None:
    shared = "+7 (900) 111-11-11"
    unique_b = "+7 (900) 333-33-33"
    facts = ClinicContactFacts(
        phone_display="",
        whatsapp_display=None,
        address_display=None,
        hours_display=None,
        parking_display=None,
        branches=(
            ClinicContactBranch(
                branch_id="a",
                label="Филиал A",
                aliases=(),
                address_display="a",
                phone_displays=(shared,),
                hours_display="9-18",
            ),
            ClinicContactBranch(
                branch_id="b",
                label="Филиал B",
                aliases=(),
                address_display="b",
                phone_displays=(shared, unique_b),
                hours_display="9-18",
            ),
        ),
    )
    lines = collect_manual_contact_phone_lines(facts)
    assert len(lines) == 2
    assert lines[0] == ("Филиал A", shared)
    assert lines[1] == ("Филиал B", unique_b)
    phones = [phone for _, phone in lines]
    assert phones.count(shared) == 1


def test_single_branch_manual_contact_without_extra_config() -> None:
    facts = ClinicContactFacts(
        phone_display="",
        whatsapp_display=None,
        address_display=None,
        hours_display=None,
        parking_display=None,
        branches=(
            ClinicContactBranch(
                branch_id="only",
                label="Only",
                aliases=(),
                address_display="адрес",
                phone_displays=("+7 (900) 555-55-55",),
                hours_display="9-18",
            ),
        ),
    )
    lines = collect_manual_contact_phone_lines(facts)
    assert lines == (("Only", "+7 (900) 555-55-55"),)


def test_branch_verifier_accepts_correct_association() -> None:
    blocks = materialize_clinic_contact_primary_evidence(
        "nikadent",
        fields=("address",),
        branch_hint_text="рябикова",
    )
    answer = "\n".join(block.text for block in blocks)
    request = _request(
        spec=_spec(required_components=("content",), required_fact_ids=()),
        blocks=blocks,
    )
    semantic = RecordingBackend()
    result = verify_target_composed_response(
        request,
        _response(request, answer),
        cached_full_context=_cached_context(),
        semantic_backend=semantic,
        client_id="nikadent",
    )
    assert result.verification_status == "verified"
    assert len(semantic.invocations) == 1


def test_branch_verifier_blocks_swapped_addresses() -> None:
    blocks = materialize_clinic_contact_primary_evidence(
        "nikadent",
        fields=("address",),
        branch_hint_text="рябикова",
    )
    wrong_label_line = blocks[0].text.replace("Филиал 1:", "Филиал 2:", 1)
    request = _request(
        spec=_spec(required_components=("content",), required_fact_ids=()),
        blocks=blocks,
    )
    semantic = RecordingBackend()
    with pytest.raises(TargetResponseVerificationError):
        verify_target_composed_response(
            request,
            _response(request, wrong_label_line),
            cached_full_context=_cached_context(),
            semantic_backend=semantic,
            client_id="nikadent",
        )
    assert len(semantic.invocations) == 0


def test_branch_verifier_blocks_swapped_phones() -> None:
    blocks = materialize_clinic_contact_primary_evidence(
        "nikadent",
        fields=("phone",),
        branch_hint_text="рябикова",
    )
    wrong_phone = canonical_contact_scalar("phone", "nikadent", branch_id="pogranichnaya")
    swapped = f"Филиал 1: Телефон: {wrong_phone}"
    request = _request(
        spec=_spec(required_components=("content",), required_fact_ids=()),
        blocks=blocks,
    )
    with pytest.raises(TargetResponseVerificationError):
        verify_target_composed_response(
            request,
            _response(request, swapped),
            cached_full_context=_cached_context(),
            semantic_backend=RecordingBackend(),
            client_id="nikadent",
        )


def test_validator_rejects_invalid_branch_id() -> None:
    contact = {
        "branches": [
            {
                "branch_id": "BAD",
                "label": "X",
                "aliases": [],
                "address_display": "a",
                "phone_displays": ["+7"],
                "hours_display": "9-18",
            }
        ],
    }
    errors = validate_clinic_contact_section(contact)
    assert any("branch_id_invalid" in err for err in errors)


def test_validator_rejects_mixed_scalar_and_branches() -> None:
    contact = {
        "phone_display": "+7 (000) 000-00-00",
        "branches": [
            {
                "branch_id": "one",
                "label": "One",
                "aliases": [],
                "address_display": "a",
                "phone_displays": ["+7"],
                "hours_display": "9-18",
            }
        ],
    }
    errors = validate_clinic_contact_section(contact)
    assert any("phone_display_forbidden_with_branches" in err for err in errors)


def test_validator_multibranch_pack_in_tmp_path_is_isolated(tmp_path: Path) -> None:
    pack = tmp_path / "isolated_multibranch"
    pack.mkdir()
    (pack / "md").mkdir()
    (pack / "md" / "x.md").write_text("# x\n", encoding="utf-8")
    target = pack / "target_response"
    target.mkdir()
    (target / "pricebook" / "services").mkdir(parents=True)
    template = Path(__file__).resolve().parents[1] / "clients" / "_template"
    for name in (
        "service_catalog.json",
        "brand_catalog.json",
        "marketing.yaml",
        "clinic_strategy.yaml",
        "pricebook/facts.json",
        "pricebook/family_prices.json",
    ):
        src = template / "target_response" / name
        if src.is_file():
            dest = target / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    (target / "pricebook" / "services" / "stub.default.json").write_text(
        json.dumps(
            {
                "offer_id": "stub.default",
                "service_id": "stub",
                "active": True,
                "price": {
                    "mode": "fixed",
                    "amount": 1000,
                    "currency": "RUB",
                    "billing_unit": "procedure",
                },
                "package": {"label": "x", "includes": []},
                "followups": [],
            }
        ),
        encoding="utf-8",
    )
    (target / "service_catalog.json").write_text(
        json.dumps(
            {
                "stub": {
                    "name": "Stub",
                    "aliases": ["stub"],
                    "family": "therapy",
                    "roles": [],
                    "active": True,
                    "content_ref": "x.md",
                    "selection": {"mode": "direct"},
                    "options": [],
                }
            }
        ),
        encoding="utf-8",
    )
    for name in (
        "brand.yaml",
        "features.yaml",
        "lead_config.yaml",
        "tone.yaml",
        "widget_config.json",
        "doctor_catalog.json",
    ):
        (pack / name).write_text((template / name).read_text(encoding="utf-8"), encoding="utf-8")
    unique_phone = "+7 (999) 888-77-66"
    (pack / "clinic_policies.yaml").write_text(
        yaml.safe_dump(
            {
                "contact": {
                    "branches": [
                        {
                            "branch_id": "only",
                            "label": "Only",
                            "aliases": ["only"],
                            "address_display": "г. Тест, ул. Уникальная, 1",
                            "phone_displays": [unique_phone],
                            "hours_display": "9-18",
                        }
                    ],
                },
                "policies": {},
                "service_alternatives": [],
                "service_not_offered_template": "нет",
                "hard_stop_template": "стоп",
                "manual_contact_template": "звоните{phone_suffix}{urgent_suffix}",
                "manual_contact_urgent_suffix": "",
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    errors = validate_client_pack(pack)
    assert errors == []
    facts = load_clinic_contact_facts_from_policies_path(pack / "clinic_policies.yaml")
    assert facts.branches[0].phone_displays == (unique_phone,)


def test_nikadent_structured_runtime_turn_ryabikova_only() -> None:
    from flask import Flask, request

    from core.target_runtime_turn import run_target_fullcontext_runtime_turn
    from core.runtime_turn_frame import publish_planner_attempt_frame
    from contracts.planner_attempt import PlannerAttempt

    frame = build_frame(
        allowed_topics=_NIKADENT_TOPICS,
        allowed_service_ids=_NIKADENT_SERVICES,
        topic="clinic",
        aspects=["contact_address"],
        primary_aspect="contact_address",
        service_id=None,
    )
    composer, semantic, boundary = default_backends("should not run")
    app = Flask(__name__)
    with app.test_request_context():
        request.ctx = {}
        publish_planner_attempt_frame(
            attempt=PlannerAttempt(frame=frame, status="ok")  # type: ignore[arg-type]
        )
        outcome = run_target_fullcontext_runtime_turn(
            client_id="nikadent",
            sid="nikadent-ryabikova-runtime",
            user_message="адрес филиала на Рябикова",
            composer_backend=composer,
            semantic_backend=semantic,
            boundary_backend=boundary,
        )
    answer = outcome.widget.payload.get("answer") or ""
    assert "Филиал 1" in answer
    assert "Рябикова" in answer
    assert "Пограничная" not in answer
    assert len(composer.invocations) == 0
    assert len(semantic.invocations) == 0


def test_sales_one_plus_deterministic_contact_pogranichnaya() -> None:
    from orchestration.sales_one_plus_ask_turn import _try_deterministic_contacts_terminal

    def _payload(answer: str, sid: str, client_id: str) -> dict[str, str]:
        return {"answer": answer, "sid": sid, "client_id": client_id}

    result = _try_deterministic_contacts_terminal(
        q="телефон филиала на Пограничной",
        sid="sales-test",
        client_id="nikadent",
        service_payload=_payload,
    )
    assert result is not None
    answer = result.service_payload["answer"]
    assert "Филиал 2" in answer
    assert "Филиал 1" not in answer
    assert "+7 (914) 995-78-82" in answer
    assert "+7 (900) 444-69-97" not in answer
