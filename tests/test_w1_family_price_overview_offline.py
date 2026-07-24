from __future__ import annotations

import pytest

from contracts.target_service_content_topic import (
    parse_service_catalog_content_topic,
    service_catalog_content_topic_matches,
)
from core.response_schema_loader import load_response_schema_bundle
from core.doctor_schema_loader import load_doctor_catalog
from core.target_family_price_overview import (
    FAMILY_PRICE_OVERVIEW_MAX_SERVICES,
    select_family_price_overview_services,
)


TARGET_ROOT = __import__("pathlib").Path("clients/demo/target_response")


@pytest.mark.parametrize(
    ("content_ref", "expected"),
    [
        ("implantation__service__classic.md", "implantation"),
        ("prosthetics__service__zirconia_crowns.md", "prosthetics"),
        ("invalid.md", None),
        ("no_topic_prefix.md", None),
        (None, None),
    ],
)
def test_parse_service_catalog_content_topic(content_ref, expected) -> None:
    assert parse_service_catalog_content_topic(content_ref) == expected


def test_service_catalog_content_topic_matches_is_generic() -> None:
    assert service_catalog_content_topic_matches(
        "implantation__service__all_on_4.md",
        "implantation",
    )
    assert not service_catalog_content_topic_matches(
        "prosthetics__service__zirconia_crowns.md",
        "implantation",
    )


def test_implantation_family_overview_selects_multiple_priced_services() -> None:
    bundle = load_response_schema_bundle(TARGET_ROOT)
    doctors = load_doctor_catalog(__import__("pathlib").Path("clients/demo/doctor_catalog.json"))
    selection = select_family_price_overview_services(
        bundle,
        doctors,
        turn_topic="implantation",
    )
    assert len(selection.entries) >= 2
    assert len(selection.entries) <= FAMILY_PRICE_OVERVIEW_MAX_SERVICES
    service_ids = selection.service_ids
    assert "all_on_4" in service_ids
    assert "classic" in service_ids
    assert all(
        service_catalog_content_topic_matches(
            bundle.services[sid].content_ref,
            "implantation",
        )
        for sid in service_ids
    )


def test_prosthetics_family_overview_excludes_implantation_services() -> None:
    bundle = load_response_schema_bundle(TARGET_ROOT)
    doctors = load_doctor_catalog(__import__("pathlib").Path("clients/demo/doctor_catalog.json"))
    selection = select_family_price_overview_services(
        bundle,
        doctors,
        turn_topic="prosthetics",
    )
    assert len(selection.entries) >= 2
    assert "all_on_4" not in selection.service_ids
    assert all(
        service_catalog_content_topic_matches(
            bundle.services[sid].content_ref,
            "prosthetics",
        )
        for sid in selection.service_ids
    )


