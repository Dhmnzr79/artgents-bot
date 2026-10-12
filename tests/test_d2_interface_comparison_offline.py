"""3B candidate structure and frozen experiment factorization, no live calls."""
import json

import pytest
from pydantic import ValidationError

from scripts import d2_context_candidate_protocol as candidate
from scripts import experiment_d2_interface_comparison as experiment


def parse(blocks, **kwargs):
    return candidate.parse(json.dumps({"outcome": "dialogue", "blocks": blocks}),
                           service_ids={"classic", "inactive"}, active_ids={"classic"},
                           topic_ids={"implantation"}, document_sections={"approved.md": {"a:short"}},
                           **kwargs)


@pytest.mark.parametrize("block", [
    {"kind": "content", "brand_id": "osstem"},
    {"kind": "content", "content_text": "Ответ", "clarification": None, "pending_question": None},
    {"kind": "content", "target": "service:inactive"},
    {"kind": "price", "target": "topic:implantation", "clarification": None},
    {"kind": "price_detail", "target": "service:classic", "price_detail_aspect": "includes"},
    {"kind": "contact", "contact_fields": ["contact_address"]},
    {"kind": "doctors", "target": "service:classic"},
    {"kind": "clinic_policy", "policy_ids": ["no_oms"]},
    {"kind": "booking", "target": "service:classic"},
    {"kind": "commercial_fact", "target": "clinic", "fact_ids": ["approved"]},
    {"kind": "off_topic"},
])
def test_native_nine_kinds_and_completed_optional_text(block):
    result = parse([block])
    assert result.blocks[0].kind == block["kind"]
    assert not hasattr(result.blocks[0], "request_id")


@pytest.mark.parametrize("block", [
    {"kind": "content", "request_id": "r1", "content_text": "Ответ"},
    {"kind": "content", "target": {"type": "service", "id": "classic"}},
    {"kind": "content", "pending_question": "Объяснить"},
    {"kind": "content", "clarification": {"missing": "term"}},
    {"kind": "content", "pending_question": "Объяснить", "clarification": {"missing": "term"}, "content_text": "Ответ"},
    {"kind": "content", "content_text": "   "},
    {"kind": "content", "content_text": "x" * 4001},
    {"kind": "price", "target": "service:classic", "clarification": {"missing": "term"}},
    {"kind": "price", "clarification": {"missing": "jaw"}},
    {"kind": "commercial_fact", "target": "unresolved", "fact_ids": ["a"]},
    {"kind": "price_detail", "price_detail_aspect": "includes", "price_detail_offer_id": "a", "price_detail_offer_ordinal": 1},
    {"kind": "doctors", "target": "topic:implantation"},
])
def test_reject_old_wire_and_conflicting_or_incomplete_meaning(block):
    with pytest.raises(ValueError):
        parse([block])


def test_pending_explanation_and_detail_preserve_task_and_volume():
    block = {"kind": "content", "pending_question": "Как выполняется установка?",
             "brand_id": "nobel_biocare", "volume": {"extent": "few_teeth", "tooth_count": 3},
             "clarification": {"missing": "term"}}
    parsed = parse([block]).blocks[0]
    assert parsed.pending_question == block["pending_question"]
    assert parsed.volume.tooth_count == 3
    assert parsed.brand_id == "nobel_biocare"
    assert parsed.content_text is None
    detail = parse([{"kind": "price_detail", "price_detail_aspect": "includes",
                     "clarification": {"missing": "term"}}]).blocks[0]
    assert detail.price_detail_aspect == "includes"


@pytest.mark.parametrize("block", [
    {"kind": "price", "target": "service:foreign"},
    {"kind": "content", "target": "topic:foreign"},
    {"kind": "doctors", "target": "service:inactive"},
    {"kind": "content", "content_ref": "foreign.md"},
    {"kind": "content", "content_ref": "approved.md", "content_section_refs": ["foreign"]},
    {"kind": "price", "clarification": {"missing": "service", "choices": ["service:classic", "service:inactive"]}},
])
def test_read_only_reference_checks_do_not_repair(block):
    original = json.dumps(block)
    with pytest.raises(ValueError):
        parse([block])
    assert json.dumps(block) == original


@pytest.mark.parametrize("raw", [
    '[]', '{"outcome":"dialogue","blocks":[]}',
    '{"outcome":"dialogue","outcome":"admin","blocks":[]}',
    '{"outcome":"admin","blocks":[{"kind":"off_topic"}]}',
    '```json\n{"outcome":"admin","blocks":[]}\n```',
])
def test_malformed_root_and_duplicate_keys_are_not_repaired(raw):
    with pytest.raises(ValueError):
        candidate.parse(raw, service_ids=set(), active_ids=set(), topic_ids=set(), document_sections={})


