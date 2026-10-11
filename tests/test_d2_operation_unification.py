"""Preserved dialogue forms and nested roundtrips for one operation per kind."""
import json

import pytest
from pydantic import TypeAdapter

from contracts.d2_dialogue_result import ClarifiedOperation, D2DialogueResult
from contracts.d2_session_context import D2OrdinarySessionContext, D2SessionState, empty_d2_session_snapshot
from contracts.response_plan import SessionKey


SERVICE = {"type": "service", "id": "classic"}
UNRESOLVED = {"type": "unresolved"}
TERM = {"missing": "term", "choices": []}
SERVICE_QUESTION = {"missing": "service", "choices": ["classic", "all_on_4"]}


def block(kind, pending=False):
    value = {"kind": kind, "request_id": "r1"}
    if kind == "content":
        value["pending_question" if pending else "content_text"] = "Clinic-approved text"
    elif kind == "price_detail":
        value["price_detail_aspect"] = "includes"
    elif kind == "commercial_fact":
        value.update(fact_ids=["installment_12"], target=UNRESOLVED if pending else SERVICE)
    if pending:
        value["clarification"] = TERM
    return value


def parse(value):
    return D2DialogueResult.model_validate({"outcome": "dialogue", "blocks": [value]})


@pytest.mark.parametrize("kind", ["price", "content", "price_detail"])
@pytest.mark.parametrize("pending", [False, True])
def test_same_type_and_canonical_nested_roundtrip(kind, pending):
    result = parse(block(kind, pending))
    operation = result.blocks[0]
    other = parse(block(kind, not pending)).blocks[0]
    assert type(operation) is type(other)
    assert D2DialogueResult.model_validate_json(result.model_dump_json()) == result
    dumped = operation.model_dump()
    if not pending:
        assert "clarification" not in dumped and "pending_question" not in dumped
        with pytest.raises(ValueError, match="clarify_task_requires_clarification"):
            TypeAdapter(ClarifiedOperation).validate_python(dumped)
        return
    if kind == "content":
        assert "content_text" not in dumped
    key = SessionKey(client_id="demo", sid="unified-storage")
    values = empty_d2_session_snapshot(key).state.model_dump()
    state = D2SessionState.model_validate({**values, "clarify_pending": True, "clarify_task": dumped})
    assert type(state.clarify_task) is type(operation)
    assert D2SessionState.model_validate_json(state.model_dump_json()) == state
    context = D2OrdinarySessionContext(clarify_pending=True, clarify_task=operation)
    assert D2OrdinarySessionContext.model_validate(context.model_dump()) == context
    assert context.clarify_task is operation


@pytest.mark.parametrize("kind", ["price", "content", "price_detail"])
def test_explicit_null_clarification_remains_invalid(kind):
    with pytest.raises(ValueError):
        parse({**block(kind), "clarification": None})


@pytest.mark.parametrize("pending", [False, True])
@pytest.mark.parametrize("other_text", [None, "Other text"])
def test_incompatible_content_field_even_null_remains_invalid(pending, other_text):
    value = block("content", pending)
    value["content_text" if pending else "pending_question"] = other_text
    with pytest.raises(ValueError):
        parse(value)


@pytest.mark.parametrize("target", [None, UNRESOLVED, SERVICE, {"type": "topic", "id": "implantation"}])
def test_direct_price_preserves_targetless_policy_inputs(target):
    assert parse({**block("price"), "target": target}).blocks[0].kind == "price"


@pytest.mark.parametrize("clarification", [TERM, SERVICE_QUESTION])
@pytest.mark.parametrize("kind", ["price"])
def test_known_target_cannot_be_hidden_by_clarification(kind, clarification):
    with pytest.raises(ValueError):
        parse({**block(kind, True), "target": SERVICE, "clarification": clarification})


@pytest.mark.parametrize("kind", ["doctors", "clinic_policy", "commercial_fact"])
def test_removed_information_commands_cannot_be_stored_as_pending(kind):
    with pytest.raises(ValueError):
        parse({"kind": kind, "request_id": "r1", "clarification": SERVICE_QUESTION})
    with pytest.raises(ValueError):
        TypeAdapter(ClarifiedOperation).validate_python({"kind": kind, "request_id": "r1"})


def test_payment_content_clinic_target_stays_rejected_not_repaired():
    with pytest.raises(ValueError):
        parse({**block("content"), "content_ref": "clinic__info__payment_terms.md", "target": {"type": "clinic"}})
    accepted = parse({**block("content"), "content_ref": "clinic__info__payment_terms.md"})
    assert accepted.blocks[0].content_ref == "clinic__info__payment_terms.md"


def test_actual_schema_has_one_branch_per_kind_and_no_pending_types():
    schema = D2DialogueResult.model_json_schema()
    items = schema["properties"]["blocks"]["items"]
    assert set(items["discriminator"]["mapping"]) == {
        "price", "content", "price_detail", "contact", "booking", "off_topic"}
    assert len(items["oneOf"]) == 6
    assert not any(name.startswith("Pending") for name in schema["$defs"])
    assert "AuthorizedExplanationOperation" not in json.dumps(schema)