def test_synthetic_fixture_family_overview_without_demo_hardcode(tmp_path) -> None:
    root = tmp_path / "target_response"
    (root / "pricebook" / "services").mkdir(parents=True)
    catalog = {
        "alpha_srv": {
            "name": "Alpha service",
            "aliases": [],
            "family": "therapy",
            "roles": ["protocol"],
            "active": True,
            "content_ref": "alpha_topic__service__alpha_srv.md",
            "selection": {"mode": "direct"},
            "options": [],
        },
        "beta_srv": {
            "name": "Beta service",
            "aliases": [],
            "family": "therapy",
            "roles": ["supporting"],
            "active": True,
            "content_ref": "alpha_topic__service__beta_srv.md",
            "selection": {"mode": "direct"},
            "options": [],
        },
    }
    (root / "service_catalog.json").write_text(
        __import__("json").dumps(catalog, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    for sid, amount in (("alpha_srv", 10_000), ("beta_srv", 20_000)):
        offer = {
            "offer_id": f"{sid}.default",
            "service_id": sid,
            "active": True,
            "price": {
                "mode": "from",
                "min_amount": amount,
                "currency": "RUB",
                "billing_unit": "procedure",
            },
            "package": {"label": sid, "includes": ["step"]},
        }
        (root / "pricebook" / "services" / f"{sid}.default.json").write_text(
            __import__("json").dumps(offer, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    (root / "pricebook" / "facts.json").write_text(
        "{}",
        encoding="utf-8",
    )
    (root / "brand_catalog.json").write_text(
        __import__("json").dumps({"version": 1, "brands": {}}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (root / "marketing.yaml").write_text(
        """version: 1
limits:
  max_marketing_facts_per_turn: 0
  max_amplifiers_per_turn: 0
  max_scenarios_per_turn: 0
initial_commercial_blocks: {}
scenario_rules: {}
cta_contexts:
  default: callback
""",
        encoding="utf-8",
    )
    (root / "clinic_strategy.yaml").write_text(
        "version: 1\ndefault_max_options: 3\ndefault_service_priorities: {}\ndefault_offer_priorities: {}\nrules: []\n",
        encoding="utf-8",
    )

    bundle = load_response_schema_bundle(root)
    doctors = load_doctor_catalog(__import__("pathlib").Path("clients/demo/doctor_catalog.json"))
    selection = select_family_price_overview_services(
        bundle,
        doctors,
        turn_topic="alpha_topic",
    )
    assert selection.service_ids == ("alpha_srv", "beta_srv")


def _family_overview_frame(**overrides: object):
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


def test_implantation_family_price_overview_materializes_via_pipeline() -> None:
    from contracts.target_turn_frame_dispatch import TargetTurnFrameBoundMaterializeResponse
    from core.target_turn_frame_bound_response import run_target_offline_turn_frame_bound_response
    from tests.test_demo_target_turn_frame_bound_response import (
        RecordingComposerBackend,
        RecordingSemanticBackend,
        _envelope,
        _pipeline_inputs,
    )

    bundle = load_response_schema_bundle(TARGET_ROOT)
    selection = select_family_price_overview_services(
        bundle,
        load_doctor_catalog(__import__("pathlib").Path("clients/demo/doctor_catalog.json")),
        turn_topic="implantation",
    )
    parts: list[str] = ["Стоимость зависит от метода."]
    for entry in selection.entries:
        offer = next(o for o in bundle.offers if o.offer_id == entry.offer_id)
        price = offer.price
        if price.mode == "from":
            amount = price.min_amount
            parts.append(f"{entry.service_name} — от {amount:,} рублей".replace(",", " "))
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
    answer = " ".join(parts)
    composer = RecordingComposerBackend(text=answer)
    semantic = RecordingSemanticBackend()
    inputs = _pipeline_inputs()
    inputs["user_message"] = "Сколько стоит имплантация?"
    result = run_target_offline_turn_frame_bound_response(
        _family_overview_frame(),
        _envelope(allowed_topics=("implantation", "prosthetics", "doctors")),
        **inputs,  # type: ignore[arg-type]
        composer_backend=composer,
        semantic_backend=semantic,
    )
    assert isinstance(result, TargetTurnFrameBoundMaterializeResponse)
    assert result.dispatch.policy_request.family_price_overview_topic == "implantation"
    assert len(composer.invocations) == 1
    evidence = __import__("json").loads(composer.invocations[0].primary_evidence_json)
    assert len(evidence) >= 2
    assert all(block["kind"] == "offer" for block in evidence)


def test_all_on_4_exact_price_path_unchanged() -> None:
    from contracts.target_turn_frame_dispatch import TargetTurnFrameBoundMaterializeResponse
    from core.target_turn_frame_bound_response import run_target_offline_turn_frame_bound_response
    from tests.test_demo_target_turn_frame_bound_response import (
        RecordingComposerBackend,
        RecordingSemanticBackend,
        VALID_TEXT,
        _envelope,
        _frame,
        _pipeline_inputs,
    )

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
