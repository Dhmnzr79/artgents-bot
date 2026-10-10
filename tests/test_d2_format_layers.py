"""Offline guards for an isolated experiment, not runtime semantic guarantees."""
import json
from types import SimpleNamespace

import pytest

from scripts.check_d2_format_layers import MAX_CALLS, assess, prepare_cases, run


@pytest.fixture(scope="module")
def cases():
    return prepare_cases()


def correct_raw(case):
    target = {"type": "service", "id": "professional_whitening"} if case["name"] == "compound" else {"type": "topic", "id": "implantation"}
    price = {"kind": "price", "request_id": "r1", "target": target}
    if case["name"] == "nobel":
        price["brand_id"] = "nobel_biocare"
    blocks = [price]
    if case["name"] == "compound":
        blocks.append({"kind": "contact", "request_id": "r2", "contact_fields": ["contact_address"]})
    if case["layer"] == "small":
        actions = []
        for block in blocks:
            action = {"action": block["kind"]}
            if "target" in block:
                action.update(target_type=target["type"], target_id=target["id"])
            for field in ("brand_id", "contact_fields"):
                if field in block:
                    action[field] = block[field]
            actions.append(action)
        return json.dumps({"actions": actions})
    return json.dumps({"outcome": "dialogue", "blocks": blocks})


def test_pairs_and_repetitions_share_inputs_and_allow_real_clarification(cases):
    assert len(cases) == MAX_CALLS == 48
    assert {c["layer"] for c in cases} == {"small", "full_schema", "full_instructions", "full_context"}
    for i in range(0, len(cases), 2):
        a, b = cases[i:i + 2]
        assert a["request"] == b["request"] and a["messages"] == b["messages"]
        assert a["mode"] != b["mode"]
        assert a["request"].context.ordinary.dialogue_pairs == ()
    assert "clarify_service" in json.dumps(cases[1]["response_format"])
    for case in cases:
        assert assess(case, correct_raw(case))[1] == []


@pytest.mark.parametrize("layer", ["small", "full_schema", "full_instructions", "full_context"])
def test_semantics_reject_false_clarification_and_missing_address(cases, layer):
    case = next(c for c in cases if c["layer"] == layer and c["name"] == "compound")
    raw = json.dumps({"actions": [{"action": "clarify_service", "choices": ["professional_whitening", "veneers"]}]}) if layer == "small" else json.dumps({"outcome": "dialogue", "blocks": [{"kind": "price", "request_id": "r1", "clarification": {"missing": "service", "choices": ["professional_whitening", "veneers"]}}]})
    assert set(assess(case, raw)[1]) == {"wrong_or_missing_price_target", "unnecessary_clarification", "address_omitted"}


def test_budget_reservations_no_resume_and_no_prompt_persistence(cases, tmp_path):
    calls = []
    def transport(**kwargs):
        stored = json.loads((tmp_path / "report.json").read_text())
        assert stored["attempts"] == len(calls) + 1
        assert stored["results"][-1]["status"] == "reserved"
        raw = correct_raw(cases[len(calls)])
        calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=raw))])
    report = run(cases, output=tmp_path, model="fake", transport=transport)
    assert len(calls) == 48 and all(r["target_checks_pass"] for r in report["results"])
    assert all(c["max_completion_tokens"] == 1024 for c in calls)
    assert "system" not in (tmp_path / "report.json").read_text()
    with pytest.raises(FileExistsError):
        run(cases, output=tmp_path, model="fake", transport=transport)
    assert len(calls) == 48


def test_transport_failure_stops_without_retry_or_body(cases, tmp_path):
    calls = []
    def transport(**kwargs):
        calls.append(kwargs)
        raise RuntimeError("PRIVATE PROVIDER BODY")
    report = run(cases, output=tmp_path, model="fake", transport=transport)
    assert report["attempts"] == len(calls) == 1
    assert report["results"][0]["stage"] == "transport"
    assert "PRIVATE" not in (tmp_path / "report.json").read_text()


def test_bad_format_is_recorded_without_repair_or_repeat(cases, tmp_path):
    calls = []
    def transport(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content="[]"))])
    report = run(cases, output=tmp_path, model="fake", transport=transport)
    assert report["attempts"] == len(calls) == 48
    assert all(r["status"] == "failed" and r["stage"] == "parse" for r in report["results"])
