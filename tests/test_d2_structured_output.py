"""One wire description, strict HTTP generation, and a bounded capability probe."""
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from contracts.d2_dialogue_result import (
    D2DialogueResult, D2ExplanationReply, D2ExplanationTask, validate_d2_payload,
)
from core.d2_live_provider import D2HttpProvider, build_d2_d1r_messages, d2_strict_response_format
from scripts.check_d2_structured_output import MAX_CALLS, check_reply, main, prepare_cases, run_live
from tests.test_d2_live_provider_offline import _request


def task():
    return D2ExplanationTask(blocks=(
        {"kind": "content", "request_id": "r1", "target": {"type": "service", "id": "classic"},
         "brand_id": "nobel_biocare", "volume": {"extent": "one_tooth"},
         "content_ref": "implantation__faq__pain.md", "content_section_refs": ["a:pain"],
         "pending_question": "Explain the selected section"},
        {"kind": "content", "request_id": "r2", "pending_question": "Explain its continuation"},
    ))


def validate(payload):
    return validate_d2_payload(payload, active_service_ids=frozenset({"classic"}), known_task=task())


def test_reply_preserves_exact_text_and_only_server_owned_binding():
    result = validate({"explanations": [
        {"request_id": "r1", "content_text": "  First approved explanation.  "},
        {"request_id": "r2", "content_text": "Second explanation."},
    ]})
    for source, completed in zip(task().blocks, result.blocks):
        assert completed.model_dump(exclude={"content_text"}) == source.model_dump(exclude={"pending_question"})
    assert result.blocks[0].content_text == "  First approved explanation.  "
    assert result.blocks[1].content_text == "Second explanation."


@pytest.mark.parametrize("item,code", [
    ({"request_id": "r1"}, "text_required"),
    ({"request_id": "r1", "content_text": None}, "text_required"),
    ({"request_id": "r1", "content_text": ""}, "text_required"),
    ({"request_id": "r1", "content_text": " \n "}, "text_required"),
    ({"request_id": "r1", "content_text": 123}, "text_required"),
    ({"request_id": "r2", "content_text": "text"}, "invalid"),
    ({"content_text": "text"}, "invalid"),
    ({"request_id": "r1", "content_text": "text", "target": {"type": "service", "id": "foreign"}}, "invalid"),
    ({"request_id": "r1", "content_text": "text", "source": "foreign"}, "invalid"),
    ("text", "invalid"),
])
def test_reply_rejects_empty_prose_and_binding_replacement(item, code):
    with pytest.raises(ValueError, match="known_task_explanation_" + code):
        validate({"explanations": [item, {"request_id": "r2", "content_text": "Second"}]})


@pytest.mark.parametrize("payload", [
    {}, {"explanations": None}, {"explanations": []},
    {"explanations": [{"request_id": "r1", "content_text": "One"}]},
    {"explanations": [], "outcome": "dialogue"},
])
def test_reply_count_and_root_stay_strict(payload):
    with pytest.raises(ValueError, match="known_task_explanations_required"):
        validate(payload)


@pytest.mark.parametrize("items,code", [
    ([{"request_id": "r2", "content_text": ""}, {"request_id": "r2", "content_text": "OK"}], "invalid"),
    ([{"request_id": "r1", "content_text": ""}, {"request_id": "r2", "content_text": "OK", "target": "foreign"}], "text_required"),
    ([{"request_id": "r1", "content_text": "", "source": "foreign"}, {"request_id": "r2", "content_text": "OK"}], "invalid"),
    ([{"request_id": "r1", "content_text": "OK"}, {"request_id": "r2", "content_text": ""}], "text_required"),
])
def test_previous_first_error_priority_is_preserved(items, code):
    with pytest.raises(ValueError, match="known_task_explanation_" + code):
        validate({"explanations": items})


@pytest.mark.parametrize("known", [False, True])
def test_strict_format_is_generated_from_the_same_runtime_types(known):
    request = replace(_request(), known_task=task() if known else None)
    fmt = d2_strict_response_format(request)
    expected = D2ExplanationReply if known else D2DialogueResult
    assert fmt["type"] == "json_schema" and fmt["json_schema"]["strict"] is True
    assert fmt["json_schema"]["schema"] == expected.model_json_schema()
    schema = fmt["json_schema"]["schema"]
    assert schema["type"] == "object" and schema["additionalProperties"] is False
    if known:
        assert set(schema["properties"]) == {"explanations"}
        assert set(schema["$defs"]["D2ExplanationReplyItem"]["properties"]) == {"request_id", "content_text"}
    else:
        assert set(schema["properties"]) == {"outcome", "blocks"}
        items = schema["properties"]["blocks"]["items"]
        assert len(items["oneOf"]) == 9
        assert len(items["discriminator"]["mapping"]) == 9


