"""Boundary evidence: one strict parser, no competing control fields."""
import json

import pytest

from contracts.d2_dialogue_result import D2DialogueResult
from core.one_call_envelope_protocol import parse_production_envelope_json
from tests.test_d2_live_provider_offline import _request


def parse(payload, known_task=None):
    view = _request().model_view
    return parse_production_envelope_json(
        payload if isinstance(payload, str) else json.dumps(payload),
        active_service_catalog=view.active_service_catalog,
        service_reference_catalog=view.service_reference_catalog,
        commercial_fact_catalog=view.commercial_fact_catalog,
        known_task=known_task, d2_contract=True,
    )


@pytest.mark.parametrize("field,value", [
    ("route", "ANSWER"), ("service_id", "classic"), ("primary_price_request_id", "r1"),
    ("patient_text", "independent prose"), ("commercial_intent", "price"),
])
def test_competing_top_level_controls_are_rejected(field, value):
    payload = {"outcome": "dialogue", "blocks": [{"kind": "price", "request_id": "r1",
               "target": {"type": "service", "id": "classic"}}], field: value}
    with pytest.raises(ValueError):
        parse(payload)


def test_duplicate_json_keys_and_foreign_choices_are_rejected():
    with pytest.raises(ValueError, match="json_duplicate_keys"):
        parse('{"outcome":"admin","outcome":"dialogue"}')
    with pytest.raises(ValueError, match="clarify_service_not_active"):
        parse({"outcome": "dialogue", "blocks": [{"kind": "clarification", "request_id": "r1",
               "missing": "service", "choices": ["classic", "foreign"],
               "operation": {"kind": "price", "request_id": "r1"}}]})


def test_known_explanation_cannot_replace_operation_or_target():
    task = D2DialogueResult.model_validate({"outcome": "dialogue", "blocks": [
        {"kind": "content", "request_id": "r1", "target": {"type": "service", "id": "classic"},
         "content_text": "Explain this service"}]})
    with pytest.raises(ValueError, match="known_task_explanation_invalid"):
        parse({"explanations": [{"request_id": "r1", "content_text": "changed",
               "target": {"type": "service", "id": "veneers"}}]}, task)
    answer = parse({"explanations": [{"request_id": "r1", "content_text": "Grounded explanation"}]}, task)
    assert answer.blocks[0].target == task.blocks[0].target


def test_admin_is_exclusive_and_contact_has_no_price_fields():
    with pytest.raises(ValueError, match="admin_blocks_forbidden"):
        parse({"outcome": "admin", "blocks": [{"kind": "content", "request_id": "r1", "content_text": "ordinary"}]})
    with pytest.raises(ValueError):
        parse({"outcome": "dialogue", "blocks": [{"kind": "contact", "request_id": "r1",
               "contact_fields": ["contact_address"], "brand_id": "nobel"}]})


@pytest.mark.parametrize("service_id", ["foreign-service", "braces"])
def test_doctors_rejects_nonactive_tenant_service(service_id):
    with pytest.raises(ValueError, match="doctors_service_not_active"):
        parse({"outcome": "dialogue", "blocks": [{"kind": "doctors", "request_id": "r1",
               "target": {"type": "service", "id": service_id}}]})


@pytest.mark.parametrize("extra", [{"content_text": "Invented doctor"}, {"subject": {"subject_id": "s1", "relation": "self"}},
                                  {"service_id": "classic"}, {"route": "ANSWER"}])
def test_doctors_has_no_parallel_meaning_or_prose(extra):
    with pytest.raises(ValueError):
        parse({"outcome": "dialogue", "blocks": [{"kind": "doctors", "request_id": "r1",
               "target": {"type": "service", "id": "classic"}, **extra}]})


def test_doctors_requires_service_target():
    with pytest.raises(ValueError):
        parse({"outcome": "dialogue", "blocks": [{"kind": "doctors", "request_id": "r1",
               "target": {"type": "topic", "id": "implantation"}}]})


@pytest.mark.parametrize("replacement", [{}, {"content_text": None}, {"content_text": ""}, {"content_text": "   "}])
def test_known_task_must_not_publish_seed_as_new_explanation(replacement):
    task = D2DialogueResult.model_validate({"outcome": "dialogue", "blocks": [
        {"kind": "content", "request_id": "r1", "content_text": "SEED ONLY"}]})
    with pytest.raises(ValueError, match="known_task_explanation_text_required"):
        parse({"explanations": [{"request_id": "r1", **replacement}]}, task)


