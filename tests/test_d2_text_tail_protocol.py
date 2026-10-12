"""Isolated replacement experiment: prose survives metadata and domain guards stay."""
import json
import pytest
from tests.d2_ci_http import http_env
from contracts.d2_dialogue_result import parse_d2_text_reply as parse_text_tail
from contracts.d2_dialogue_result import D2RejectedOperation, D2ExplanationTask, AuthorizedExplanationOperation


def raw(text="", **metadata):
    return text + "\n<D2_META>\n" + json.dumps(metadata,ensure_ascii=False) + "\n</D2_META>"


def action(name="show_price", **arguments):
    return {"name":name,"arguments":arguments}


def parse(value, **kwargs):
    return parse_text_tail(value,active_service_ids={"classic","sinus_lift"},**kwargs)


@pytest.mark.parametrize("text",["Ответ по базе.",'{"outcome":"admin"}',"Ответ "*1200],ids=["plain","json-is-prose","long"])
def test_plain_prose_not_a_structural_command(text):
    assert parse(text).blocks[0].content_text==text.strip()


@pytest.mark.parametrize("tail",[
    '<D2_META>\n{',
    '<D2_META>\n{}\n</D2_META>\nextra',
    '<D2_META>\n{}\n</D2_META>\n<D2_META>\n{}\n</D2_META>',
    '<D2_META>\n{"sources":[],"sources":[]}\n</D2_META>',
    '<D2_META>\n{"sources":null}\n</D2_META>',
    '<D2_META>\n{"unexpected":1}\n</D2_META>',
    '<D2_META>\n{}</D2_META>',
])
def test_damaged_whole_tail_keeps_prose_without_executing(tail):
    result=parse("Да, используем Nobel.\n"+tail)
    assert result.blocks[0].content_text=="Да, используем Nobel."
    assert len(result.blocks)==1
    assert result.source_claims is None


@pytest.mark.parametrize("value",["",raw(sources=[{"content_ref":"one.md"}]),raw(actions=[action(target=0)])])
def test_missing_answer_or_accepted_action_is_failure(value):
    with pytest.raises(ValueError):parse(value)


def test_price_only_and_invalid_first_price_position_are_preserved():
    valid=action(target={"type":"service","id":"classic"},brand_id="nobel_biocare",volume={"extent":"one_tooth"})
    assert parse(raw(actions=[valid])).blocks[0].brand_id=="nobel_biocare"
    result=parse(raw("Объяснение.",actions=[action(target=0),valid]))
    assert isinstance(result.blocks[1],D2RejectedOperation)
    assert result.blocks[1].kind=="price"
    assert [b.request_id for b in result.blocks]==["r1","r2","r3"]


@pytest.mark.parametrize("bad",[None,{"name":[],"arguments":{}},{"name":"show_price","arguments":"{}"},action(request_id="r1"),action("price_detail")])
def test_bad_action_does_not_cancel_text(bad):
    result=parse(raw("Гарантия по договору.",actions=[bad]))
    assert result.blocks[0].content_text=="Гарантия по договору."
    assert isinstance(result.blocks[1],D2RejectedOperation)


def test_source_multiplicity_and_invalid_sibling_remain():
    result=parse(raw("Ответ.",sources=[{"content_ref":"one.md"},{"content_ref":"../other.md"},{"content_ref":"one.md"}]))
    assert [c.content_ref for c in result.source_claims]==["one.md",None,"one.md"]


def test_handoff_exclusive_but_invalid_handoff_not_admin():
    assert parse(raw("Текст.",actions=[action(target=0),action("handoff")])).outcome=="admin"
    result=parse(raw("Текст.",actions=[action("handoff",injected=True)]))
    assert result.outcome=="dialogue"
    assert isinstance(result.blocks[1],D2RejectedOperation)


