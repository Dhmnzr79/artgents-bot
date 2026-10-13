"""Active text protocol; migrated native assertions without an API-tools adapter."""
import json
from types import SimpleNamespace
import pytest
from contracts.d2_dialogue_result import parse_d2_text_reply, D2RejectedOperation, D2ExplanationTask, AuthorizedExplanationOperation
from core.d2_live_provider import _plain_text_reply, D2LiveProviderError


def action(name, **arguments):
    return {"name":name,"arguments":arguments}


def response(text="", *, actions=(), sources=None):
    metadata={"actions":list(actions)}
    if sources is not None: metadata["sources"]=list(sources)
    return (text or "")+"\n<D2_META>\n"+json.dumps(metadata,ensure_ascii=False)+"\n</D2_META>"


def parse(raw, **kwargs):
    return parse_d2_text_reply(raw,active_service_ids={"classic","sinus_lift"},**kwargs)


@pytest.mark.parametrize("args",[[{}],"{",{"target":0},{"request_id":"r1"},{"kind":"price"},{"brand_id":5},{"option_id":0}])
def test_bad_action_arguments_keep_written_prose(args):
    arguments = {"contact_fields": ["contact_phone"], **args} if isinstance(args, dict) else args
    result=parse(response("Готовый ответ.",actions=[{"name":"show_contacts","arguments":arguments}]))
    assert result.blocks[0].content_text=="Готовый ответ."
    assert isinstance(result.blocks[1],D2RejectedOperation)
    assert result.blocks[1].kind=="contact"


def test_tail_price_cannot_restore_removed_command():
    result = parse(response("Готовый ответ.", actions=[action("show_price", target={"type":"service","id":"classic"})]))
    assert result.blocks[0].content_text == "Готовый ответ."
    assert isinstance(result.blocks[1], D2RejectedOperation)
    assert result.blocks[1].kind == "reference"


def test_duplicate_key_tail_keeps_text_but_executes_nothing():
    result=parse('Ответ.\n<D2_META>\n{"actions":[],"actions":[]}\n</D2_META>')
    assert result.blocks[0].content_text=="Ответ."
    assert len(result.blocks)==1


@pytest.mark.parametrize("bad",["{",{"target":0},{"content_ref":"../foreign.md"}])
def test_bad_source_keeps_unscoped_sibling_slot(bad):
    result=parse(response("Ответ.",sources=[{"content_ref":"one.md"},bad]))
    assert len(result.source_claims)==2
    assert result.source_claims[1].content_ref is None


def test_text_first_actions_in_order_and_identity_owned_by_server():
    result=parse(response("Вступление.",actions=[action("show_price",target={"type":"service","id":"classic"}),action("show_contacts",contact_fields=["contact_address"])],sources=[{"content_ref":"one.md"}]))
    assert [b.kind for b in result.blocks]==["content","reference","contact"]
    assert isinstance(result.blocks[1], D2RejectedOperation)
    assert [b.request_id for b in result.blocks]==["r1","r2","r3"]


@pytest.mark.parametrize("name", ["clarify_content", "doctors"])
def test_removed_information_command_rejected_without_losing_prose(name):
    result=parse(response("Ответ.",actions=[action(name,pending_question="Что?",clarification={"missing":"service","choices":["classic","sinus_lift"]})]))
    assert result.blocks[0].content_text=="Ответ."
    assert isinstance(result.blocks[1],D2RejectedOperation)


def test_known_task_requires_single_text_and_cannot_be_reclassified():
    task=D2ExplanationTask(blocks=(AuthorizedExplanationOperation(
        kind="content",request_id="r1",target={"type":"service","id":"classic"},
        brand_id="nobel_biocare",volume={"extent":"one_tooth"},
        content_ref="known.md",content_section_refs=["a:pain"],pending_question="Explain"),))
    result=parse(response("Section answer.",actions=[action("handoff")],sources=[{"content_ref":"other.md"}]),known_task=task)
    assert result.outcome=="dialogue"
    assert result.blocks[0].model_dump(exclude={"content_text"}) == task.blocks[0].model_dump(exclude={"pending_question"})
    assert result.blocks[0].content_text == "Section answer."
    assert result.source_claims is None
    for invalid in (" ",):
        with pytest.raises(ValueError):parse(invalid,known_task=task)
    with pytest.raises(ValueError):parse("Answer",known_task=task.model_copy(update={"blocks":task.blocks*2}))


