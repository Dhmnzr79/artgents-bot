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
        parse({"outcome": "dialogue", "blocks": [{"kind": "price", "request_id": "r1",
               "clarification": {"missing": "service", "choices": ["classic", "foreign"]}}]})


def test_known_explanation_cannot_replace_operation_or_target():
    task = D2DialogueResult.model_validate({"outcome": "dialogue", "blocks": [
        {"kind": "content", "request_id": "r1", "target": {"type": "service", "id": "classic"},
         "pending_question": "Explain this service"}]})
    with pytest.raises(ValueError, match="known_task_explanation_invalid"):
        parse({"explanations": [{"request_id": "r1", "content_text": "changed",
               "target": {"type": "service", "id": "veneers"}}]}, task)
    answer = parse({"explanations": [{"request_id": "r1", "content_text": "Grounded explanation"}]}, task)
    assert answer.blocks[0].target == task.blocks[0].target
    assert answer.blocks[0].content_text == "Grounded explanation"
    assert "pending_question" not in answer.blocks[0].model_dump()


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
        {"kind": "content", "request_id": "r1", "pending_question": "SEED ONLY"}]})
    with pytest.raises(ValueError, match="known_task_explanation_text_required"):
        parse({"explanations": [{"request_id": "r1", **replacement}]}, task)


def prompt_example(index):
    """Read what the live provider actually sends, not a separate example fixture."""
    import re
    from core.d2_live_provider import build_d2_d1r_messages
    system, _ = build_d2_d1r_messages(_request())
    examples = re.findall(r"```json\s*(.*?)\s*```", system["content"], re.DOTALL)
    assert len(examples) == 6
    text = examples[index].replace("<topic_id>", "implantation")
    text = text.replace("<service_id>", "classic").replace("<other_service_id>", "all_on_4")
    text = text.replace("<requested_service_id>", "classic").replace("<requested_brand_id>", "nobel_biocare")
    return json.loads(text)


@pytest.mark.parametrize("index,kind", [(0, "price"), (1, "price"), (2, "content"), (3, "content"), (4, "price_detail"), (5, "price")])
def test_sent_prompt_examples_conform_to_current_parser(index, kind):
    result = parse(prompt_example(index))
    block = result.blocks[0]
    operation = block
    assert operation.kind == kind and operation.request_id == "r1"
    if index in (0, 3, 5):
        assert operation.topic_id == "implantation" and operation.service_id is None
    elif index == 4:
        assert operation.service_id == "classic"
        assert operation.brand_id == "nobel_biocare"
        assert operation.price_detail_aspect == "stages"
    else:
        assert block.clarification.missing == "service"
        assert "operation" not in block.model_dump()
    if index == 5:
        assert operation.kind == "price"
        assert operation.volume.extent == "few_teeth"
        assert operation.volume.tooth_count == 3


def test_target_in_place_of_pending_operation_is_not_repaired():
    payload = prompt_example(1)
    payload["blocks"][0]["operation"] = {"type": "service", "id": "classic"}
    with pytest.raises(ValueError, match="extra_forbidden"):
        parse(payload)


def test_sent_prompt_contains_only_current_extent_menu_copy():
    from core.d2_live_provider import build_d2_d1r_messages
    system, _ = build_d2_d1r_messages(_request())
    directions = system["content"].split("=== D2_DIRECTION_PRICES ===\n")[1].split("=== BRAND_CATALOG ===")[0]
    rows = json.loads(directions)
    assert rows
    expected = {item.topic_id: item.unknown_extent_text for item in _request().model_view.direction_prices}
    assert {row["topic_id"]: row["unknown_extent_text"] for row in rows} == expected
    assert all('Несколько зубов' not in row['unknown_extent_text'] for row in rows)


@pytest.mark.parametrize("missing", ["extent", "jaw", "stage"])
@pytest.mark.parametrize("target", [None, {"type": "topic", "id": "implantation"}, {"type": "service", "id": "classic"}])
def test_price_parameter_clarification_removed_from_parser_and_memory(missing, target):
    from pydantic import TypeAdapter
    from contracts.d2_dialogue_result import ClarifiedOperation
    operation = {"kind": "price", "request_id": "r1", "target": target,
                 "clarification": {"missing": missing, "choices": []}}
    with pytest.raises(ValueError):
        parse({"outcome": "dialogue", "blocks": [operation]})
    with pytest.raises(ValueError):
        TypeAdapter(ClarifiedOperation).validate_python(operation)


