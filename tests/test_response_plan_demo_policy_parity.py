"""DEMO-POLICY-PARITY-1: offline parity for demo clinic policies on response-plan path."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from contracts.authored_service_alternative import AuthoredServiceAlternative
from contracts.response_plan import SessionKey
from contracts.response_plan_post_composer import PostComposerMaterialAuthority
from contracts.response_schema import ResponseSchemaBundle, TargetService
from core.response_plan_composer_authority import build_composer_decision_authority
from core.response_plan_composer_contract import (
    build_composer_policy_sidecar,
    serialize_composer_policy_sidecar,
)
from core.response_schema_loader import load_response_schema_bundle
from tests.test_response_plan_dialogue_acceptance import (
    DialogueContext,
    DialogueRunner,
    TurnSpec,
    _composer_dict,
    _demo_context,
    _demo_corpus,
    _policy,
    _store,
)

TARGET_ROOT = Path("clients/demo/target_response")
BRACES_APPROVED = (
    "Брекеты мы не устанавливаем. Для выравнивания зубов "
    "в клинике используются элайнеры."
)
ALIGNERS_NAME = "Элайнеры для выравнивания зубов"
INSTALLMENT_NEGATIVE_SCOPE = (
    "На лечение кариеса и удаление зуба рассрочка не предоставляется."
)
GROUP_ALT_TEXT = "Доступны варианты A и B для выравнивания."
POLICY_PATCH = "core.response_plan_authored_alternative_policy.load_authored_service_alternatives"

def _runner(tmp_path: Path, *, ctx: DialogueContext | None = None) -> DialogueRunner:
    return DialogueRunner(
        store=_store(tmp_path),
        ctx=ctx or _demo_context(),
        policy=_policy(),
    )


def _installment_sidecar_fact(*, bundle: ResponseSchemaBundle | None = None) -> dict[str, object]:
    material = PostComposerMaterialAuthority(
        source_client_id="demo",
        bundle=bundle or load_response_schema_bundle(TARGET_ROOT),
    )
    authority = build_composer_decision_authority(
        material,
        allowed_source_refs=(),
        history_turn_count=0,
        active_session_service_id=None,
        as_of=date(2026, 9, 3),
    )
    sidecar = build_composer_policy_sidecar(authority)
    payload = json.loads(serialize_composer_policy_sidecar(sidecar))
    return next(
        item for item in payload["requestable_facts"] if item["fact_id"] == "installment_12"
    )


def _bundle_with_inactive(service_id: str, *, name: str, family: str = "orthodontics") -> ResponseSchemaBundle:
    base = load_response_schema_bundle(TARGET_ROOT)
    services = dict(base.services)
    services[service_id] = TargetService(
        name=name,
        aliases=[],
        family=family,  # type: ignore[arg-type]
        roles=[],
        active=False,
        selection={"mode": "context"},
        options=[],
    )
    return base.model_copy(update={"services": services})


def _demo_context_for_bundle(bundle: ResponseSchemaBundle) -> DialogueContext:
    return DialogueContext(
        label="demo_policy_fixture",
        data_kind="SYNTHETIC_FIXTURE",
        session_key=SessionKey(client_id="demo", sid="demo-policy-parity"),
        material=PostComposerMaterialAuthority(source_client_id="demo", bundle=bundle),
        corpus=_demo_corpus("demo"),
        condition_evidence={},
    )


def _inactive_turn(
    *,
    inactive_service_id: str,
    request_id: str,
    patient_message: str,
    **composer_overrides: object,
) -> TurnSpec:
    payload = {
        "patient_text": "Про недоступную услугу.",
        "service_reference_kind": "explicit_current",
        "explicit_service_id": inactive_service_id,
        "requested_aspect_ids": ["service_availability"],
    }
    payload.update(composer_overrides)
    return TurnSpec(
        patient_message=patient_message,
        request_id=request_id,
        composer_json=_composer_dict(**payload),
    )


def _braces_turn(*, request_id: str, patient_message: str, **composer_overrides: object) -> TurnSpec:
    payload = {
        "patient_text": "Про брекеты.",
        "service_reference_kind": "explicit_current",
        "explicit_service_id": "braces",
        "requested_aspect_ids": ["service_availability"],
    }
    payload.update(composer_overrides)
    return TurnSpec(
        patient_message=patient_message,
        request_id=request_id,
        composer_json=_composer_dict(**payload),
    )


def test_braces_known_inactive_shows_authored_aligners(tmp_path: Path) -> None:
    outcome = _runner(tmp_path).run_turn(
        _braces_turn(request_id="braces-1", patient_message="Можно поставить брекеты?")
    )
    selection = outcome.pipeline.selection
    resolved = outcome.pipeline.materialized.resolved

    assert selection.reference_service_id == "braces"
    assert selection.response_scope == "topic"
    assert selection.selection_basis == "authored_alternative"
    assert selection.visible_service_option_ids == ("aligners",)
    assert selection.price_candidate_service_ids == ()
    assert resolved.response_scope == "topic"
    assert resolved.session_delta.active_service_id is None
    assert resolved.authored_service_alternative_block is not None
    assert resolved.authored_service_alternative_block.approved_text == BRACES_APPROVED
    assert resolved.authored_service_alternative_block.options_unambiguous_topic_id == "orthodontics"
    assert resolved.finalized_commercial_ids.shown_service_option_ids == ("aligners",)
    assert BRACES_APPROVED in outcome.prepared.rendered_text
    assert ALIGNERS_NAME in outcome.prepared.rendered_text
    assert resolved.price_block is None


def test_braces_price_request_shows_alternative_without_price(tmp_path: Path) -> None:
    outcome = _runner(tmp_path).run_turn(
        _braces_turn(
            request_id="braces-price",
            patient_message="Сколько стоят брекеты?",
            requested_aspect_ids=["price"],
        )
    )
    resolved = outcome.pipeline.materialized.resolved

    assert resolved.price_block is None
    assert resolved.finalized_commercial_ids.price_offer_ids == ()
    assert resolved.authored_service_alternative_block is not None
    assert len(resolved.authored_service_alternative_block.options) == 1
    assert "₽" not in outcome.prepared.rendered_text
    assert BRACES_APPROVED in outcome.prepared.rendered_text
    assert ALIGNERS_NAME in outcome.prepared.rendered_text


def test_known_inactive_without_authored_policy_has_no_options(tmp_path: Path) -> None:
    with patch(POLICY_PATCH, return_value=()):
        outcome = _runner(tmp_path).run_turn(
            _braces_turn(request_id="braces-no-policy", patient_message="Нужны брекеты")
        )
    resolved = outcome.pipeline.materialized.resolved

    assert resolved.finalized_commercial_ids.shown_service_option_ids == ()
    assert resolved.authored_service_alternative_block is not None
    assert "не оказывается" in resolved.authored_service_alternative_block.approved_text
    assert resolved.authored_service_alternative_block.options == ()


def test_unknown_service_does_not_invent_alternative(tmp_path: Path) -> None:
    outcome = _runner(tmp_path).run_turn(
        TurnSpec(
            patient_message="Делаете гнатологию?",
            request_id="unknown-service",
            composer_json=_composer_dict(
                patient_text="Про гнатологию.",
                service_reference_kind="explicit_current",
                explicit_service_id="gnathology",
                requested_aspect_ids=["service_availability"],
            ),
        )
    )
    selection = outcome.pipeline.selection
    resolved = outcome.pipeline.materialized.resolved

    assert selection.reference_service_id is None
    assert resolved.authored_service_alternative_block is None
    assert resolved.finalized_commercial_ids.shown_service_option_ids == ()


def test_aligners_snapshot_persists_after_topic_null_commit_read(tmp_path: Path) -> None:
    runner = _runner(tmp_path)
    turn1 = runner.run_turn(
        _braces_turn(
            request_id="braces-memory-1",
            patient_message="Хочу брекеты",
            topic_id=None,
        )
    )
    assert turn1.pipeline.selection.resolved_topic_id == "orthodontics"
    assert turn1.pipeline.materialized.resolved.finalized_commercial_ids.shown_service_option_ids == (
        "aligners",
    )
    after_turn1 = runner.read().state
    assert after_turn1.shown_options_snapshot is not None
    assert after_turn1.shown_options_snapshot.topic_id == "orthodontics"
    assert after_turn1.shown_options_snapshot.service_ids == ("aligners",)
    assert after_turn1.active_service is None

    runner.run_turn(
        TurnSpec(
            patient_message="Продолжаем",
            request_id="braces-memory-2",
            composer_json=_composer_dict(
                patient_text="Спасибо.",
                topic_id="orthodontics",
                service_reference_kind="none",
            ),
        )
    )
    after_turn2 = runner.read().state
    assert after_turn2.active_service is None
    assert after_turn2.shown_options_snapshot is not None
    assert after_turn2.shown_options_snapshot.service_ids == ("aligners",)


def test_installment_positive_for_all_on_4(tmp_path: Path) -> None:
    outcome = _runner(tmp_path).run_turn(
        TurnSpec(
            patient_message="Можно в рассрочку на All-on-4?",
            request_id="installment-all-on-4",
            composer_json=_composer_dict(
                patient_text="Про рассрочку на All-on-4.",
                service_reference_kind="explicit_current",
                explicit_service_id="all_on_4",
                topic_id="implantation",
                requested_fact_ids=["installment_12"],
            ),
        )
    )
    resolved = outcome.pipeline.materialized.resolved
    bundle = load_response_schema_bundle(TARGET_ROOT)
    assert "installment_12" in resolved.finalized_commercial_ids.requested_fact_ids
    assert bundle.facts["installment_12"].text_fact in outcome.prepared.rendered_text


@pytest.mark.parametrize(
    ("service_id", "patient_message"),
    [
        ("caries", "Можно рассрочку на лечение кариеса?"),
        ("tooth_extraction", "Можно рассрочку на удаление зуба?"),
    ],
)
def test_installment_negative_for_excluded_services(
    tmp_path: Path,
    service_id: str,
    patient_message: str,
) -> None:
    negative_text = INSTALLMENT_NEGATIVE_SCOPE
    outcome = _runner(tmp_path).run_turn(
        TurnSpec(
            patient_message=patient_message,
            request_id=f"installment-{service_id}",
            composer_json=_composer_dict(
                patient_text=negative_text,
                service_reference_kind="explicit_current",
                explicit_service_id=service_id,
                requested_fact_ids=["installment_12"],
            ),
        )
    )
    resolved = outcome.pipeline.materialized.resolved
    assert "installment_12" not in resolved.finalized_commercial_ids.requested_fact_ids
    assert negative_text in outcome.prepared.rendered_text
    assert "requested_fact_inapplicable" in {
        item.code for item in outcome.pipeline.selection.diagnostics
    }


def test_installment_negative_rule_visible_in_composer_sidecar() -> None:
    installment = _installment_sidecar_fact()
    assert installment["excluded_service_ids"] == ["caries", "tooth_extraction"]
    assert installment["excluded_scope_text"] == INSTALLMENT_NEGATIVE_SCOPE


def test_installment_negative_rule_absent_without_demo_metadata() -> None:
    base = load_response_schema_bundle(TARGET_ROOT)
    facts = dict(base.facts)
    facts["installment_12"] = facts["installment_12"].model_copy(
        update={"excluded_service_ids": [], "excluded_scope_text": None}
    )
    bundle = base.model_copy(update={"facts": facts})
    installment = _installment_sidecar_fact(bundle=bundle)
    assert installment["excluded_service_ids"] == []
    assert installment["excluded_scope_text"] is None


def test_authored_group_text_used_when_all_alternatives_available(tmp_path: Path) -> None:
    inactive_id = "policy_dual_alt"
    bundle = _bundle_with_inactive(inactive_id, name="Dual alt test")
    row = AuthoredServiceAlternative(
        requested_service_id=inactive_id,
        alternative_service_ids=("aligners",),
        approved_text=BRACES_APPROVED,
    )
    ctx = _demo_context_for_bundle(bundle)
    with patch(POLICY_PATCH, return_value=(row,)):
        outcome = _runner(tmp_path, ctx=ctx).run_turn(
            _inactive_turn(
                inactive_service_id=inactive_id,
                request_id="authored-full",
                patient_message="Нужна услуга",
            )
        )
    block = outcome.pipeline.materialized.resolved.authored_service_alternative_block
    assert block is not None
    assert block.approved_text == BRACES_APPROVED
    assert outcome.pipeline.selection.resolved_topic_id == "orthodontics"


def test_authored_group_text_dropped_when_alternative_filtered(tmp_path: Path) -> None:
    inactive_id = "policy_partial_alt"
    bundle = _bundle_with_inactive(inactive_id, name="Partial alt test")
    row = AuthoredServiceAlternative(
        requested_service_id=inactive_id,
        alternative_service_ids=("aligners", "missing_alt"),
        approved_text=GROUP_ALT_TEXT,
    )
    ctx = _demo_context_for_bundle(bundle)
    with patch(POLICY_PATCH, return_value=(row,)):
        outcome = _runner(tmp_path, ctx=ctx).run_turn(
            _inactive_turn(
                inactive_service_id=inactive_id,
                request_id="authored-partial",
                patient_message="Нужна услуга",
            )
        )
    rendered = outcome.prepared.rendered_text
    block = outcome.pipeline.materialized.resolved.authored_service_alternative_block
    assert block is not None
    assert GROUP_ALT_TEXT not in rendered
    assert "не оказывается" in block.approved_text
    assert block.options[0].service_id == "aligners"
    assert "missing_alt" not in rendered


def test_authored_all_alternatives_unavailable_has_no_options(tmp_path: Path) -> None:
    inactive_id = "policy_no_alt"
    bundle = _bundle_with_inactive(inactive_id, name="No alt test")
    row = AuthoredServiceAlternative(
        requested_service_id=inactive_id,
        alternative_service_ids=("missing_a", "missing_b"),
        approved_text=GROUP_ALT_TEXT,
    )
    ctx = _demo_context_for_bundle(bundle)
    with patch(POLICY_PATCH, return_value=(row,)):
        outcome = _runner(tmp_path, ctx=ctx).run_turn(
            _inactive_turn(
                inactive_service_id=inactive_id,
                request_id="authored-none",
                patient_message="Нужна услуга",
            )
        )
    resolved = outcome.pipeline.materialized.resolved
    assert resolved.authored_service_alternative_block is not None
    assert resolved.authored_service_alternative_block.options == ()
    assert GROUP_ALT_TEXT not in outcome.prepared.rendered_text


@pytest.mark.parametrize("composer_topic_id", [None, "orthodontics", "implantation"])
def test_authored_mixed_topic_alternatives_do_not_bind_snapshot_by_conversation_topic(
    tmp_path: Path,
    composer_topic_id: str | None,
) -> None:
    inactive_id = "policy_mixed_topic"
    bundle = _bundle_with_inactive(inactive_id, name="Mixed topic test")
    row = AuthoredServiceAlternative(
        requested_service_id=inactive_id,
        alternative_service_ids=("aligners", "all_on_4"),
        approved_text=GROUP_ALT_TEXT,
    )
    ctx = _demo_context_for_bundle(bundle)
    runner = _runner(tmp_path, ctx=ctx)
    with patch(POLICY_PATCH, return_value=(row,)):
        outcome = runner.run_turn(
            _inactive_turn(
                inactive_service_id=inactive_id,
                request_id=f"authored-mixed-topic-{composer_topic_id or 'null'}",
                patient_message="Нужна услуга",
                topic_id=composer_topic_id,
            )
        )
    selection = outcome.pipeline.selection
    block = outcome.pipeline.materialized.resolved.authored_service_alternative_block
    assert block is not None
    assert block.options_unambiguous_topic_id is None
    assert tuple(option.service_id for option in block.options) == ("aligners", "all_on_4")
    assert outcome.pipeline.materialized.resolved.session_delta.active_service_id is None
    if composer_topic_id is None:
        assert selection.resolved_topic_id is None
        assert selection.response_scope == "clinic"
    else:
        assert selection.resolved_topic_id == composer_topic_id
    after = runner.read().state
    assert after.shown_options_snapshot is None
    assert after.active_service is None


def test_authored_mixed_topic_alternatives_reorder_does_not_create_snapshot(tmp_path: Path) -> None:
    inactive_id = "policy_mixed_topic"
    bundle = _bundle_with_inactive(inactive_id, name="Mixed topic test")
    ctx = _demo_context_for_bundle(bundle)
    runner = _runner(tmp_path, ctx=ctx)
    with patch(POLICY_PATCH, return_value=(AuthoredServiceAlternative(
        requested_service_id=inactive_id,
        alternative_service_ids=("all_on_4", "aligners"),
        approved_text=GROUP_ALT_TEXT,
    ),)):
        reordered = runner.run_turn(
            _inactive_turn(
                inactive_service_id=inactive_id,
                request_id="authored-mixed-topic-reordered",
                patient_message="Повтор",
            )
        )
    assert reordered.pipeline.materialized.resolved.authored_service_alternative_block.options_unambiguous_topic_id is None
    assert runner.read().state.shown_options_snapshot is None


def test_authored_two_same_topic_alternatives_resolve_common_topic(tmp_path: Path) -> None:
    inactive_id = "policy_same_topic"
    base = load_response_schema_bundle(TARGET_ROOT)
    services = dict(base.services)
    services[inactive_id] = TargetService(
        name="Same topic test",
        aliases=[],
        family="orthodontics",
        roles=[],
        active=False,
        selection={"mode": "context"},
        options=[],
    )
    services["aligners_b"] = services["aligners"].model_copy(update={"name": "Элайнеры B"})
    bundle = base.model_copy(update={"services": services})
    row = AuthoredServiceAlternative(
        requested_service_id=inactive_id,
        alternative_service_ids=("aligners", "aligners_b"),
        approved_text=GROUP_ALT_TEXT,
    )
    ctx = _demo_context_for_bundle(bundle)
    with patch(POLICY_PATCH, return_value=(row,)):
        outcome = _runner(tmp_path, ctx=ctx).run_turn(
            _inactive_turn(
                inactive_service_id=inactive_id,
                request_id="authored-same-topic",
                patient_message="Нужна услуга",
            )
        )
    assert outcome.pipeline.selection.resolved_topic_id == "orthodontics"
    block = outcome.pipeline.materialized.resolved.authored_service_alternative_block
    assert block is not None
    assert block.approved_text == GROUP_ALT_TEXT
    assert block.options_unambiguous_topic_id == "orthodontics"
    assert tuple(option.service_id for option in block.options) == ("aligners", "aligners_b")


def test_installment_general_clinic_scope(tmp_path: Path) -> None:
    outcome = _runner(tmp_path).run_turn(
        TurnSpec(
            patient_message="Есть рассрочка?",
            request_id="installment-general",
            composer_json=_composer_dict(
                patient_text="Общий вопрос про рассрочку.",
                topic_id=None,
                requested_fact_ids=["installment_12"],
            ),
        )
    )
    resolved = outcome.pipeline.materialized.resolved
    bundle = load_response_schema_bundle(TARGET_ROOT)
    assert "installment_12" in resolved.finalized_commercial_ids.requested_fact_ids
    assert bundle.facts["installment_12"].text_fact in outcome.prepared.rendered_text


def test_warranty_topic_scope_without_forced_service(tmp_path: Path) -> None:
    outcome = _runner(tmp_path).run_turn(
        TurnSpec(
            patient_message="Какая гарантия на имплантацию?",
            request_id="warranty-topic",
            composer_json=_composer_dict(
                patient_text="Про гарантию на имплантацию.",
                topic_id="implantation",
                requested_fact_ids=["implant_warranty"],
            ),
        )
    )
    resolved = outcome.pipeline.materialized.resolved
    bundle = load_response_schema_bundle(TARGET_ROOT)
    assert resolved.response_scope == "topic"
    assert resolved.session_delta.active_service_id is None
    assert "implant_warranty" in resolved.finalized_commercial_ids.requested_fact_ids
    assert bundle.facts["implant_warranty"].text_fact in outcome.prepared.rendered_text


def test_warranty_not_automatic_on_overview(tmp_path: Path) -> None:
    outcome = _runner(tmp_path).run_turn(
        TurnSpec(
            patient_message="Расскажите про All-on-4",
            request_id="warranty-no-auto",
            composer_json=_composer_dict(
                patient_text="Обзор All-on-4.",
                service_reference_kind="explicit_current",
                explicit_service_id="all_on_4",
                topic_id="implantation",
                requested_aspect_ids=["overview"],
            ),
        )
    )
    finalized = outcome.pipeline.materialized.resolved.finalized_commercial_ids
    assert "implant_warranty" not in finalized.requested_fact_ids
    assert "implant_warranty" not in finalized.promo_fact_ids
    assert "implant_warranty" not in finalized.amplifier_fact_ids
