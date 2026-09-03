from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

import pytest

from contracts.response_plan import RouteModePair
from contracts.response_plan_composer import (
    ComposerAdapterError,
    ComposerParserError,
    ComposerProvenanceWarning,
    adapt_composer_envelope_to_decision,
    parse_response_plan_composer_json,
)
from tests.test_response_plan_composer_contract import (
    _base_payload,
    _composer_decision_authority_from_plan,
    _composer_plan,
    _json,
)


def _parse(payload: dict[str, object]) -> object:
    return parse_response_plan_composer_json(json.dumps(payload, ensure_ascii=False))


def test_invalid_json() -> None:
    with pytest.raises(ComposerParserError) as exc:
        parse_response_plan_composer_json("{not json")
    assert exc.value.code == "json_invalid"


def test_markdown_fence_rejected() -> None:
    raw = "```json\n" + _json() + "\n```"
    with pytest.raises(ComposerParserError) as exc:
        parse_response_plan_composer_json(raw)
    assert exc.value.code == "json_invalid"


def test_trailing_prose_rejected() -> None:
    with pytest.raises(ComposerParserError) as exc:
        parse_response_plan_composer_json(_json() + " trailing")
    assert exc.value.code == "json_invalid"


@pytest.mark.parametrize("raw", ["[]", "null", "1", '"text"'])
def test_non_object_root_rejected(raw: str) -> None:
    with pytest.raises(ComposerParserError) as exc:
        parse_response_plan_composer_json(raw)
    assert exc.value.code == "json_root_not_object"


@pytest.mark.parametrize(
    "field",
    [
        "route",
        "mode",
        "patient_text",
        "service_reference_kind",
        "option_reference_kind",
        "topic_id",
        "explicit_service_id",
        "requested_aspect_ids",
        "patient_situation",
        "requested_fact_ids",
    ],
)
def test_missing_core_field_parametric(field: str) -> None:
    payload = _base_payload()
    del payload[field]
    with pytest.raises(ComposerParserError) as exc:
        _parse(payload)
    assert exc.value.code == "json_missing_core_field"
    assert exc.value.detail == field


def test_duplicate_top_level_key_fatal() -> None:
    raw = (
        '{"route":"ANSWER","route":"ADMIN","mode":"standard","patient_text":"x",'
        '"service_reference_kind":"none","option_reference_kind":"none","topic_id":null,"explicit_service_id":null,'
        '"requested_aspect_ids":[],"patient_situation":{"extent":"unknown","jaw":"unknown",'
        '"stage":"unknown","modifiers":[]},"requested_fact_ids":[],"source_identity":null}'
    )
    with pytest.raises(ComposerParserError) as exc:
        parse_response_plan_composer_json(raw)
    assert exc.value.code == "json_duplicate_key"


def test_lowercase_route_rejected() -> None:
    with pytest.raises(ComposerParserError) as exc:
        parse_response_plan_composer_json(_json(route="answer"))
    assert exc.value.code == "route_mode_invalid"


def test_padded_route_rejected() -> None:
    with pytest.raises(ComposerParserError) as exc:
        parse_response_plan_composer_json(_json(route=" ANSWER"))
    assert exc.value.code == "route_mode_invalid"


def test_missing_mode_rejected() -> None:
    payload = _base_payload()
    del payload["mode"]
    with pytest.raises(ComposerParserError) as exc:
        _parse(payload)
    assert exc.value.code == "json_missing_core_field"


def test_numeric_requested_fact_id_rejected() -> None:
    with pytest.raises(ComposerParserError) as exc:
        parse_response_plan_composer_json(_json(requested_fact_ids=[1]))
    assert exc.value.code == "field_type_invalid"


def test_null_requested_fact_id_rejected() -> None:
    with pytest.raises(ComposerParserError) as exc:
        parse_response_plan_composer_json(_json(requested_fact_ids=[None]))
    assert exc.value.code == "field_type_invalid"


def test_blank_requested_fact_id_rejected() -> None:
    with pytest.raises(ComposerParserError) as exc:
        parse_response_plan_composer_json(_json(requested_fact_ids=[""]))
    assert exc.value.code == "identifier_invalid"