def test_content_alternatives_are_present_in_the_generated_schema():
    schema = candidate.schema()
    complete = schema["$defs"]["CompletedContent"]
    pending = schema["$defs"]["PendingContent"]
    assert "content_text" not in complete["required"]
    assert complete["properties"]["clarification"]["type"] == "null"
    assert {"pending_question", "clarification"} <= set(pending["required"])
    assert pending["properties"]["content_text"]["type"] == "null"
    for definition in schema["$defs"].values():
        assert "request_id" not in definition.get("properties", {})


@pytest.fixture(scope="module")
def prepared(tmp_path_factory):
    output = tmp_path_factory.mktemp("3b-frozen")
    return experiment.prepare(output)


def context(cell):
    raw = cell["messages"][1]["content"].split("=== D2_SESSION_CONTEXT ===\n", 1)[1].split("\n\n===", 1)[0]
    return json.loads(raw)


def test_common_inputs_are_identical_for_b_c_d(prepared):
    assert len(prepared) == 12
    for name in experiment.QUESTIONS:
        group = [c for c in prepared if c["case"] == name]
        assert len({c["facts_sha256"] for c in group}) == 1
        assert len({c["history_sha256"] for c in group if c["variant"] != "A"}) == 1
        assert group[1]["messages"][1] == group[2]["messages"][1] == group[3]["messages"][1]


def test_b_only_replaces_actual_history_text_and_restores_invitation(prepared):
    a, b = [c for c in prepared if c["case"] == "continue"][:2]
    assert a["messages"][0] == b["messages"][0]
    actual, whole = context(a), context(b)
    old_pairs = actual["ordinary"].pop("dialogue_pairs")
    new_pairs = whole["ordinary"].pop("dialogue_pairs")
    assert actual == whole
    assert len(old_pairs) == len(new_pairs) == 2
    for old, new in zip(old_pairs, new_pairs):
        old.pop("assistant_text")
        new.pop("assistant_text")
        assert old == new
    shown = context(b)["ordinary"]["dialogue_pairs"][-1]["assistant_text"]
    assert "Osstem" in shown and "могу рассказать" in shown
    assert shown != context(a)["ordinary"]["dialogue_pairs"][-1]["assistant_text"]


def test_preparation_and_assessment_do_not_instantiate_live_transport(prepared, monkeypatch):
    import llm
    def forbidden(**kwargs):
        pytest.fail("unexpected provider call")
    monkeypatch.setattr(llm, "chat_completions_create", forbidden)
    d = next(c for c in prepared if c["case"] == "osstem" and c["variant"] == "D")
    assessed = experiment.assess(d, '{"outcome":"dialogue","blocks":[{"kind":"content","brand_id":"osstem"}]}')
    assert assessed["structure"] == "typed_accepted"
    assert assessed["execution_tested"] is False
    assert assessed["requires_manual_semantic_review"] is True


def test_artifacts_cannot_be_written_inside_repository():
    with pytest.raises(ValueError, match="outside_repository"):
        experiment.require_external_output(experiment.ROOT / "tmp-experiment")


def test_candidate_assessment_uses_canonical_information_topics(prepared):
    cell = next(c for c in prepared if c["variant"] == "D")
    raw = '{"outcome":"dialogue","blocks":[{"kind":"content","target":"topic:clinic"}]}'
    assert experiment.assess(cell, raw)["structure"] == "typed_accepted"
    foreign = raw.replace("topic:clinic", "topic:foreign")
    with pytest.raises(ValueError, match="unknown_target"):
        experiment.assess(cell, foreign)


def test_budget_reservations_survive_restart_and_do_not_repeat_jobs(tmp_path):
    path = tmp_path / "budget.json"
    first = experiment.AttemptLedger(path)
    assert first.reserve("qwen", "q1", {})["attempt"] == 1
    restarted = experiment.AttemptLedger(path)
    assert restarted.reserve("qwen", "q1", {}) is None
    assert restarted.reserve("qwen", "q2", {})["attempt"] == 2
    assert restarted.reserve("deepseek", "d1", {})["attempt"] == 1
    assert len(json.loads(path.read_text())["attempts"]) == 3


def test_budget_cap_is_independent_for_each_model(tmp_path):
    ledger = experiment.AttemptLedger(tmp_path / "budget.json")
    for index in range(30):
        assert ledger.reserve("qwen", f"q{index}", {})["attempt"] == index + 1
    with pytest.raises(ValueError, match="exhausted"):
        ledger.reserve("qwen", "q31", {})
    assert ledger.reserve("deepseek", "d1", {})["attempt"] == 1


def test_existing_lock_never_resets_budget(tmp_path):
    path = tmp_path / "budget.json"
    path.with_suffix(".lock").write_text("other process")
    with pytest.raises(FileExistsError):
        experiment.AttemptLedger(path).reserve("qwen", "q1", {})
    assert not path.exists()


def test_failed_attempt_remains_reserved_even_without_response_artifact(tmp_path):
    path = tmp_path / "budget.json"
    experiment.AttemptLedger(path).reserve("deepseek", "timedout", {})
    assert experiment.AttemptLedger(path).reserve("deepseek", "timedout", {}) is None
    assert len(json.loads(path.read_text())["attempts"]) == 1