def test_known_document_retains_authorized_source_and_identity():
    task=D2ExplanationTask(blocks=(AuthorizedExplanationOperation(kind="content",request_id="r9",content_ref="approved.md",pending_question="Section"),))
    result=parse(raw("Ответ раздела.",sources=[{"content_ref":"other.md"}],actions=[action("handoff")]),known_task=task)
    assert result.outcome=="dialogue"
    assert result.blocks[0].request_id=="r9"
    assert result.blocks[0].content_ref=="approved.md"


def test_actual_fullcontext_builder_keeps_complete_corpus_and_one_tail_contract():
    from tests.test_d2_live_provider_offline import _request
    from core.d2_live_provider import build_d2_d1r_messages
    request=_request()
    system,user=build_d2_d1r_messages(request)
    assert request.model_view.approved_md_corpus in system["content"]
    assert request.model_view.service_reference_catalog.block_text() in system["content"]
    assert request.context.model_dump_json() in user["content"]
    assert system["content"].count("=== D2_OPERATIONS_INSTRUCTIONS ===")==1
    assert "API tools are not available" in system["content"]
    assert "D2_RESULT_SCHEMA" not in system["content"]


@pytest.fixture
def tail_http(http_env):
    # Actual runtime provider/parser path, no parser replacement fixture.
    return http_env


@pytest.mark.parametrize("transport",["json","sse"])
def test_downstream_price_history_then_prose_and_known_detail(tail_http,transport):
    from tests.d2_ci_http import FakeProvider,send,click
    from tests.test_d2_price_cards import cards
    from tests.test_d2_sim2_dialogues import forbidden
    client,db,use,_=tail_http
    fake=use(FakeProvider(raw(actions=[action(target={"type":"service","id":"classic"},brand_id="nobel_biocare",volume={"extent":"one_tooth"})])))
    body=send(client,transport,q="Цена Nobel на один зуб?",request_id="price")
    row=cards(body)[0]["price"]["rows"][0]
    assert (row["offer_id"],row["amount"])==("classic.one_tooth.nobel",101200)
    fake.generate=forbidden
    selected=click(client,body,"price_detail:includes",transport=transport,request_id="includes")
    assert row["includes"][0] in selected["answer"]
    assert len(fake.inputs)==1
    fake.generate=FakeProvider.generate.__get__(fake,FakeProvider)
    fake.raw="Гарантия по договору и паспорту системы."
    body=send(client,transport,q="А гарантия?",request_id="guarantee")
    assert "Гарантия по договору" in body["answer"]
    assert not cards(body)
    assert "Nobel" in fake.inputs[-1].context.ordinary.dialogue_pairs[-1].assistant_text


@pytest.mark.parametrize("transport",["json","sse"])
def test_invalid_first_price_not_promoted_and_text_survives(tail_http,transport):
    from tests.d2_ci_http import FakeProvider,send
    from tests.test_d2_price_cards import cards
    client,_,use,_=tail_http
    use(FakeProvider(raw("Самостоятельный ответ.",actions=[action(target=0),action(target={"type":"service","id":"classic"})])))
    body=send(client,transport,q="Расскажите и цена?",request_id="mixed")
    assert "Самостоятельный ответ." in body["answer"]
    assert not cards(body)


@pytest.mark.parametrize("transport",["json","sse"])
def test_source_followup_uses_authorized_document_task(tail_http,transport):
    from tests.d2_ci_http import FakeProvider,send,click
    client,_,use,_=tail_http
    fake=use(FakeProvider(raw("Объяснение страха боли.",sources=[{"content_ref":"implantation__faq__pain.md","target":{"type":"topic","id":"implantation"}}])))
    body=send(client,transport,q="Я боюсь боли.",request_id="pain")
    refs=[q["reply_id"] for q in body["ui"]["quick_replies"] if q["reply_id"].startswith("implantation__faq__pain.md#")]
    assert refs
    fake.raw="Ответ выбранного раздела."
    selected=click(client,body,refs[0],transport=transport,request_id="followup")
    assert "Ответ выбранного раздела." in selected["answer"]
    assert fake.inputs[-1].known_task is not None
    assert len(fake.inputs)==2