def test_padded_requested_fact_id_rejected() -> None:
    with pytest.raises(ComposerParserError) as exc:
        parse_response_plan_composer_json(_json(requested_fact_ids=[" fact"]))
    assert exc.value.code == "identifier_invalid"


def test_duplicate_requested_fact_id_rejected() -> None:
    with pytest.raises(ComposerParserError) as exc:
        parse_response_plan_composer_json(_json(requested_fact_ids=["a", "a"]))
    assert exc.value.code == "identifier_invalid"


def test_answer_standard_without_patient_text_rejected() -> None:
    with pytest.raises(ComposerParserError) as exc:
        parse_response_plan_composer_json(_json(patient_text=None))
    assert exc.value.code == "output_shape_invalid"


def test_answer_standard_whitespace_patient_text_rejected() -> None:
    with pytest.raises(ComposerParserError) as exc:
        parse_response_plan_composer_json(_json(patient_text="   "))
    assert exc.value.code == "output_shape_invalid"


def test_contacts_with_patient_text_rejected() -> None:
    with pytest.raises(ComposerParserError) as exc:
        parse_response_plan_composer_json(
            _json(route="ANSWER", mode="contacts", patient_text="контакты")
        )
    assert exc.value.code == "output_shape_invalid"


def test_clarify_with_requested_fact_rejected() -> None:
    with pytest.raises(ComposerParserError) as exc:
        parse_response_plan_composer_json(
            _json(route="CLARIFY", mode="standard", patient_text="?", requested_fact_ids=["x"])
        )
    assert exc.value.code == "output_shape_invalid"


def test_price_text_top_level_forbidden() -> None:
    with pytest.raises(ComposerParserError) as exc:
        parse_response_plan_composer_json(_json(price_text="120 000 ₽"))
    assert exc.value.code == "json_extra_field"
    assert exc.value.detail == "price_text"


def test_explicit_current_requires_explicit_service_id() -> None:
    with pytest.raises(ComposerParserError) as exc:
        parse_response_plan_composer_json(
            _json(service_reference_kind="explicit_current", explicit_service_id=None)
        )
    assert exc.value.code == "service_reference_invalid"


def test_active_session_forbids_explicit_service_id() -> None:
    with pytest.raises(ComposerParserError) as exc:
        parse_response_plan_composer_json(
            _json(
                service_reference_kind="active_session",
                explicit_service_id="all_on_4",
            )
        )
    assert exc.value.code == "service_reference_invalid"


def test_unknown_aspect_rejected() -> None:
    with pytest.raises(ComposerParserError) as exc:
        parse_response_plan_composer_json(_json(requested_aspect_ids=["composition"]))
    assert exc.value.code == "aspect_invalid"


def test_patient_situation_extra_field_rejected() -> None:
    with pytest.raises(ComposerParserError) as exc:
        parse_response_plan_composer_json(
            _json(
                patient_situation={
                    "extent": "unknown",
                    "jaw": "unknown",
                    "stage": "unknown",
                    "modifiers": [],
                    "extra": True,
                }
            )
        )
    assert exc.value.code == "situation_invalid"


def test_source_identity_missing_warning() -> None:
    payload = _base_payload()
    del payload["source_identity"]
    parsed = parse_response_plan_composer_json(json.dumps(payload, ensure_ascii=False))
    assert parsed.envelope.source_identity is None
    assert any(item.code == "source_identity_missing" for item in parsed.warnings)


def test_source_identity_primary_not_used_warning() -> None:
    parsed = parse_response_plan_composer_json(
        _json(
            source_identity={
                "primary_content_ref": "primary.md",
                "used_content_refs": ["other.md"],
            }
        )
    )
    assert parsed.envelope.source_identity is None
    assert any(item.code == "source_identity_primary_not_used" for item in parsed.warnings)


def test_source_identity_empty_object_warning() -> None:
    parsed = parse_response_plan_composer_json(
        _json(source_identity={"primary_content_ref": None, "used_content_refs": []})
    )
    assert parsed.envelope.source_identity is None
    assert any(item.code == "source_identity_empty" for item in parsed.warnings)


