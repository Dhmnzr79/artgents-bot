"""Offline tests for governed UI channel mutex."""

from __future__ import annotations

from pathlib import Path

from contracts.target_response_spec import TargetResponseSpec
from contracts.ui_scope_action import build_ui_scope_ref
from core.target_client_ui_nav import TargetNavigationFollowup
from core.target_presentation_decision import TargetPresentationCadenceState, decide_target_presentation
from core.target_response_followup_materializer import TargetContentFollowup, TargetPriceFollowup
from core.target_response_followup_policy import TargetResponseFollowupSelection

_DEMO_MD = Path("clients/demo/md")


def test_price_channel_without_content_secondary() -> None:
    content = (
        TargetContentFollowup(
            id="f1",
            label="Подробнее",
            ref="implantation__service__bone_graft.md#f1",
            source_content_ref="implantation__service__bone_graft.md",
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
        navigation_followups=(),
        selected_followups=TargetResponseFollowupSelection(
            source="price",
            content=content,
            price=price,
        ),
        primary_content_ref="implantation__service__bone_graft.md",
        cadence=TargetPresentationCadenceState(),
        allow_situation=False,
    )
    assert decision.channel == "price"
    assert all(not item["ref"].startswith("implantation__") for item in decision.quick_replies)


def test_choice_channel_excludes_price_detail() -> None:
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
