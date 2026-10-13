"""Full captured terms reach ordinary and verified-click prompts without live calls."""
import json
from pathlib import Path

import pytest

from tests.test_d2_http_contract import http_env, post, post_sse
from tests.test_d2_document_click_task_http import PromptProvider, _body, _raw


def _facts(messages):
    text = messages[0]["content"].split("=== COMMERCIAL_FACT_CATALOG ===\n", 1)[1]
    return json.JSONDecoder().raw_decode(text)[0]


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_fact_source_changes_reach_ordinary_and_verified_click(http_env, transport):
    client, _, use_provider, root = http_env
    path = root / "clients/demo/target_response/pricebook/facts.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["implant_warranty"]["text_fact"] = "Уникальные полные условия из источника фактов."
    data["implant_warranty"]["microfact_text"] = "Краткие условия из того же источника."
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    provider = use_provider(PromptProvider(_raw("Пояснение о гарантии.", ref="clinic__info__warranty.md")))
    send = post if transport == "json" else post_sse
    first = _body(send(client, q="Какая гарантия?", request_id="first"), transport)
    ref = "clinic__info__warranty.md#chto-delat-esli-voznikla-problema"
    assert any(row["reply_id"] == ref for row in first["ui"]["quick_replies"])
    original = _facts(provider.messages[0])
    rows = {row["fact_id"]: row for row in original["facts"]}
    assert rows["implant_warranty"]["text_fact"] == data["implant_warranty"]["text_fact"]
    assert rows["implant_warranty"]["microfact_text"] == data["implant_warranty"]["microfact_text"]
    for field in ("excluded_scope_text", "excluded_service_ids", "incompatible_with", "requested_display_policy"):
        assert rows["installment_12"][field] == data["installment_12"][field]
    assert rows["free_implant_consult"]["active_until"] == data["free_implant_consult"]["active_until"]
    provider.raw = json.dumps({"explanations": [{"request_id": "r1", "content_text": "Порядок обращения по гарантии."}]})
    args = dict(q="", ref=ref, ui_revision=first["revision"], request_id="click")
    second = _body(send(client, **args), transport)
    assert second["answer"] == "Порядок обращения по гарантии."
    assert provider.inputs[-1].known_task is not None
    assert _facts(provider.messages[-1]) == original
    assert _body(send(client, **args), transport) == second
    assert len(provider.inputs) == 2


def test_demo_fact_publication_strings_are_whole_paragraphs():
    data = json.loads(Path("clients/demo/target_response/pricebook/facts.json").read_text(encoding="utf-8"))
    for fact in data.values():
        for field in ("catalog_label", "text_fact", "microfact_text"):
            if field in fact:
                text = fact[field]
                assert text == text.strip()
                assert not any(char in text for char in "\r\n\t")
                assert "  " not in text