def test_source_identity_duplicate_json_key_fatal() -> None:
    raw = (
        '{"route":"ANSWER","mode":"standard","patient_text":"x","service_reference_kind":"none",'
        '"option_reference_kind":"none","topic_id":null,"explicit_service_id":null,"requested_aspect_ids":[],'
        '"patient_situation":{"extent":"unknown","jaw":"unknown","stage":"unknown","modifiers":[]},'
        '"requested_fact_ids":[],"source_identity":{"primary_content_ref":null,'
        '"used_content_refs":[],"used_content_refs":[]}}'
    )
    with pytest.raises(ComposerParserError) as exc:
        parse_response_plan_composer_json(raw)
    assert exc.value.code == "json_duplicate_key"


def test_invalid_source_ref_examples_warn_and_drop_identity() -> None:
    for ref in (
        "../secret.md",
        "a/../secret.md",
        "/absolute.md",
        "C:\\secret.md",
        "a\\secret.md",
        "https://host/doc.md",
        "a//b.md",
        "file.txt",
        " source.md",
        "source.md ",
    ):
        parsed = parse_response_plan_composer_json(
            _json(
                source_identity={
                    "primary_content_ref": None,
                    "used_content_refs": [ref],
                }
            )
        )
        assert parsed.envelope.source_identity is None
        assert any(item.code == "source_identity_invalid_ref" for item in parsed.warnings)


def test_valid_nested_source_ref_attestation_preserved() -> None:
    parsed = parse_response_plan_composer_json(
        _json(
            source_identity={
                "primary_content_ref": "a_first/service_a.md",
                "used_content_refs": ["a_first/service_a.md"],
            }
        )
    )
    assert parsed.envelope.source_identity is not None
    assert parsed.envelope.source_identity.used_content_refs == ("a_first/service_a.md",)


def test_terminal_route_with_identity_dropped_by_adapter() -> None:
    plan = _composer_plan()
    parsed = parse_response_plan_composer_json(
        _json(
            route="ADMIN",
            mode="standard",
            patient_text=None,
            source_identity={
                "primary_content_ref": "doc.md",
                "used_content_refs": ["doc.md"],
            },
        )
    )
    adapted = adapt_composer_envelope_to_decision(
        parsed,
        _composer_decision_authority_from_plan(plan),
    )
    assert adapted.decision.route == "ADMIN"
    assert adapted.source_identity is None
    assert any(item.code == "terminal_fields_normalized" for item in adapted.diagnostics)


def test_parser_accepts_globally_valid_pair_without_plan() -> None:
    parsed = parse_response_plan_composer_json(
        _json(route="CLARIFY", mode="standard", patient_text="Уточните.")
    )
    assert parsed.envelope.route == "CLARIFY"


def test_parser_does_not_import_adapter_module() -> None:
    module = importlib.import_module("contracts.response_plan_composer")
    source = Path(module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "core.response_plan_production_adapter" not in imported
    assert "contracts.response_plan_adapter" not in imported


def test_adapter_module_does_not_call_json_loads() -> None:
    source = Path("contracts/response_plan_adapter.py").read_text(encoding="utf-8")
    assert "json.loads" not in source


def test_parser_preserves_exact_raw_field_values() -> None:
    parsed = parse_response_plan_composer_json(_json(patient_text="  spaced  "))
    assert parsed.envelope.patient_text == "  spaced  "


def test_unknown_requested_id_accepted_by_parser() -> None:
    parsed = parse_response_plan_composer_json(_json(requested_fact_ids=["unknown_fact"]))
    assert parsed.envelope.requested_fact_ids == ("unknown_fact",)


def test_plan_aware_route_validation_only_in_adapter() -> None:
    from contracts.response_plan import ComposerSelectedRouteAuthority

    plan = _composer_plan(
        route_authority=ComposerSelectedRouteAuthority(
            allowed_route_modes=(RouteModePair(route="ANSWER", mode="standard"),),
            terminal_candidates=(),
        )
    )
    parsed = parse_response_plan_composer_json(_json(route="CLARIFY", mode="standard", patient_text="?"))

    with pytest.raises(ComposerAdapterError) as exc:
        adapt_composer_envelope_to_decision(
            parsed,
            _composer_decision_authority_from_plan(plan),
        )
    assert exc.value.code == "route_mode_not_allowed"