@pytest.mark.parametrize("target", [{"type": "topic", "id": "implantation"}, {"type": "service", "id": "classic"}])
def test_known_price_cannot_be_hidden_in_term_clarification(target):
    from pydantic import TypeAdapter
    from contracts.d2_dialogue_result import ClarifiedOperation
    operation = {"kind": "price", "request_id": "r1", "target": target,
                 "clarification": {"missing": "term", "choices": []}}
    with pytest.raises(ValueError):
        parse({"outcome": "dialogue", "blocks": [operation]})
    with pytest.raises(ValueError):
        TypeAdapter(ClarifiedOperation).validate_python(operation)


def test_actual_provider_schema_excludes_price_parameter_path():
    from core.d2_live_provider import build_d2_d1r_messages
    system, _ = build_d2_d1r_messages(_request())
    schema = json.loads(system["content"].split("=== D2_RESULT_SCHEMA ===\n")[1].split("=== SERVICE_REFERENCE_CATALOG ===")[0])
    definitions = schema["$defs"]
    variants = [definitions[v["$ref"].split("/")[-1]]
                for v in schema["properties"]["blocks"]["items"]["anyOf"]]
    prices = [v for v in variants if v["properties"]["kind"].get("const") == "price"]
    assert len(prices) == 2
    direct = next(v for v in prices if "clarification" not in v["properties"])
    pending = next(v for v in prices if "clarification" in v["properties"])
    assert direct["additionalProperties"] is False
    assert set(pending["properties"]["clarification"]["discriminator"]["mapping"]) == {"service", "term"}
    target = pending["properties"]["target"]
    assert target["anyOf"] == [{"$ref": "#/$defs/UnresolvedTarget"}, {"type": "null"}]
    assert all(v["properties"]["kind"].get("const") != "clarification" for v in variants)
    assert all("operation" not in v["properties"] for v in variants)
    contents = [v for v in variants if v["properties"]["kind"].get("const") == "content"]
    assert len(contents) == 2
    assert all(v["additionalProperties"] is False for v in contents)
    assert {tuple(k for k in ("content_text", "pending_question") if k in v["properties"]) for v in contents} == {
        ("content_text",), ("pending_question",)}
    assert all(next(k for k in ("content_text", "pending_question") if k in v["properties"]) in v["required"] for v in contents)


def test_unidentified_price_term_still_has_a_pending_task():
    result = parse({"outcome": "dialogue", "blocks": [{"kind": "price", "request_id": "r1",
        "target": {"type": "unresolved"}, "clarification": {"missing": "term", "choices": []}}]})
    assert result.blocks[0].kind == "price"


@pytest.mark.parametrize("kind", ["price", "content", "price_detail"])
def test_old_wrapper_and_recursive_clarification_are_rejected(kind):
    from pydantic import TypeAdapter
    from contracts.d2_dialogue_result import ClarifiedOperation
    operation = {"kind": kind, "request_id": "r1"}
    if kind == "content":
        operation["content_text"] = "Old unfinished question"
    if kind == "price_detail":
        operation["price_detail_aspect"] = "includes"
    old = {"kind": "clarification", "request_id": "r1", "missing": "service",
           "choices": ["classic", "all_on_4"], "operation": operation}
    recursive = {"kind": "price", "request_id": "r1", "clarification": {
        "missing": "service", "choices": ["classic", "all_on_4"], "operation": old}}
    for invalid in (old, recursive):
        with pytest.raises(ValueError):
            parse({"outcome": "dialogue", "blocks": [invalid]})
        with pytest.raises(ValueError):
            TypeAdapter(ClarifiedOperation).validate_python(invalid)


@pytest.mark.parametrize("texts", [
    {}, {"pending_question": "Question"},
    {"content_text": "Answer", "pending_question": "Question"},
    {"content_text": "Answer", "clarification": {"missing": "term"}},
])
def test_unfinished_content_is_never_a_ready_ordinary_answer(texts):
    with pytest.raises(ValueError):
        parse({"outcome": "dialogue", "blocks": [{"kind": "content", "request_id": "r1", **texts}]})


def test_wire_and_persisted_slot_use_the_same_operation():
    from contracts.d2_session_context import D2SessionState, empty_d2_session_snapshot
    from contracts.response_plan import SessionKey
    block = parse(prompt_example(2)).blocks[0]
    values = empty_d2_session_snapshot(SessionKey(client_id="demo", sid="same-type")).state.model_dump()
    state = D2SessionState.model_validate({**values, "clarify_pending": True, "clarify_task": block.model_dump()})
    assert type(state.clarify_task) is type(block)
    assert state.clarify_task == block
    assert state.clarify_task.model_dump() == block.model_dump()
    assert not hasattr(state.clarify_task, "operation")
    assert parse(prompt_example(2)).requests == (block,)
