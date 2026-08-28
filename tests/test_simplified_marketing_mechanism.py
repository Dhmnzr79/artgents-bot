"""Matrix tests for simplified automatic marketing (checkpoint mechanism)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from contracts.response_schema import ResponseSchemaBundle
from contracts.response_schema_refs import (
    ResponseSchemaExternalIndex,
    validate_response_schema_external_refs,
)
from contracts.doctor_schema_refs import build_doctor_source_refs
from core.doctor_schema_loader import load_doctor_catalog
from core.response_schema_kb_index import build_response_schema_kb_refs
from core.response_schema_loader import load_response_schema_bundle
from core.target_marketing_selector import select_stage51_marketing
from core.target_runtime_session import (
    read_target_runtime_session,
    write_target_runtime_session_after_materialized,
)
from core.target_response_verifier import TargetVerifiedComposedResponse
from contracts.turn_frame import TurnFrame

TODAY = date(2026, 7, 21)
DEMO_ROOT = Path("clients/demo")
TARGET_ROOT = DEMO_ROOT / "target_response"
MD_ROOT = DEMO_ROOT / "md"
DOCTOR_CATALOG_PATH = DEMO_ROOT / "doctor_catalog.json"


def _marketing_bundle(
  *,
  promo_ids: tuple[str, ...] = ("promo_a", "promo_b", "promo_c"),
  amplifier_ids: tuple[str, ...] = ("installment", "tax"),
  service_id: str = "svc",
  service_value_id: str | None = None,
) -> ResponseSchemaBundle:
    facts: dict[str, object] = {}
    for pid in promo_ids:
        facts[pid] = {
            "id": pid,
            "kind": "promo",
            "catalog_label": pid,
            "text_fact": f"Promo text {pid}.",
            "render_mode": "strict",
            "active": True,
            "allowed_service_ids": [service_id],
        }
    for aid in amplifier_ids:
        facts[aid] = {
            "id": aid,
            "kind": "payment" if aid == "installment" else "benefit",
            "catalog_label": aid,
            "text_fact": f"Amplifier text {aid}.",
            "render_mode": "strict",
            "active": True,
            "allowed_service_ids": [service_id],
        }
    if service_value_id:
        facts[service_value_id] = {
            "id": service_value_id,
            "kind": "service_value",
            "catalog_label": service_value_id,
            "text_fact": f"Service value {service_value_id}.",
            "render_mode": "strict",
            "active": True,
            "allowed_service_ids": [service_id],
        }
    service_payload: dict[str, object] = {
        "name": "Svc",
        "family": "implantology",
        "roles": ["protocol"],
        "active": True,
        "selection": {"mode": "context"},
    }
    if service_value_id:
        service_payload["service_value_ref"] = f"fact:{service_value_id}"
    return ResponseSchemaBundle.model_validate(
        {
            "services": {service_id: service_payload},
            "brands": {"version": 1, "brands": {}},
            "offers": [],
            "facts": facts,
            "strategy": {"version": 1, "default_max_options": 3, "rules": []},
            "marketing": {
                "version": 1,
                "limits": {
                    "max_scenarios_per_turn": 2,
                    "service": {
                        "max_promos_per_turn": 2,
                        "max_amplifiers_per_turn": 2,
                    },
                    "price": {
                        "max_promos_per_turn": 2,
                        "max_amplifiers_per_turn": 4,
                    },
                },
                "initial_commercial_blocks": {
                    "service": {
                        "ordered_fact_refs": [f"fact:{pid}" for pid in promo_ids],
                    }
                },
                "ordered_amplifier_refs": [f"fact:{aid}" for aid in amplifier_ids],
                "cta_contexts": {"service": "plan", "default": "callback"},
            },
        }
    )


def _empty_index() -> ResponseSchemaExternalIndex:
    return ResponseSchemaExternalIndex(kb_refs=(), doctor_refs=())


def _empty_doctors():
    from contracts.doctor_schema import TargetDoctorCatalog

    return TargetDoctorCatalog.model_validate({"doctors": {}})


def _select(**kwargs):
    bundle = kwargs.pop("bundle")
    today = kwargs.pop("today", TODAY)
    service_id = kwargs.pop("service_id", "svc")
    semantic_context = kwargs.pop("semantic_context", "service")
    return select_stage51_marketing(
        bundle,
        _empty_doctors(),
        _empty_index(),
        route="ANSWER",
        commercial_intent="none",
        promotion_scope="none",
        semantic_context=semantic_context,
        service_id=service_id,
        today=today,
        **kwargs,
    )


# --- A. Selection matrix ---


def test_two_promos_and_installment_selects_two_promos_and_installment() -> None:
    outcome = _select(bundle=_marketing_bundle())
    assert outcome.selection is not None
    refs = outcome.selection.selected_refs
    assert refs == ("fact:promo_a", "fact:promo_b")
    assert outcome.selection.amplifier_refs == ("fact:installment", "fact:tax")


def test_one_promo_shown_selects_second_promo_and_installment() -> None:
    outcome = _select(
        bundle=_marketing_bundle(promo_ids=("promo_a", "promo_b")),
        shown_fact_ids=("promo_a",),
    )
    assert outcome.selection is not None
    assert outcome.selection.selected_refs == ("fact:promo_b",)
    assert outcome.selection.amplifier_refs == ("fact:installment", "fact:tax")


def test_one_promo_available_plus_installment() -> None:
    bundle = _marketing_bundle(promo_ids=("promo_a",))
    outcome = _select(bundle=bundle)
    assert outcome.selection is not None
    assert outcome.selection.selected_refs == ("fact:promo_a",)
    assert outcome.selection.amplifier_refs == ("fact:installment", "fact:tax")


def test_no_promos_selects_two_amplifiers() -> None:
    bundle = _marketing_bundle(promo_ids=())
    outcome = _select(bundle=bundle)
    assert outcome.selection is not None
    assert outcome.selection.selected_refs == ()
    assert outcome.selection.amplifier_refs == ("fact:installment", "fact:tax")


def test_installment_shown_selects_next_amplifier() -> None:
    bundle = _marketing_bundle(promo_ids=())
    outcome = _select(bundle=bundle, shown_amplifier_refs=("fact:installment",))
    assert outcome.selection is not None
    assert outcome.selection.amplifier_refs == ("fact:tax",)


def test_one_promo_expired_other_plus_installment() -> None:
    bundle = _marketing_bundle(promo_ids=("promo_a", "promo_b"))
    bundle.facts["promo_a"].active_until = "2026-07-20"
    outcome = _select(bundle=bundle, today=date(2026, 7, 21))
    assert outcome.selection is not None
    assert outcome.selection.selected_refs == ("fact:promo_b",)
    assert outcome.selection.amplifier_refs == ("fact:installment", "fact:tax")


def test_one_promo_wrong_service_other_plus_installment() -> None:
    bundle = _marketing_bundle(promo_ids=("promo_a", "promo_b"))
    bundle.facts["promo_a"].allowed_service_ids = ["other_svc"]
    outcome = _select(bundle=bundle)
    assert outcome.selection is not None
    assert outcome.selection.selected_refs == ("fact:promo_b",)
    assert outcome.selection.amplifier_refs == ("fact:installment", "fact:tax")


def test_incompatible_promos_select_compatible_amplifier() -> None:
    bundle = _marketing_bundle(promo_ids=("promo_a", "promo_b"))
    bundle.facts["promo_b"].incompatible_with = ["promo_a"]
    outcome = _select(bundle=bundle)
    assert outcome.selection is not None
    assert outcome.selection.selected_refs == ("fact:promo_a",)
    assert outcome.selection.amplifier_refs == ("fact:installment", "fact:tax")


def test_both_promos_unavailable_selects_two_amplifiers() -> None:
    bundle = _marketing_bundle(promo_ids=("promo_a", "promo_b"))
    outcome = _select(
        bundle=bundle,
        shown_fact_ids=("promo_a", "promo_b"),
    )
    assert outcome.selection is not None
    assert outcome.selection.selected_refs == ()
    assert outcome.selection.amplifier_refs == ("fact:installment", "fact:tax")


def test_expired_promo_skipped() -> None:
    bundle = _marketing_bundle()
    bundle.facts["promo_a"].active_until = "2026-07-20"
    outcome = _select(bundle=bundle, today=date(2026, 7, 21))
    assert outcome.selection is not None
    assert "fact:promo_a" not in outcome.selection.selected_refs


def test_no_candidates_returns_empty_selection() -> None:
    bundle = _marketing_bundle(promo_ids=(), amplifier_ids=())
    outcome = _select(bundle=bundle)
    assert outcome.selection is not None
    assert outcome.selection.selected_refs == ()


# --- B. service_value ---


def test_service_value_separate_from_commercial_quota() -> None:
    bundle = _marketing_bundle(service_value_id="sv_fact")
    outcome = _select(bundle=bundle)
    assert outcome.selection is not None
    assert outcome.selection.service_value_ref == "fact:sv_fact"
    assert len(outcome.selection.selected_refs) == 2
    assert len(outcome.selection.amplifier_refs) == 2


def test_service_value_not_repeated() -> None:
    bundle = _marketing_bundle(service_value_id="sv_fact")
    outcome = _select(bundle=bundle, shown_service_value_ids=("sv_fact",))
    assert outcome.selection is not None
    assert outcome.selection.service_value_ref is None


def test_missing_service_value_ref_does_not_break() -> None:
    outcome = _select(bundle=_marketing_bundle())
    assert outcome.selection is not None


# --- C. Consultation / direct ---


def test_direct_fact_bypasses_shown_suppression() -> None:
    bundle = _marketing_bundle(promo_ids=("promo_a",))
    outcome = _select(
        bundle=bundle,
        shown_fact_ids=("promo_a",),
        direct_requested_fact_ref="fact:promo_a",
    )
    assert outcome.selection is not None
    assert "fact:promo_a" in outcome.selection.selected_refs


def test_present_fact_in_answer_excluded_from_auto() -> None:
    outcome = _select(
        bundle=_marketing_bundle(),
        present_fact_ids=("promo_a",),
    )
    assert outcome.selection is not None
    assert "fact:promo_a" not in outcome.selection.selected_refs
    assert outcome.selection.selected_refs[0] == "fact:promo_b"


def _bundle_with_incompatible_promos() -> ResponseSchemaBundle:
    bundle = _marketing_bundle(promo_ids=("promo_a", "promo_b"))
    facts = dict(bundle.facts)
    facts["promo_b"] = facts["promo_b"].model_copy(
        update={"incompatible_with": ["promo_a"]},
    )
    return bundle.model_copy(update={"facts": facts})


def _select_promotion(**kwargs):
    bundle = kwargs.pop("bundle")
    today = kwargs.pop("today", TODAY)
    return select_stage51_marketing(
        bundle,
        _empty_doctors(),
        _empty_index(),
        route="ANSWER",
        commercial_intent="promotion",
        promotion_scope="service",
        semantic_context="service",
        service_id="svc",
        today=today,
        **kwargs,
    )


def test_direct_service_promotion_lists_incompatible_alternatives() -> None:
    bundle = _bundle_with_incompatible_promos()
    outcome = _select_promotion(bundle=bundle)
    assert outcome.selection is not None
    assert outcome.selection.selected_refs == ("fact:promo_a", "fact:promo_b")


def test_direct_fact_blocks_incompatible_auto_candidate() -> None:
    bundle = _bundle_with_incompatible_promos()
    outcome = _select(bundle=bundle, present_fact_ids=("promo_a",))
    assert outcome.selection is not None
    assert "fact:promo_a" not in outcome.selection.selected_refs
    assert outcome.selection.amplifier_refs == ("fact:installment", "fact:tax")


def test_bidirectional_incompatibility_direct_and_auto() -> None:
    bundle = _marketing_bundle(promo_ids=("promo_a", "promo_b"))
    facts = dict(bundle.facts)
    facts["promo_a"] = facts["promo_a"].model_copy(
        update={"incompatible_with": ["promo_b"]},
    )
    facts["promo_b"] = facts["promo_b"].model_copy(
        update={"incompatible_with": ["promo_a"]},
    )
    bundle = bundle.model_copy(update={"facts": facts})
    direct = _select_promotion(bundle=bundle)
    assert direct.selection is not None
    assert direct.selection.selected_refs == ("fact:promo_a", "fact:promo_b")
    auto = _select(bundle=bundle, present_fact_ids=("promo_a",))
    assert auto.selection is not None
    assert "fact:promo_b" not in auto.selection.selected_refs


def test_direct_fact_not_duplicated_by_automatic_insert() -> None:
    bundle = _marketing_bundle(promo_ids=("promo_a", "promo_b"))
    outcome = _select(bundle=bundle, present_fact_ids=("promo_a",))
    assert outcome.selection is not None
    assert outcome.selection.selected_refs.count("fact:promo_a") == 0


def test_two_slot_limit_applies_to_automatic_not_direct_promotion() -> None:
    bundle = _marketing_bundle(promo_ids=("promo_a", "promo_b", "promo_c"))
    outcome = _select_promotion(bundle=bundle)
    assert outcome.selection is not None
    assert len(outcome.selection.selected_refs) == 3
    auto = _select(bundle=bundle)
    assert auto.selection is not None
    assert len(auto.selection.selected_refs) == 2


def test_unknown_direct_fact_id_not_used_as_compatibility_context() -> None:
    bundle = _bundle_with_incompatible_promos()
    baseline = _select(bundle=bundle)
    with_unknown = _select(bundle=bundle, present_fact_ids=("missing_promo",))
    assert baseline.selection is not None
    assert with_unknown.selection is not None
    assert with_unknown.selection.selected_refs == baseline.selection.selected_refs


def _bundle_with_direct_anchor_and_amplifiers(
    *,
    direct_incompatible_with: list[str] | None = None,
    installment_incompatible_with: list[str] | None = None,
    promo_ids: tuple[str, ...] = (),
) -> ResponseSchemaBundle:
    bundle = _marketing_bundle(promo_ids=promo_ids, amplifier_ids=("installment", "tax"))
    facts = dict(bundle.facts)
    facts["direct_anchor"] = {
        "id": "direct_anchor",
        "kind": "promo",
        "catalog_label": "direct_anchor",
        "text_fact": "Direct anchor promo.",
        "render_mode": "strict",
        "active": True,
        "allowed_service_ids": ["svc"],
        "incompatible_with": direct_incompatible_with or [],
    }
    if installment_incompatible_with is not None:
        facts["installment"] = facts["installment"].model_copy(
            update={"incompatible_with": installment_incompatible_with},
        )
    return ResponseSchemaBundle.model_validate(
        bundle.model_dump(mode="python") | {"facts": facts}
    )


def test_direct_fact_blocks_first_incompatible_amplifier_without_auto_promos() -> None:
    bundle = _bundle_with_direct_anchor_and_amplifiers(
        direct_incompatible_with=["installment"],
    )
    outcome = _select(bundle=bundle, present_fact_ids=("direct_anchor",))
    assert outcome.selection is not None
    assert outcome.selection.amplifier_refs == ("fact:tax",)
    assert "fact:installment" not in outcome.selection.amplifier_refs


def test_direct_fact_blocks_incompatible_amplifier_with_one_auto_promo() -> None:
    bundle = _bundle_with_direct_anchor_and_amplifiers(
        direct_incompatible_with=["installment"],
        promo_ids=("promo_a",),
    )
    outcome = _select(bundle=bundle, present_fact_ids=("direct_anchor",))
    assert outcome.selection is not None
    assert outcome.selection.selected_refs == ("fact:promo_a",)
    assert outcome.selection.amplifier_refs == ("fact:tax",)
    assert "fact:installment" not in outcome.selection.amplifier_refs


def test_compatible_amplifier_fills_free_slot_after_incompatible_skipped() -> None:
    bundle = _marketing_bundle(
        promo_ids=(),
        amplifier_ids=("installment", "blocked_amp", "tax"),
    )
    facts = dict(bundle.facts)
    facts["direct_anchor"] = {
        "id": "direct_anchor",
        "kind": "promo",
        "catalog_label": "direct_anchor",
        "text_fact": "Direct anchor promo.",
        "render_mode": "strict",
        "active": True,
        "allowed_service_ids": ["svc"],
        "incompatible_with": ["blocked_amp"],
    }
    bundle = ResponseSchemaBundle.model_validate(
        bundle.model_dump(mode="python") | {"facts": facts}
    )
    outcome = _select(bundle=bundle, present_fact_ids=("direct_anchor",))
    assert outcome.selection is not None
    assert outcome.selection.amplifier_refs == ("fact:installment", "fact:tax")
    assert "fact:blocked_amp" not in outcome.selection.amplifier_refs


def test_direct_fact_side_incompatibility_blocks_amplifier() -> None:
    bundle = _bundle_with_direct_anchor_and_amplifiers(
        direct_incompatible_with=["installment"],
        installment_incompatible_with=[],
    )
    outcome = _select(bundle=bundle, present_fact_ids=("direct_anchor",))
    assert outcome.selection is not None
    assert "fact:installment" not in outcome.selection.amplifier_refs


def test_amplifier_side_incompatibility_blocks_against_direct_fact() -> None:
    bundle = _bundle_with_direct_anchor_and_amplifiers(
        direct_incompatible_with=[],
        installment_incompatible_with=["direct_anchor"],
    )
    outcome = _select(bundle=bundle, present_fact_ids=("direct_anchor",))
    assert outcome.selection is not None
    assert "fact:installment" not in outcome.selection.amplifier_refs
    assert outcome.selection.amplifier_refs == ("fact:tax",)


# --- D. Demo bundle smoke ---


def test_demo_bundle_loads_with_ordered_amplifier_refs() -> None:
    bundle = load_response_schema_bundle(TARGET_ROOT)
    assert bundle.marketing.limits.service is not None
    assert bundle.marketing.limits.service.max_promos_per_turn == 2
    assert bundle.marketing.limits.price is not None
    assert bundle.marketing.limits.price.max_amplifiers_per_turn == 4
    assert bundle.marketing.ordered_amplifier_refs[0] == "fact:installment_12"
    assert "fact:implant_warranty" not in bundle.marketing.ordered_amplifier_refs


def test_demo_all_on_4_automatic_two_promos_and_installment() -> None:
    bundle = load_response_schema_bundle(TARGET_ROOT)
    doctors = load_doctor_catalog(DOCTOR_CATALOG_PATH)
    kb_refs = build_response_schema_kb_refs(MD_ROOT)
    external_index = ResponseSchemaExternalIndex(
        kb_refs=kb_refs,
        doctor_refs=build_doctor_source_refs(doctors),
    )
    assert validate_response_schema_external_refs(bundle, external_index) is None
    outcome = select_stage51_marketing(
        bundle,
        doctors,
        external_index,
        route="ANSWER",
        commercial_intent="none",
        promotion_scope="none",
        semantic_context="service",
        service_id="all_on_4",
        today=TODAY,
        turn_topic="implantation",
    )
    assert outcome.selection is not None
    refs = outcome.selection.selected_refs
    assert len(refs) == 2
    assert outcome.selection.amplifier_refs == ("fact:installment_12", "fact:tax_deduction")


def test_marketing_session_isolation_via_widget_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app as app_module
    from core.target_runtime_session import read_target_runtime_session
    from tests.test_sales_fast_widget_integration import (
        _run_widget_turn_with_envelope,
    )
    from tests.test_sales_one_plus_turn import answer_envelope

    sid_demo = "mkt-isolation-demo"
    sid_nika = "mkt-isolation-nika"
    _run_widget_turn_with_envelope(
        monkeypatch,
        client_id="demo",
        sid=sid_demo,
        user_message="Расскажите про All-on-4",
        envelope_json=answer_envelope(
            "All-on-4 — протокол.",
            service_id="all_on_4",
            commercial_intent="none",
        ),
        flask_app=app_module.app,
    )
    demo_session = read_target_runtime_session(sid_demo)
    assert demo_session.shown_fact_ids

    _run_widget_turn_with_envelope(
        monkeypatch,
        client_id="nikadent",
        sid=sid_nika,
        user_message="Что такое All-on-4?",
        envelope_json=answer_envelope(
            "All-on-4 — протокол.",
            service_id="all_on_4",
            commercial_intent="none",
        ),
        flask_app=app_module.app,
    )
    nika_session = read_target_runtime_session(sid_nika)
    assert not set(demo_session.shown_fact_ids).intersection(nika_session.shown_fact_ids)


def test_orchestrate_ask_resets_demo_session_after_nikadent_bind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import date

    from core.target_runtime_session import read_target_runtime_session
    from session import bind_session_client
    from tests.test_sales_fast_widget_integration import (
        _CountingBackend,
        _orchestrate_ask,
    )
    from tests.test_sales_one_plus_turn import answer_envelope

    sid = "orchestrate-demo-bind-regression"
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 7, 21),
    )
    monkeypatch.setattr(
        "core.sales_fast_widget_runtime.runtime_today",
        lambda: date(2026, 7, 21),
    )
    envelope = answer_envelope(
        "All-on-4 на нижнюю челюсть — 368 000 ₽.",
        commercial_intent="price",
        service_id="all_on_4",
        extent="full_arch",
        jaw="lower",
    )
    bind_session_client("demo")
    first = _orchestrate_ask(
        monkeypatch,
        backend=_CountingBackend(envelope),
        q="Сколько стоит All-on-4 на нижнюю челюсть?",
        sid=sid,
    )
    first_answer = str(first.get("answer") or "")
    assert "скидк" in first_answer.lower()
    assert "консультац" in first_answer.lower()
    assert "рассроч" in first_answer.lower()
    demo_session = read_target_runtime_session(sid)
    assert demo_session.shown_fact_ids

    bind_session_client("nikadent")
    second = _orchestrate_ask(
        monkeypatch,
        backend=_CountingBackend(envelope),
        q="Сколько стоит All-on-4 на нижнюю челюсть?",
        sid=sid,
    )
    second_answer = str(second.get("answer") or "")
    assert "скидк" in second_answer.lower()
    assert "консультац" in second_answer.lower()
    assert "рассроч" in second_answer.lower()
    assert "по этапам" in second_answer.lower()


# --- E. CP-MKT-1 profile limits and per-service policy ---


def _profile_policy_bundle() -> ResponseSchemaBundle:
    facts = {
        "promo_a": {
            "id": "promo_a",
            "kind": "promo",
            "catalog_label": "promo_a",
            "text_fact": "Promo text promo_a.",
            "render_mode": "strict",
            "active": True,
            "allowed_service_ids": ["svc_a", "svc_b"],
        },
        "installment": {
            "id": "installment",
            "kind": "payment",
            "catalog_label": "installment",
            "text_fact": "Amplifier text installment.",
            "render_mode": "strict",
            "active": True,
            "allowed_service_ids": ["svc_a", "svc_b"],
        },
        "tax": {
            "id": "tax",
            "kind": "benefit",
            "catalog_label": "tax",
            "text_fact": "Amplifier text tax.",
            "render_mode": "strict",
            "active": True,
            "allowed_service_ids": ["svc_a", "svc_b"],
        },
        "cost_fix": {
            "id": "cost_fix",
            "kind": "benefit",
            "catalog_label": "cost_fix",
            "text_fact": "Amplifier text cost_fix.",
            "render_mode": "strict",
            "active": True,
            "allowed_service_ids": ["svc_a", "svc_b"],
        },
        "direct_only": {
            "id": "direct_only",
            "kind": "benefit",
            "catalog_label": "direct_only",
            "text_fact": "Direct-only amplifier.",
            "render_mode": "strict",
            "active": True,
            "allowed_service_ids": ["svc_a"],
        },
    }
    service_payload = {
        "name": "Svc",
        "family": "implantology",
        "roles": ["protocol"],
        "active": True,
        "selection": {"mode": "context"},
    }
    return ResponseSchemaBundle.model_validate(
        {
            "services": {
                "svc_a": service_payload | {"name": "Svc A"},
                "svc_b": service_payload | {"name": "Svc B"},
            },
            "brands": {"version": 1, "brands": {}},
            "offers": [],
            "facts": facts,
            "strategy": {"version": 1, "default_max_options": 3, "rules": []},
            "marketing": {
                "version": 1,
                "limits": {
                    "max_scenarios_per_turn": 2,
                    "service": {
                        "max_promos_per_turn": 2,
                        "max_amplifiers_per_turn": 2,
                    },
                    "price": {
                        "max_promos_per_turn": 2,
                        "max_amplifiers_per_turn": 4,
                    },
                },
                "initial_commercial_blocks": {
                    "service": {"ordered_fact_refs": ["fact:promo_a"]},
                },
                "ordered_amplifier_refs": [
                    "fact:installment",
                    "fact:tax",
                    "fact:cost_fix",
                    "fact:direct_only",
                ],
                "service_automatic_commercial": {
                    "svc_a": {
                        "service": {
                            "ordered_amplifier_refs": ["fact:tax"],
                        },
                        "price": {
                            "ordered_amplifier_refs": [
                                "fact:tax",
                                "fact:cost_fix",
                            ],
                        },
                    },
                    "svc_b": {
                        "service": {
                            "ordered_amplifier_refs": [
                                "fact:tax",
                                "fact:cost_fix",
                            ],
                        },
                        "price": {
                            "ordered_amplifier_refs": ["fact:tax"],
                        },
                    },
                },
                "cta_contexts": {"service": "plan", "price": "price", "default": "callback"},
            },
        }
    )


def test_two_promos_do_not_reduce_amplifier_quota() -> None:
    bundle = _marketing_bundle(promo_ids=("promo_a", "promo_b", "promo_c"))
    outcome = _select(bundle=bundle)
    assert outcome.selection is not None
    assert len(outcome.selection.selected_refs) == 2
    assert len(outcome.selection.amplifier_refs) == 2


def test_price_profile_allows_four_amplifiers() -> None:
    bundle = _marketing_bundle(
        promo_ids=(),
        amplifier_ids=("installment", "tax", "amp3", "amp4", "amp5"),
    )
    facts = dict(bundle.facts)
    for amp_id in ("amp3", "amp4", "amp5"):
        facts[amp_id] = {
            "id": amp_id,
            "kind": "benefit",
            "catalog_label": amp_id,
            "text_fact": f"Amplifier text {amp_id}.",
            "render_mode": "strict",
            "active": True,
            "allowed_service_ids": ["svc"],
        }
    bundle = ResponseSchemaBundle.model_validate(
        bundle.model_dump(mode="python") | {"facts": facts}
    )
    outcome = select_stage51_marketing(
        bundle,
        _empty_doctors(),
        _empty_index(),
        route="ANSWER",
        commercial_intent="none",
        promotion_scope="none",
        semantic_context="price",
        service_id="svc",
        today=TODAY,
    )
    assert outcome.selection is not None
    assert outcome.selection.service_value_ref is None
    assert len(outcome.selection.amplifier_refs) == 4


def test_cost_fix_allowed_for_service_on_svc_b_but_price_only_on_svc_a() -> None:
    bundle = _profile_policy_bundle()
    svc_b_service = select_stage51_marketing(
        bundle,
        _empty_doctors(),
        _empty_index(),
        route="ANSWER",
        commercial_intent="none",
        promotion_scope="none",
        semantic_context="service",
        service_id="svc_b",
        today=TODAY,
    )
    svc_a_service = select_stage51_marketing(
        bundle,
        _empty_doctors(),
        _empty_index(),
        route="ANSWER",
        commercial_intent="none",
        promotion_scope="none",
        semantic_context="service",
        service_id="svc_a",
        today=TODAY,
    )
    svc_a_price = select_stage51_marketing(
        bundle,
        _empty_doctors(),
        _empty_index(),
        route="ANSWER",
        commercial_intent="none",
        promotion_scope="none",
        semantic_context="price",
        service_id="svc_a",
        today=TODAY,
    )
    assert svc_b_service.selection is not None
    assert "fact:cost_fix" in svc_b_service.selection.amplifier_refs
    assert svc_a_service.selection is not None
    assert "fact:cost_fix" not in svc_a_service.selection.amplifier_refs
    assert svc_a_price.selection is not None
    assert "fact:cost_fix" in svc_a_price.selection.amplifier_refs


def test_direct_only_fact_not_auto_shown_but_present_for_direct() -> None:
    bundle = _profile_policy_bundle()
    outcome = _select(
        bundle=bundle,
        service_id="svc_a",
        present_fact_ids=("direct_only",),
    )
    assert outcome.selection is not None
    assert "fact:direct_only" not in outcome.selection.amplifier_refs


def test_presentation_formats_amplifiers_as_bulleted_list() -> None:
    from types import SimpleNamespace

    from contracts.response_schema import TargetCommercialFact
    from core.sales_fast_presentation import (
        AUTOMATIC_AMPLIFIER_LIST_HEADER,
        supplement_sales_fast_patient_text_with_marketing,
    )
    from core.target_marketing_selector import TargetMarketingSelection

    bundle = _marketing_bundle(promo_ids=())
    installment = bundle.facts["installment"]
    tax = bundle.facts["tax"]
    materials = SimpleNamespace(
        marketing_selection=TargetMarketingSelection(
            applied_scenarios=(),
            selected_refs=(),
            amplifier_refs=("fact:installment", "fact:tax"),
            cta_key="plan",
        ),
        commercial_facts=(
            TargetCommercialFact.model_validate(installment.model_dump()),
            TargetCommercialFact.model_validate(tax.model_dump()),
        ),
    )
    bound = SimpleNamespace(package=SimpleNamespace(materials=materials))
    text = supplement_sales_fast_patient_text_with_marketing(
        patient_text="Основной ответ.",
        bound_package=bound,
        bundle=bundle,
    )
    assert AUTOMATIC_AMPLIFIER_LIST_HEADER in text
    assert "- Amplifier text installment." in text
    assert "- Amplifier text tax." in text
    assert text.index("Основной ответ.") < text.index(AUTOMATIC_AMPLIFIER_LIST_HEADER)


# --- F. CP-MKT-1 correction: direct promotion vs automatic allowlists ---


def _direct_auto_split_bundle() -> ResponseSchemaBundle:
    facts = {
        "promo_a": {
            "id": "promo_a",
            "kind": "promo",
            "catalog_label": "promo_a",
            "text_fact": "Direct-auto promo_a.",
            "render_mode": "strict",
            "active": True,
            "allowed_service_ids": ["svc"],
        },
        "promo_b": {
            "id": "promo_b",
            "kind": "promo",
            "catalog_label": "promo_b",
            "text_fact": "Direct-auto promo_b.",
            "render_mode": "strict",
            "active": True,
            "allowed_service_ids": ["svc"],
        },
        "promo_expired": {
            "id": "promo_expired",
            "kind": "promo",
            "catalog_label": "promo_expired",
            "text_fact": "Direct-auto promo_expired.",
            "render_mode": "strict",
            "active": True,
            "active_until": "2026-07-20",
            "allowed_service_ids": ["svc"],
        },
    }
    return ResponseSchemaBundle.model_validate(
        {
            "services": {
                "svc": {
                    "name": "Svc",
                    "family": "implantology",
                    "roles": ["protocol"],
                    "active": True,
                    "selection": {"mode": "context"},
                },
            },
            "brands": {"version": 1, "brands": {}},
            "offers": [],
            "facts": facts,
            "strategy": {"version": 1, "default_max_options": 3, "rules": []},
            "marketing": {
                "version": 1,
                "limits": {
                    "max_scenarios_per_turn": 2,
                    "service": {
                        "max_promos_per_turn": 2,
                        "max_amplifiers_per_turn": 2,
                    },
                    "price": {
                        "max_promos_per_turn": 2,
                        "max_amplifiers_per_turn": 4,
                    },
                },
                "initial_commercial_blocks": {
                    "service": {
                        "ordered_fact_refs": [
                            "fact:promo_a",
                            "fact:promo_b",
                            "fact:promo_expired",
                        ],
                    }
                },
                "service_automatic_commercial": {
                    "svc": {
                        "service": {
                            "ordered_promo_refs": [],
                            "ordered_amplifier_refs": [],
                        },
                        "price": {
                            "ordered_promo_refs": [],
                            "ordered_amplifier_refs": [],
                        },
                    }
                },
                "cta_contexts": {"service": "plan", "price": "price", "default": "callback"},
            },
        }
    )


def _select_promotion_service(bundle: ResponseSchemaBundle, **kwargs):
    today = kwargs.pop("today", TODAY)
    service_id = kwargs.pop("service_id", "svc")
    return select_stage51_marketing(
        bundle,
        _empty_doctors(),
        _empty_index(),
        route="ANSWER",
        commercial_intent="promotion",
        promotion_scope="service",
        semantic_context="service",
        service_id=service_id,
        today=today,
        **kwargs,
    )


def test_empty_auto_promo_list_blocks_automatic_but_not_direct() -> None:
    bundle = _direct_auto_split_bundle()
    auto = _select(bundle=bundle)
    direct = _select_promotion_service(bundle)
    assert auto.selection is not None
    assert auto.selection.selected_refs == ()
    assert direct.selection is not None
    assert direct.selection.selected_refs == ("fact:promo_a", "fact:promo_b")


def test_auto_promo_allowlist_is_subset_of_direct_pool() -> None:
    bundle = _direct_auto_split_bundle()
    marketing_payload = bundle.marketing.model_dump(mode="python")
    marketing_payload["service_automatic_commercial"] = {
        "svc": {
            "service": {
                "ordered_promo_refs": ["fact:promo_a"],
                "ordered_amplifier_refs": [],
            },
            "price": {
                "ordered_promo_refs": [],
                "ordered_amplifier_refs": [],
            },
        }
    }
    bundle = ResponseSchemaBundle.model_validate(
        bundle.model_dump(mode="python") | {"marketing": marketing_payload}
    )
    auto = _select(bundle=bundle)
    direct = _select_promotion_service(bundle)
    assert auto.selection is not None
    assert auto.selection.selected_refs == ("fact:promo_a",)
    assert direct.selection is not None
    assert direct.selection.selected_refs == ("fact:promo_a", "fact:promo_b")


def test_expired_promo_excluded_from_direct_service_promotion() -> None:
    bundle = _direct_auto_split_bundle()
    outcome = _select_promotion_service(bundle, today=date(2026, 7, 21))
    assert outcome.selection is not None
    assert "fact:promo_expired" not in outcome.selection.selected_refs


def test_empty_price_profile_auto_lists_block_automatic_promos() -> None:
    bundle = _direct_auto_split_bundle()
    outcome = select_stage51_marketing(
        bundle,
        _empty_doctors(),
        _empty_index(),
        route="ANSWER",
        commercial_intent="none",
        promotion_scope="none",
        semantic_context="price",
        service_id="svc",
        today=TODAY,
    )
    assert outcome.selection is not None
    assert outcome.selection.selected_refs == ()


def test_missing_profile_block_keeps_global_automatic_promos() -> None:
    bundle = _marketing_bundle(promo_ids=("promo_a", "promo_b", "promo_c"))
    outcome = _select(bundle=bundle)
    assert outcome.selection is not None
    assert len(outcome.selection.selected_refs) == 2


def test_three_eligible_promos_automatically_capped_at_two() -> None:
    bundle = _marketing_bundle(promo_ids=("promo_a", "promo_b", "promo_c"))
    outcome = _select(bundle=bundle)
    assert outcome.selection is not None
    assert len(outcome.selection.selected_refs) == 2
    direct = _select_promotion_service(bundle)
    assert direct.selection is not None
    assert len(direct.selection.selected_refs) == 3


def test_legacy_nikadent_limits_normalize_to_agreed_caps() -> None:
    from pathlib import Path

    from core.response_schema_loader import load_response_schema_bundle

    bundle = load_response_schema_bundle(Path("clients/nikadent/target_response"))
    assert bundle.marketing.limits.profile_limits("service") == (2, 2)
    assert bundle.marketing.limits.profile_limits("price") == (2, 2)


def test_demo_limits_load_with_profile_caps() -> None:
    bundle = load_response_schema_bundle(TARGET_ROOT)
    assert bundle.marketing.limits.profile_limits("service") == (2, 2)
    assert bundle.marketing.limits.profile_limits("price") == (2, 4)