@pytest.mark.parametrize("known", [False, True])
def test_http_retains_json_object_after_adverse_strict_comparison(known):
    request = replace(_request(), known_task=task() if known else None)
    calls = []
    def transport(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))])
    assert D2HttpProvider(transport=transport).generate(request) == "{}"
    assert len(calls) == 1
    assert calls[0]["response_format"] == {"type": "json_object"}
    assert calls[0]["messages"] == build_d2_d1r_messages(request)
    assert calls[0]["max_completion_tokens"] == 1024
    assert calls[0]["provider_call_source"] == "d2_http"


def response(raw):
    return SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(content=raw), finish_reason="stop")])


def test_probe_checks_all_real_schemas_and_stops_at_four(tmp_path):
    cases = prepare_cases()
    raws = [json.dumps({"probe": "ok"}), json.dumps({"outcome": "dialogue", "blocks": [
        {"kind": "price", "request_id": "r1", "target": {"type": "topic", "id": "implantation"},
         "brand_id": "nobel_biocare"}]}), json.dumps({"outcome": "dialogue", "blocks": [
        {"kind": "price", "request_id": "r1", "target": {"type": "service", "id": "whitening"}},
        {"kind": "contact", "request_id": "r2", "contact_fields": ["contact_address"]}]}),
        json.dumps({"explanations": [{"request_id": "r1", "content_text": "Explanation."}]}),
    ]
    calls = []
    def transport(**kwargs):
        reserved = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
        assert reserved["attempts"] == len(calls) + 1
        calls.append(kwargs)
        return response(raws[len(calls) - 1])
    report = run_live(cases, output=tmp_path, model="fake", transport=transport)
    assert report["attempts"] == len(calls) == MAX_CALLS
    assert [r["operation_kinds"] for r in report["results"]] == [[], ["price"], ["price", "contact"], ["content"]]
    assert all(r["status"] == "parser_accepted" for r in report["results"])
    assert [c["response_format"] for c in calls] == [c["response_format"] for c in cases]
    with pytest.raises(FileExistsError):
        run_live(cases, output=tmp_path, model="fake", transport=transport)
    assert len(calls) == MAX_CALLS


@pytest.mark.parametrize("failure", ["schema_rejected", "array", "context"])
def test_probe_stops_on_failure_without_retry_fallback_or_secret_report(tmp_path, failure):
    cases = prepare_cases()
    calls = []
    def transport(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1 and failure != "schema_rejected":
            return response('{"probe":"ok"}')
        if failure == "schema_rejected":
            raise RuntimeError("PRIVATE provider body")
        if failure == "context":
            return response('{"outcome":"dialogue","blocks":[]}')
        return response('[{"kind":"price"}]')
    report = run_live(cases, output=tmp_path, model="fake", transport=transport)
    assert len(calls) == (1 if failure == "schema_rejected" else 2)
    assert report["results"][-1]["status"] == "failed"
    assert report["results"][-1]["stage"] == ("transport" if failure == "schema_rejected" else "parse")
    assert "PRIVATE" not in (tmp_path / "report.json").read_text(encoding="utf-8")
    assert all(c["response_format"]["type"] == "json_schema" for c in calls)


def test_dry_run_has_no_transport_or_artifacts(monkeypatch, capsys):
    import llm
    monkeypatch.setattr(llm, "chat_completions_create", lambda **kwargs: pytest.fail("provider forbidden"))
    assert main([]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["provider_calls"] == 0
    assert [c["name"] for c in summary["cases"]] == [
        "simple_schema", "ordinary_price", "ordinary_compound", "known_explanation"]


def test_live_cli_requires_explicit_budget_and_output():
    with pytest.raises(SystemExit):
        main(["--live"])


def test_root_array_is_not_wrapped_or_published():
    cases = prepare_cases()
    for case in cases[1:]:
        with pytest.raises(ValueError, match="envelope_not_object"):
            check_reply(case, '[{"kind":"price","request_id":"r1"}]')
