"""COMPLETION checker and acceptance tests for FULLCONTEXT_PRESENTATION_PARITY."""

from __future__ import annotations

from pathlib import Path

from contracts.target_response_spec import TargetResponseSpec
from contracts.ui_scope_action import build_ui_scope_ref
from core.response_schema_loader import load_response_schema_bundle
from core.target_client_ui_nav import TargetNavigationFollowup
from core.target_presentation_decision import (
    CHOICE_MENU_MAX,
    SECONDARY_CONTENT_MAX,
    TargetPresentationCadenceState,
    decide_target_presentation,
)
from core.target_presentation_source_identity import is_valid_content_ref
from core.target_presentation_turn_projection import (
    derive_marketing_scenarios,
    resolve_target_semantic_context,
)
from core.target_response_followup_materializer import TargetContentFollowup
from core.target_response_followup_policy import TargetResponseFollowupSelection
from evals.v5.final_scope_widget_e2e_live_contract import FROZEN_TURNS_HASH, sha256_file_hex
from evals.v5.final_scope_widget_e2e_retry4_live_contract import (
    assert_frozen_retry4_live_artifacts_unchanged,
)
from tests.test_ac3_scope_price_flow_offline import test_w1b_snapshot_checksums_unchanged
from tests.test_final_price_scope_coverage_nav_implementation import (
    test_frozen_pins_unchanged as test_pscn_frozen_pins_unchanged,
)
from tests.test_final_scope_widget_e2e_closeout_implementation import (
    test_frozen_retry4_artifacts_unchanged_after_closeout,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEMO_MD = _REPO_ROOT / "clients" / "demo" / "md"
_TARGET = _REPO_ROOT / "clients" / "demo" / "target_response"


def _frame(**overrides: object) -> TurnFrame:
    from core.turn_frame_from_raw import build_turn_frame_from_raw

    payload: dict[str, object] = {
        "route": "content",
        "aspects": ["overview"],
        "primary_aspect": "overview",
        "service_id": "bone_graft",
        "topic": "implantation",
        "topic_confidence": 0.9,
    }
    payload.update(overrides)
    return build_turn_frame_from_raw(
        payload,
        allowed_topics=frozenset({"implantation", "doctors"}),
        allowed_service_ids=frozenset({"bone_graft", "all_on_4", "sinus_lift"}),
    )


def test_implementation_artifacts_present() -> None:
    assert (_REPO_ROOT / "core" / "target_presentation_decision.py").is_file()
    assert (_REPO_ROOT / "core" / "target_presentation_turn_projection.py").is_file()
    assert (_REPO_ROOT / "core" / "target_presentation_source_identity.py").is_file()
    assert (_REPO_ROOT / "tests" / "test_fullcontext_presentation_parity_bone_graft_demo_data.py").is_file()


def test_frozen_pins_unchanged() -> None:
    test_frozen_retry4_artifacts_unchanged_after_closeout()
    test_w1b_snapshot_checksums_unchanged()
    test_pscn_frozen_pins_unchanged()
    turns_path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    assert sha256_file_hex(turns_path) == FROZEN_TURNS_HASH
    assert_frozen_retry4_live_artifacts_unchanged()


def test_choice_menu_caps_at_four() -> None:
    navigation = tuple(
        TargetNavigationFollowup(
            label=f"Opt {index}",
            ref=build_ui_scope_ref(topic=topic, extent=extent),
        )
        for index, (topic, extent) in enumerate(
            (
                ("implantation", "one_tooth"),
                ("implantation", "few_teeth"),
                ("implantation", "full_arch"),
                ("veneers", "one_tooth"),
                ("whitening", "one_tooth"),
            )
        )
    )
    decision = decide_target_presentation(
        client_id="demo",
        md_root=_DEMO_MD,
        spec=TargetResponseSpec(
            response_mode="answer",
            service_id="classic",
            tone_key="commercial_warm",
            allowed_topics=("implantation",),
            required_components=("price",),
        ),
        navigation_followups=navigation[:5],
        selected_followups=TargetResponseFollowupSelection(source=None, content=(), price=()),
        primary_content_ref=None,
        cadence=TargetPresentationCadenceState(),
        allow_situation=False,
    )
    assert len(decision.quick_replies) <= CHOICE_MENU_MAX
    assert any("choice_over_limit" in item for item in decision.dropped)


def test_secondary_content_allows_two_followups_without_video() -> None:
    content = (
        TargetContentFollowup(
            id="one",
            label="One",
            ref="implantation__service__bone_graft.md#kak-prohodit-vosstanovlenie",
            source_content_ref="implantation__service__bone_graft.md",
        ),
        TargetContentFollowup(
            id="two",
            label="Two",
            ref="implantation__service__bone_graft.md#sinus-lifting-i-stoimost",
            source_content_ref="implantation__service__bone_graft.md",
        ),
        TargetContentFollowup(
            id="three",
            label="Three",
            ref="implantation__service__bone_graft.md#skulovye-implanty-i-alternativy",
            source_content_ref="implantation__service__bone_graft.md",
        ),
    )
    decision = decide_target_presentation(
        client_id="demo",
        md_root=_DEMO_MD,
        spec=TargetResponseSpec(
            response_mode="answer",
            service_id="bone_graft",
            tone_key="commercial_warm",
            allowed_topics=("implantation",),
            required_components=("content",),
        ),
        navigation_followups=(),
        selected_followups=TargetResponseFollowupSelection(
            source="content",
            content=content,
            price=(),
        ),
        primary_content_ref="implantation__service__bone_graft.md",
        cadence=TargetPresentationCadenceState(),
        allow_situation=False,
    )
    assert len(decision.quick_replies) == SECONDARY_CONTENT_MAX
    assert decision.video is None


def test_invalid_primary_content_ref_omitted() -> None:
    assert not is_valid_content_ref(_DEMO_MD, "implantation__info__invented.md")


def test_semantic_context_projection() -> None:
    frame = _frame(primary_aspect="price", aspects=["price"])
    spec = TargetResponseSpec(
        response_mode="answer",
        service_id="bone_graft",
        tone_key="commercial_warm",
        allowed_topics=("implantation",),
        required_components=("price",),
    )
    assert resolve_target_semantic_context(frame, spec) == "price"


def test_marketing_scenarios_from_turn_frame_emotion() -> None:
    frame = _frame().model_copy(update={"emotion": "fear"})
    assert "pain_fear" in derive_marketing_scenarios(frame)


def test_bone_graft_service_and_offer_in_catalog() -> None:
    bundle = load_response_schema_bundle(_TARGET)
    assert "bone_graft" in bundle.services
    assert bundle.services["bone_graft"].content_ref == "implantation__service__bone_graft.md"
    offers = [offer for offer in bundle.offers if offer.service_id == "bone_graft"]
    assert len(offers) == 1
    assert offers[0].price.mode == "no_public_price"
    assert (
        offers[0].price.approved_text
        == "Стоимость костной пластики рассчитывается после КТ и зависит от необходимого объёма и выбранной методики."
    )


def test_sinus_lift_prices_unchanged() -> None:
    bundle = load_response_schema_bundle(_TARGET)
    closed = next(
        offer for offer in bundle.offers if offer.offer_id == "sinus_lift.one_site.closed"
    )
    open_offer = next(
        offer for offer in bundle.offers if offer.offer_id == "sinus_lift.one_site.open"
    )
    assert closed.price.min_amount == 42000  # type: ignore[union-attr]
    assert open_offer.price.min_amount == 68000  # type: ignore[union-attr]
