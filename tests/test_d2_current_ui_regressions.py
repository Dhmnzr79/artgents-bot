"""Current volume navigation and clicked-only follow-ups; no live provider."""
import json

import pytest

from core.d2_live_provider import D2HttpProvider
from tests.test_d2_http_contract import http_env
from tests.test_d2_demo_release_gate import call
from tests.test_d2_native_price_runtime import Transport, message


DOC = "clinic__info__warranty.md"
REFS = [f"{DOC}#chto-delat-esli-voznikla-problema",
        f"{DOC}#pochemu-garantiya-na-rabotu-vracha-1-god"]


def refs(body):
    return [item["reply_id"] for item in body["ui"]["quick_replies"]]


@pytest.mark.parametrize("section", ["korotko", "a:korotko", "not-a-section"])
def test_warranty_lower_click_keeps_upper_then_exhausts(http_env, section):
    client, _, use, _ = http_env
    text = "Условия гарантии закреплены в договоре."
    raw = text + "\n<D2_META>\n" + json.dumps({"sources": [{
        "content_ref": DOC, "content_section_refs": [section]}]}) + "\n</D2_META>"
    wire = Transport(message(raw), message("Почему срок ограничен."),
                     message("Как обратиться за помощью."))
    use(D2HttpProvider(transport=wire))
    first = call(client, request_id="first", q="Какая гарантия?")
    assert first["answer"] == text
    if section == "not-a-section":
        assert refs(first) == []
        return
    assert refs(first) == REFS
    second = call(client, request_id="lower", q="", ref=REFS[1], ui_revision=first["revision"])
    assert refs(second) == REFS[:1]
    assert call(client, request_id="lower", q="", ref=REFS[1], ui_revision=first["revision"]) == second
    third = call(client, request_id="upper", q="", ref=REFS[0], ui_revision=second["revision"])
    assert refs(third) == []
    assert len(wire.calls) == 3


@pytest.mark.parametrize("volume", [None, {"extent": "unknown"}])
def test_topic_volume_navigation_remains_after_click(http_env, volume):
    client, _, use, _ = http_env
    args = {"target": {"type": "topic", "id": "implantation"}}
    if volume is not None:
        args["volume"] = volume
    wire = Transport(message(None, args), message("<NO_TEXT>"))
    use(D2HttpProvider(transport=wire))
    first = call(client, request_id="first", q="Сколько стоит имплантация?")
    expected = [f"volume:implantation:{extent}" for extent in ("one_tooth", "full_arch", "unknown")]
    assert [r for r in refs(first) if r.startswith("volume:")] == expected
    for index, ref in enumerate([expected[0], expected[1], expected[2]]):
        first = call(client, request_id=f"click{index}", q="", ref=ref, ui_revision=first["revision"])
        assert [r for r in refs(first) if r.startswith("volume:")] == expected
        assert "Какой объём вас интересует" not in first["answer"]
    assert len(wire.calls) == 2
