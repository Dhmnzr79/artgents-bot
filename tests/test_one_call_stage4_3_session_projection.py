from __future__ import annotations

from contracts.exact_sales_resolution import ExactSalesFieldAuthority, ExactSalesResolution
from contracts.one_call_envelope import OneCallEnvelope
from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot
from core.one_call_envelope_protocol import production_envelope_template
from core.sales_fast_strict_evidence import effective_scope_from_semantic_frame
from core.sales_fast_turn_frame import build_turn_frame_from_semantic_frame
from core.service_reference_catalog import ServiceReferenceCatalogSnapshot
from core.sales_one_plus_semantic_authority import bind_semantic_frame, governed_ui_authority_from_resolution
from core.target_client_data import load_target_client_data
from core.target_runtime_session import (
    TargetRuntimeSessionState,
    write_target_runtime_session_after_materialized,
)
from session import mem_get, mem_reset


def _envelope(**overrides: object) -> OneCallEnvelope:
    return OneCallEnvelope.model_validate({**production_envelope_template(), **overrides})


def test_null_service_turn_preserves_historical_focus_set_at_turn() -> None:
    sid = "stage43-session-focus"
    mem_reset(sid)
    st = mem_get(sid)
    st["session_turn_count"] = 3
    st["target_runtime_state"] = {
        "last_service_id": "classic",
        "last_topic": "implantation",
        "service_focus_set_at_turn": 1,
    }

    unknown = ExactSalesFieldAuthority(authority="unknown", provenance="unknown")
    resolution = ExactSalesResolution(
        None,
        None,
        None,
        None,
        None,
        unknown,
        unknown,
        unknown,
        unknown,
        unknown,
    )
    catalog = ActiveServiceCatalogSnapshot.from_bundle(load_target_client_data("demo").bundle)
    ref_catalog = ServiceReferenceCatalogSnapshot.from_bundle(load_target_client_data("demo").bundle)
    semantic = bind_semantic_frame(
        envelope=_envelope(service_id=None),
        governed_ui=governed_ui_authority_from_resolution(resolution),
        active_service_catalog=catalog,
        service_reference_catalog=ref_catalog,
    )
    turn_frame = build_turn_frame_from_semantic_frame(
        semantic=semantic,
        user_message="Как обеспечивается стерильность?",
        bundle=load_target_client_data("demo").bundle,
    )
    effective_scope = effective_scope_from_semantic_frame(
        semantic,
        current_ui_action=None,
        current_ui_stage_action=None,
    )
    prior = TargetRuntimeSessionState(
        last_service_id="classic",
        last_topic="implantation",
        last_primary_aspect="price",
        service_focus_set_at_turn=1,
        session_turn_count=3,
        shown_fact_ids=(),
        shown_amplifier_refs=(),
        shown_consultation_value_refs=(),
        shown_service_value_ids=(),
        shown_video_ids=(),
        shown_content_followup_refs=(),
        shown_price_followup_refs=(),
        situation_offered=False,
        last_rendered_promo_fact_id=None,
        rendered_promo_fact_ids=(),
        last_turn_rendered_promo_fact_ids=(),
        followups=(),
    )
    write_target_runtime_session_after_materialized(
        sid,
        turn_frame=turn_frame,
        verified=type("Verified", (), {"used_content_refs": ()})(),
        prior=prior,
        current_selection=type(
            "Selection",
            (),
            {
                "shown_fact_ids": (),
                "shown_amplifier_refs": (),
                "shown_consultation_value_refs": (),
                "shown_service_value_ids": (),
                "rendered_promo_fact_ids": (),
                "last_rendered_promo_fact_id": None,
                "last_turn_rendered_promo_fact_ids": (),
            },
        )(),
        followups=(),
        effective_scope=effective_scope,
        presentation_cadence_update=None,
    )
    payload = mem_get(sid)["target_runtime_state"]
    assert payload["last_service_id"] == "classic"
    assert payload["service_focus_set_at_turn"] == 1
    assert turn_frame.service_id is None
