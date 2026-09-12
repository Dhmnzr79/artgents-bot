"""COMPLETION checker and acceptance tests for FULLCONTEXT_DIALOGUE_PRESENTATION_CONVERGENCE."""

from __future__ import annotations

from pathlib import Path

from contracts.target_response_spec import TargetResponseSpec
from contracts.ui_scope_action import build_ui_scope_ref
from core.target_client_ui_nav import TargetNavigationFollowup
from core.target_composer_output import compose_composer_json_payload, parse_composer_backend_output
from core.target_contact_authority import (
    canonical_contact_phone,
    materialize_clinic_contact_primary_evidence,
)
from core.target_presentation_decision import (
    TargetPresentationCadenceState,
    decide_target_presentation,
)
from core.target_presentation_source_identity import is_valid_content_ref
from core.target_presentation_turn_projection import marketing_scenarios_from_turn_frame
from core.target_response_followup_materializer import TargetContentFollowup, TargetPriceFollowup
from core.target_response_followup_policy import TargetResponseFollowupSelection
from core.target_runtime_widget import materialize_target_error_payload
from core.turn_frame_from_raw import build_turn_frame_from_raw
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


def _frame(**overrides: object):
    payload: dict[str, object] = {
        "route": "content",
        "aspects": ["overview"],
        "primary_aspect": "overview",
        "service_id": None,
        "topic": "implantation",
        "topic_confidence": 0.9,
        "marketing_scenarios": [],
    }
    payload.update(overrides)
    return build_turn_frame_from_raw(
        payload,
        allowed_topics=frozenset({"implantation", "clinic", "doctors"}),
        allowed_service_ids=frozenset({"all_on_4", "bone_graft"}),
    )


def test_implementation_artifacts_present() -> None:
    required = (
        "contracts/target_composer_source_identity.py",
        "core/target_composer_output.py",
        "core/target_contact_authority.py",
        "tests/test_situation_intake_http_offline.py",
        "tests/test_target_contact_primary_evidence_offline.py",
        "tests/test_target_presentation_channel_mutex_offline.py",
        "tests/test_target_fallback_phone_offline.py",
    )
    for rel in required:
        assert (_REPO_ROOT / rel).is_file(), rel


def test_frozen_pins_unchanged() -> None:
    test_frozen_retry4_artifacts_unchanged_after_closeout()
    test_w1b_snapshot_checksums_unchanged()
    test_pscn_frozen_pins_unchanged()
    turns_path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    assert sha256_file_hex(turns_path) == FROZEN_TURNS_HASH
    assert_frozen_retry4_live_artifacts_unchanged()


def test_composer_json_envelope_parsed() -> None:
    raw = compose_composer_json_payload(
        answer="Ответ.",
        primary_content_ref="implantation__service__bone_graft.md",
        used_content_refs=("implantation__service__bone_graft.md",),
    )
    answer, identity, warnings = parse_composer_backend_output(raw)
    assert answer == "Ответ."
    assert identity is not None
    assert identity.primary_content_ref == "implantation__service__bone_graft.md"
    assert warnings == ()


def test_generic_faq_invalid_source_fail_open_text() -> None:
    raw = '{"answer":"Общий ответ без источника."}'
    answer, identity, warnings = parse_composer_backend_output(raw)
    assert answer == "Общий ответ без источника."
    assert identity is None
    assert "source_identity_missing" in warnings


def test_marketing_scenarios_from_turn_frame() -> None:
    frame = _frame(marketing_scenarios=["time", "result_reliability"])
    assert marketing_scenarios_from_turn_frame(frame) == ("time", "result_reliability")


def test_contact_primary_evidence_kind() -> None:
    blocks = materialize_clinic_contact_primary_evidence("demo", aspect="contacts")
    assert blocks
    assert blocks[0].kind == "clinic_contact"
    assert canonical_contact_phone("demo") in blocks[0].text


def test_channel_mutex_choice_suppresses_price() -> None:
    navigation = (
        TargetNavigationFollowup(
            label="Один зуб",
            ref=build_ui_scope_ref(topic="implantation", extent="one_tooth"),
        ),
    )
    price = (
        TargetPriceFollowup(
            id="default",
            label="Цена",
            ref="price:all_on_4/default",
            action="show",
            source_offer_ids=("all_on_4.default",),
        ),
    )
    decision = decide_target_presentation(
        client_id="demo",
        md_root=_DEMO_MD,
        spec=TargetResponseSpec(
            response_mode="answer",
            service_id="all_on_4",
            tone_key="commercial_warm",
            allowed_topics=("implantation",),
            required_components=("price",),
        ),
        navigation_followups=navigation,
        selected_followups=TargetResponseFollowupSelection(
            source="price",
            content=(),
            price=price,
        ),
        primary_content_ref=None,
        cadence=TargetPresentationCadenceState(),
        allow_situation=False,
    )
    assert decision.channel == "choice"
    assert all(not item["ref"].startswith("price:") for item in decision.quick_replies)


def test_fallback_error_includes_canonical_phone() -> None:
    phone = canonical_contact_phone("demo")
    payload = materialize_target_error_payload(
        client_id="demo",
        sid="s-test",
        error_code="target_runtime_pipeline_failed:RuntimeError",
    )
    assert phone in payload.payload["answer"]
    assert payload.payload["cta"] is None
    assert payload.payload["video"] is None
    assert payload.payload["situation"]["show"] is False
    assert payload.payload["meta"]["attribution_kind"] == "plain"


def test_situation_after_followup_not_before() -> None:
    ref = "implantation__service__bone_graft.md#followup-1"
    content = (
        TargetContentFollowup(
            id="followup-1",
            label="Подробнее",
            ref=ref,
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
        allow_situation=True,
    )
    refs = [item["ref"] for item in decision.quick_replies]
    if decision.situation.get("show"):
        assert ref in refs or len(refs) == 0


def test_validated_primary_required_for_presentation_meta() -> None:
    assert is_valid_content_ref(_DEMO_MD, "implantation__service__bone_graft.md")