def prompt_example(index):
    """Read what the live provider actually sends, not a separate example fixture."""
    import re
    from core.d2_live_provider import build_d2_d1r_messages
    system, _ = build_d2_d1r_messages(_request())
    examples = re.findall(r"```json\s*(.*?)\s*```", system["content"], re.DOTALL)
    assert len(examples) == 5
    text = examples[index].replace("<topic_id>", "implantation")
    text = text.replace("<service_id>", "classic").replace("<other_service_id>", "all_on_4")
    return json.loads(text)


@pytest.mark.parametrize("index,kind", [(0, "price"), (1, "price"), (2, "content"), (3, "content"), (4, "price")])
def test_sent_prompt_examples_conform_to_current_parser(index, kind):
    result = parse(prompt_example(index))
    block = result.blocks[0]
    operation = block if index in (0, 3, 4) else block.operation
    assert operation.kind == kind and operation.request_id == "r1"
    if index in (0, 3, 4):
        assert operation.topic_id == "implantation" and operation.service_id is None
    else:
        assert block.request_id == operation.request_id
    if index == 4:
        assert operation.kind == "price"
        assert operation.situation.extent == "few_teeth"
        assert operation.situation.tooth_count == 3


def test_target_in_place_of_pending_operation_is_not_repaired():
    payload = prompt_example(1)
    payload["blocks"][0]["operation"] = {"type": "service", "id": "classic"}
    with pytest.raises(ValueError, match="union_tag_not_found"):
        parse(payload)


def test_sent_prompt_contains_only_current_extent_menu_copy():
    from core.d2_live_provider import build_d2_d1r_messages
    system, _ = build_d2_d1r_messages(_request())
    directions = system["content"].split("=== D2_DIRECTION_PRICES ===\n")[1].split("=== BRAND_CATALOG ===")[0]
    rows = json.loads(directions)
    assert rows
    for row in rows:
        assert row["unknown_extent_text"] == "Какой объём вас интересует: один зуб, вся челюсть или пока не знаете?"


@pytest.mark.parametrize("missing", ["extent", "jaw", "stage"])
@pytest.mark.parametrize("target", [None, {"type": "topic", "id": "implantation"}, {"type": "service", "id": "classic"}])
def test_price_parameter_clarification_removed_from_parser_and_memory(missing, target):
    from contracts.response_plan_session import PersistedClarifyTask
    operation = {"kind": "price", "request_id": "r1", "target": target}
    with pytest.raises(ValueError):
        parse({"outcome": "dialogue", "blocks": [{"kind": "clarification", "request_id": "r1",
            "missing": missing, "operation": operation, "choices": []}]})
    with pytest.raises(ValueError):
        PersistedClarifyTask(missing=missing, operation=operation)


@pytest.mark.parametrize("target", [{"type": "topic", "id": "implantation"}, {"type": "service", "id": "classic"}])
def test_known_price_cannot_be_hidden_in_term_clarification(target):
    from contracts.response_plan_session import PersistedClarifyTask
    operation = {"kind": "price", "request_id": "r1", "target": target}
    with pytest.raises(ValueError):
        parse({"outcome": "dialogue", "blocks": [{"kind": "clarification", "request_id": "r1",
            "missing": "term", "operation": operation, "choices": []}]})
    with pytest.raises(ValueError):
        PersistedClarifyTask(missing="term", operation=operation)


def test_actual_provider_schema_excludes_price_parameter_path():
    from core.d2_live_provider import build_d2_d1r_messages
    system, _ = build_d2_d1r_messages(_request())
    schema = json.loads(system["content"].split("=== D2_RESULT_SCHEMA ===\n")[1].split("=== SERVICE_REFERENCE_CATALOG ===")[0])
    definitions = schema["$defs"]
    clarification = schema["properties"]["blocks"]["items"]["discriminator"]["mapping"]["clarification"]
    assert clarification["discriminator"]["propertyName"] == "missing"
    for missing in ["extent", "jaw", "stage"]:
        name = clarification["discriminator"]["mapping"][missing].split("/")[-1]
        variants = definitions[name]["properties"]["operation"]["discriminator"]["mapping"]
        assert set(variants) == {"content", "price_detail"}
    meaning_name = clarification["discriminator"]["mapping"]["service"].split("/")[-1]
    price_ref = definitions[meaning_name]["properties"]["operation"]["discriminator"]["mapping"]["price"]
    target = definitions[price_ref.split("/")[-1]]["properties"]["target"]
    assert target["anyOf"] == [{"$ref": "#/$defs/UnresolvedTarget"}, {"type": "null"}]


def test_unidentified_price_term_still_has_a_pending_task():
    result = parse({"outcome": "dialogue", "blocks": [{"kind": "clarification", "request_id": "r1",
        "missing": "term", "operation": {"kind": "price", "request_id": "r1", "target": {"type": "unresolved"}}, "choices": []}]})
    assert result.blocks[0].operation.kind == "price"
