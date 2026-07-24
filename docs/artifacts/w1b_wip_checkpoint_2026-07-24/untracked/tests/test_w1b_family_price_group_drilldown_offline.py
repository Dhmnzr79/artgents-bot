from __future__ import annotations

import json

import pytest

from contracts.target_family_price_group_followup import build_family_price_group_ref
from contracts.target_turn_frame_dispatch import TargetTurnFrameBoundMaterializeResponse
from core.response_schema_loader import load_response_schema_bundle
from core.target_family_price_overview import (
    is_family_price_group_drilldown_spec,
    select_family_price_group_drilldown,
)
from core.target_turn_frame_bound_response import run_target_offline_turn_frame_bound_response
from tests.test_demo_target_turn_frame_bound_response import (
    RecordingComposerBackend,
    RecordingSemanticBackend,
    _envelope,
    _pipeline_inputs,
)

TARGET_ROOT = __import__("pathlib").Path("clients/demo/target_response")


def _drilldown_frame(*, topic: str, group_id: str, **overrides: object):
    from contracts.turn_frame import FieldMeta
    from core.turn_frame_from_raw import build_turn_frame_from_raw

    payload: dict[str, object] = {
        "route": "content",
        "aspects": ["price"],
        "primary_aspect": "price",
        "service_id": None,
        "topic": topic,
        "topic_confidence": 0.9,
    }
    payload.update(overrides)
    frame = build_turn_frame_from_raw(
        payload,
        allowed_topics=frozenset({"implantation", "prosthetics", "doctors"}),
        allowed_service_ids=frozenset(
            load_response_schema_bundle(TARGET_ROOT).services.keys()
        ),
    )
    group_ref = build_family_price_group_ref(topic=topic, group_id=group_id)
    nav_meta = FieldMeta(
        confidence=1.0,
        provenance="test.family_price_group_nav",
        status="valid",
    )
    return frame.model_copy(
        update={
            "follow_up": True,
            "followup_of": group_ref,
            "field_meta": frame.field_meta.model_copy(
                update={"follow_up": nav_meta, "followup_of": nav_meta}
            ),
        }
    )


def _run_drilldown(topic: str, group_id: str, user_message: str):
    bundle = load_response_schema_bundle(TARGET_ROOT)
    doctors = __import__(
        "core.doctor_schema_loader", fromlist=["load_doctor_catalog"]
    ).load_doctor_catalog(__import__("pathlib").Path("clients/demo/doctor_catalog.json"))
    selection = select_family_price_group_drilldown(
        bundle,
        doctors,
        turn_topic=topic,
        group_id=group_id,
    )
    parts: list[str] = []
    for entry in selection.entries:
        offer = next(o for o in bundle.offers if o.offer_id == entry.offer_id)
        service = bundle.services[entry.service_id]
        price = offer.price
        if price.mode == "from":
            parts.append(f"{service.name} — от {price.min_amount:,} рублей".replace(",", " "))
        elif price.mode == "fixed":
            parts.append(f"{service.name} — {price.amount:,} рублей".replace(",", " "))
        elif price.mode == "range":
            parts.append(
                f"{service.name} — от {price.min_amount:,} до {price.max_amount:,} рублей".replace(
                    ",", " "
                )
            )
        else:
            parts.append(f"{service.name} — {price.approved_text}")  # type: ignore[union-attr]
    composer = RecordingComposerBackend(text=" ".join(parts))
    semantic = RecordingSemanticBackend()
    inputs = _pipeline_inputs()
    inputs["user_message"] = user_message
    result = run_target_offline_turn_frame_bound_response(
        _drilldown_frame(topic=topic, group_id=group_id),
        _envelope(allowed_topics=("implantation", "prosthetics", "doctors")),
        **inputs,  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
    )
    return result, selection, composer


def test_implantation_one_tooth_drilldown_excludes_full_jaw_protocols() -> None:
    result, selection, _composer = _run_drilldown(
        "implantation",
        "one_tooth",
        "Один зуб",
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert is_family_price_group_drilldown_spec(result.verified.spec)
    assert result.dispatch.policy_request.family_price_group_id == "one_tooth"
    service_ids = selection.service_ids
    assert service_ids == ("classic", "one_stage")
    assert "all_on_4" not in service_ids
    assert "all_on_6" not in service_ids
    assert not result.verified.selected_followups.group


def test_implantation_full_jaw_drilldown_includes_all_on_protocols() -> None:
    result, selection, _composer = _run_drilldown(
        "implantation",
        "full_jaw",
        "Вся челюсть",
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    service_ids = selection.service_ids
    assert "all_on_4" in service_ids
    assert "all_on_6" in service_ids
    assert "classic" not in service_ids


def test_prosthetics_several_teeth_includes_partial_not_full() -> None:
    _result, selection, _composer = _run_drilldown(
        "prosthetics",
        "several_teeth",
        "Несколько зубов",
    )
    offer_ids = selection.entries
    ids = tuple(entry.offer_id for entry in offer_ids)
    assert "removable_dentures.jaw.partial" in ids
    assert "removable_dentures.jaw.full" not in ids


def test_prosthetics_full_jaw_includes_full_only() -> None:
    _result, selection, _composer = _run_drilldown(
        "prosthetics",
        "full_jaw",
        "Вся челюсть",
    )
    ids = tuple(entry.offer_id for entry in selection.entries)
    assert ids == ("removable_dentures.jaw.full",)


def test_all_on_4_exact_question_skips_situation_menu() -> None:
    from core.turn_frame_from_raw import build_turn_frame_from_raw
    from tests.test_demo_target_turn_frame_bound_response import VALID_TEXT, _frame

    composer = RecordingComposerBackend(text=VALID_TEXT)
    semantic = RecordingSemanticBackend()
    result = run_target_offline_turn_frame_bound_response(
        _frame(),
        _envelope(),
        **_pipeline_inputs(),  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert result.dispatch.policy_request.service_id == "all_on_4"
    assert result.dispatch.policy_request.family_price_overview_topic is None
    assert not result.verified.selected_followups.group