@pytest.mark.parametrize("content",[None,"", " ", {}, []])
def test_provider_non_text_or_empty_reply_is_failure_even_with_unsolicited_tools(content):
    with pytest.raises(D2LiveProviderError):
        _plain_text_reply(SimpleNamespace(content=content,tool_calls=[SimpleNamespace(function=SimpleNamespace(name="show_price",arguments="{}"))]))


def test_provider_uses_only_text_no_native_adapter():
    assert _plain_text_reply(SimpleNamespace(content="Text",tool_calls=[SimpleNamespace()]))=="Text"
    with pytest.raises(ValueError):parse({"text":"Text","tool_calls":[]})


def test_ordinary_pending_still_absent_from_schema_and_session():
    from pydantic import TypeAdapter,ValidationError
    from contracts.d2_dialogue_result import ExplanationOperation,ClarifiedOperation
    from contracts.d2_session_context import D2OrdinarySessionContext
    assert not {"clarification","pending_question"} & ExplanationOperation.model_fields.keys()
    old=dict(kind="content",request_id="r1",pending_question="Which?",clarification={"missing":"service","choices":["classic","sinus_lift"]})
    with pytest.raises(ValidationError):ExplanationOperation.model_validate(old)
    with pytest.raises(ValidationError):TypeAdapter(ClarifiedOperation).validate_python(old)
    with pytest.raises(ValidationError):D2OrdinarySessionContext(clarify_pending=True,clarify_task=old)


def test_active_runtime_contains_no_native_channel_or_archive_import():
    import ast
    from pathlib import Path
    import contracts.d2_dialogue as provider_contract
    import contracts.d2_dialogue_result as result_contract
    import core.d2_live_provider as provider
    assert not hasattr(provider_contract,"D2ProviderReply")
    assert not hasattr(provider_contract,"D2ToolCall")
    assert not hasattr(result_contract,"parse_d2_native_reply")
    assert not hasattr(result_contract,"d2_native_tools")
    assert not hasattr(provider,"_native_reply")
    for path in [Path("core/d2_dialogue.py"),Path("core/d2_live_provider.py"),Path("contracts/d2_dialogue.py"),Path("contracts/d2_dialogue_result.py")]:
        tree=ast.parse(path.read_text(encoding="utf-8"))
        assert all(not isinstance(n,ast.ImportFrom) or n.module!="scripts.native_transport_archive" for n in ast.walk(tree))


def test_cp3_provider_uses_same_single_text_contract_without_tools():
    from core.d2_live_provider import D2Cp3LiveProvider
    from tests.test_d2_live_provider_offline import _request
    calls=[]
    def transport(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Ответ."))])
    provider=D2Cp3LiveProvider(transport=transport)
    assert provider.generate(_request())=="Ответ."
    assert not {"tools","tool_choice","response_format"}.intersection(calls[0])


@pytest.mark.parametrize("known", [False, True])
def test_current_http_reply_has_no_json_envelope_requirement(known):
    from dataclasses import replace
    from tests.test_d2_live_provider_offline import _request
    from core.d2_live_provider import D2HttpProvider, build_d2_d1r_messages
    task = D2ExplanationTask(blocks=(AuthorizedExplanationOperation(
        kind="content", request_id="r1", content_ref="known.md", pending_question="Explain"),))
    request = replace(_request(), known_task=task if known else None)
    calls=[]
    def transport(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Section answer."))])
    assert D2HttpProvider(transport=transport).generate(request) == "Section answer."
    assert len(calls) == 1 and 'response_format' not in calls[0]
    assert calls[0]['max_completion_tokens'] == 1536
    assert calls[0]['provider_call_source'] == 'd2_http'
    assert calls[0]['messages'] == build_d2_d1r_messages(request)
    if known:
        assert not {'tools','tool_choice'} & calls[0].keys()
    else:
        assert calls[0]['tool_choice'] == 'auto'
        assert [tool['function']['name'] for tool in calls[0]['tools']] == ['show_price']
