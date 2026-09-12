from __future__ import annotations

import json

import pytest

from contracts.target_family_price_group_followup import build_family_price_group_ref
from contracts.target_turn_frame_dispatch import TargetTurnFrameBoundMaterializeResponse
from core.response_schema_loader import load_response_schema_bundle
from core.target_family_price_overview import (
    build_family_price_situation_followups,
    get_family_price_topic_groups,
    is_family_price_situation_menu_spec,
    select_family_price_situation_menu_anchors,
)
from core.target_turn_frame_bound_response import run_target_offline_turn_frame_bound_response
from tests.test_demo_target_turn_frame_bound_response import (
    RecordingComposerBackend,
    RecordingSemanticBackend,
    _envelope,
    _pipeline_inputs,
)

TARGET_ROOT = __import__("pathlib").Path("clients/demo/target_response")


def _menu_frame(**overrides: object):
    from core.turn_frame_from_raw import build_turn_frame_from_raw

    payload: dict[str, object] = {
        "route": "content",
        "aspects": ["price"],
        "primary_aspect": "price",
        "service_id": None,
        "topic": "implantation",
        "topic_confidence": 0.9,
    }
    payload.update(overrides)
    return build_turn_frame_from_raw(
        payload,
        allowed_topics=frozenset({"implantation", "prosthetics", "doctors"}),
        allowed_service_ids=frozenset(
            load_response_schema_bundle(TARGET_ROOT).services.keys()
        ),
    )


def test_implantation_situation_menu_buttons_from_client_config() -> None:
    bundle = load_response_schema_bundle(TARGET_ROOT)
    topic_groups = get_family_price_topic_groups(bundle, turn_topic="implantation")
    assert topic_groups is not None
    followups = build_family_price_situation_followups(
        topic_groups,
        turn_topic="implantation",
    )
    labels = [item.label for item in followups]
    refs = [item.ref for item in followups]
    assert labels == ["Один зуб", "Несколько зубов", "Вся челюсть"]
    assert len(refs) == len(set(refs))
    assert all(ref.startswith("target:family_price_group/implantation/") for ref in refs)


@pytest.mark.parametrize("topic", ["implantation", "prosthetics"])
def test_situation_menu_has_three_group_anchors(topic: str) -> None:
    bundle = load_response_schema_bundle(TARGET_ROOT)
    doctors = __import__(
        "core.doctor_schema_loader", fromlist=["load_doctor_catalog"]
    ).load_doctor_catalog(__import__("pathlib").Path("clients/demo/doctor_catalog.json"))
    selection = select_family_price_situation_menu_anchors(
        bundle,
        doctors,
        turn_topic=topic,
    )
    assert len(selection.entries) == 3
    assert "all_on_4" not in selection.service_ids or topic == "implantation"


def test_implantation_vague_price_materializes_situation_menu() -> None:
    bundle = load_response_schema_bundle(TARGET_ROOT)
    doctors = __import__(
        "core.doctor_schema_loader", fromlist=["load_doctor_catalog"]
    ).load_doctor_catalog(__import__("pathlib").Path("clients/demo/doctor_catalog.json"))
    selection = select_family_price_situation_menu_anchors(
        bundle,
        doctors,
        turn_topic="implantation",
    )
    parts: list[str] = ["Стоимость зависит от ситуации."]
    for entry in selection.entries:
        offer = next(o for o in bundle.offers if o.offer_id == entry.offer_id)
        price = offer.price
        if price.mode == "from":
            parts.append(f"{entry.service_name} — от {price.min_amount:,} рублей".replace(",", " "))
        elif price.mode == "fixed":
            parts.append(f"{entry.service_name} — {price.amount:,} рублей".replace(",", " "))
        elif price.mode == "range":
            parts.append(
                f"{entry.service_name} — от {price.min_amount:,} до {price.max_amount:,} рублей".replace(
                    ",", " "
                )
            )
        else:
            parts.append(f"{entry.service_name} — {price.approved_text}")  # type: ignore[union-attr]
    composer = RecordingComposerBackend(text=" ".join(parts))
    semantic = RecordingSemanticBackend()
    inputs = _pipeline_inputs()
    inputs["user_message"] = "Сколько стоит имплантация?"
    result = run_target_offline_turn_frame_bound_response(
        _menu_frame(),
        _envelope(allowed_topics=("implantation", "prosthetics", "doctors")),
        **inputs,  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert is_family_price_situation_menu_spec(result.verified.spec)
    evidence = json.loads(composer.invocations[0].primary_evidence_json)
    assert len(evidence) == 3
    assert all('"payment_stages":[' not in block["text"] for block in evidence)
    buttons = [item.label for item in result.verified.selected_followups.group]
    assert buttons == ["Один зуб", "Несколько зубов", "Вся челюсть"]
    protocol_names = ("Классическая", "Одномоментная", "All-on-4", "All-on-6")
    assert not any(name in label for label in buttons for name in protocol_names)


def test_prosthetics_situation_menu_excludes_veneers_and_implantation_refs() -> None:
    bundle = load_response_schema_bundle(TARGET_ROOT)
    topic_groups = get_family_price_topic_groups(bundle, turn_topic="prosthetics")
    assert topic_groups is not None
    followups = build_family_price_situation_followups(
        topic_groups,
        turn_topic="prosthetics",
    )
    assert [item.label for item in followups] == [
        "Один зуб",
        "Несколько зубов",
        "Вся челюсть",
    ]
    assert all(
        build_family_price_group_ref(topic="prosthetics", group_id=item.group_id) == item.ref
        for item in followups
    )
