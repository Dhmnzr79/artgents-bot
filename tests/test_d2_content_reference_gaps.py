"""Stage 1: reject unconfirmed prose locally through the real JSON/SSE routes."""
from datetime import date

import pytest

from contracts.response_plan import SessionKey
from contracts.response_plan_materialization import MaterializationOwnershipError
from core.d2_dialogue_store import D2DialogueStore
from core.response_plan_materialization import resolve_d2_operations
from tests.d2_ci_http import FakeProvider, completed_context, http_env, raw, send
from tests.test_d2_af1b_contacts_http import DEMO_ADDRESS


PROSE = "Неподтверждённое объяснение."
GAP = "К сожалению, у меня пока недостаточно информации по этому вопросу"
SOURCE = "implantation__info__implant_systems.md"
UNKNOWN = [("service", "absent_service"), ("service", "implantation"), ("topic", "absent_topic")]


@pytest.fixture(autouse=True)
def audit_off(monkeypatch):
    monkeypatch.setenv("D2_FULL_AUDIT_LOG", "0")


def content(target, source=SOURCE):
    block = {"kind": "content", "request_id": "r1", "content_text": PROSE}
    if target is not None:
        block["target"] = {"type": target[0], "id": target[1]}
    if source is not None:
        block["content_ref"] = source
    return block


def check_gap(resolved):
    part = next(p for p in resolved.d2_request_parts if p.request_id == "r1")
    assert (part.status, part.failure_reason) == ("unavailable", "d2_content_source_missing")
    assert (part.service_id, part.topic_id, part.discussion_scope, part.content_ref) == (None, None, None, None)
    assert part.scope == "mixed" and not part.content_section_refs
    assert part.content_publication is None
    assert not resolved.information_blocks
    assert len(resolved.d2_part_failure_blocks) == 1
    assert resolved.d2_part_failure_blocks[0].display_text == GAP
    assert resolved.ui_plan.source_content_ref is None


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("target", UNKNOWN)
@pytest.mark.parametrize("source", [SOURCE, "missing.md", None])
def test_unknown_subject_never_publishes_prose_even_without_source(http_env, transport, target, source):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(content(target, source))))
    args = dict(sid="content-gap", request_id="gap", q="Расскажите об услуге")
    body = send(client, transport, **args)
    assert PROSE not in body["answer"] and body["answer"].count(GAP) == 1
    key = SessionKey(client_id="demo", sid="content-gap")
    with D2DialogueStore(db) as store:
        resolved = store.read_latest_completion(key).response.resolved
        check_gap(resolved)
        assert resolved.d2_result_status == "failed"
        assert resolved.response_scope == "mixed"
        context = completed_context(store, key).ordinary
        assert context.discussion_scope is None and not context.d2_shown_price_offer_refs
        assert PROSE not in context.dialogue_pairs[-1].assistant_text
    assert send(client, transport, **args) == body
    assert len(fake.inputs) == 1


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("target", UNKNOWN)
@pytest.mark.parametrize("independent", ["contact", "price"])
@pytest.mark.parametrize("before", [True, False])
def test_independent_answer_survives_in_original_order(http_env, transport, target, independent, before):
    client, db, use, _ = http_env
    good = ({"kind": "contact", "request_id": "r2", "contact_fields": ["contact_address"]}
        if independent == "contact" else
        {"kind": "price", "request_id": "r2", "target": {"type": "service", "id": "classic"}})
    blocks = [good, content(target)] if before else [content(target), good]
    fake = use(FakeProvider(raw(*blocks)))
    body = send(client, transport, sid="mixed-gap", request_id="mixed", q="Два вопроса")
    marker = DEMO_ADDRESS if independent == "contact" else "₽"
    assert marker in body["answer"] and PROSE not in body["answer"]
    assert (body["answer"].index(marker) < body["answer"].index(GAP)) is before
    with D2DialogueStore(db) as store:
        resolved = store.read_latest_completion(SessionKey(client_id="demo", sid="mixed-gap")).response.resolved
        check_gap(resolved)
        assert [p.request_id for p in resolved.d2_request_parts] == [b["request_id"] for b in blocks]
        assert resolved.d2_result_status == "degraded"
        if independent == "price":
            assert resolved.finalized_commercial_ids.price_offer_ids == ("classic.one_tooth.implantium",)
            assert [r.offer_id for r in resolved.d2_price_block.rows] == ["classic.one_tooth.implantium"]
    assert len(fake.inputs) == 1


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("source", [None, "missing.md"])
def test_valid_subject_keeps_optional_unattributed_prose(http_env, transport, source):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(content(("service", "classic"), source))))
    body = send(client, transport, sid="valid-prose")
    assert PROSE in body["answer"] and GAP not in body["answer"]
    with D2DialogueStore(db) as store:
        resolved = store.read_latest_completion(SessionKey(client_id="demo", sid="valid-prose")).response.resolved
        part = resolved.d2_request_parts[0]
        assert part.status == "answered" and part.service_id == "classic"
        assert part.content_ref is None and resolved.information_blocks[0].content_ref is None
    assert len(fake.inputs) == 1


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_unknown_subject_clears_previous_discussion_without_rejected_history(http_env, transport):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw({"kind": "price", "request_id": "r1", "target": {"type": "service", "id": "classic"}})))
    send(client, transport, sid="next-gap", request_id="price")
    fake.raw = raw(content(("service", "implantation")))
    send(client, transport, sid="next-gap", request_id="gap")
    assert fake.inputs[-1].context.ordinary.discussion_scope.service_id == "classic"
    fake.raw = raw({"kind": "contact", "request_id": "r1", "contact_fields": ["contact_address"]})
    body = send(client, transport, sid="next-gap", request_id="next")
    context = fake.inputs[-1].context.ordinary
    assert DEMO_ADDRESS in body["answer"]
    assert context.discussion_scope is None and not context.d2_shown_price_offer_refs
    assert PROSE not in context.dialogue_pairs[-1].assistant_text
    part = context.dialogue_pairs[-1].parts[0]
    assert part.service_id is None and part.topic_id is None and part.discussion_scope is None
    assert len(fake.inputs) == 3


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("before", [True, False])
def test_unknown_content_does_not_block_independent_price_detail(http_env, transport, before):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw({"kind": "price", "request_id": "r1", "target": {"type": "service", "id": "classic"}})))
    send(client, transport, sid="detail-gap", request_id="price")
    detail = {"kind": "price_detail", "request_id": "r2", "price_detail_aspect": "includes"}
    blocks = [content(("service", "implantation")), detail] if before else [detail, content(("service", "implantation"))]
    fake.raw = raw(*blocks)
    body = send(client, transport, sid="detail-gap", request_id="details")
    assert PROSE not in body["answer"] and GAP in body["answer"]
    with D2DialogueStore(db) as store:
        resolved = store.read_latest_completion(SessionKey(client_id="demo", sid="detail-gap")).response.resolved
        check_gap(resolved)
        assert resolved.d2_result_status == "degraded"
        assert [r.offer_id for r in resolved.d2_price_detail_blocks[0].rows] == ["classic.one_tooth.implantium"]
        assert next(p for p in resolved.d2_request_parts if p.request_id == "r2").status == "answered"
    assert len(fake.inputs) == 2


def test_foreign_source_stays_fatal_even_for_unknown_subject():
    from tests.test_d2_independent_request_parts import _sources_ab, _part, _envelope
    sources = _sources_ab()
    foreign = sources.d2_authored_content[0].model_copy(update={"source_client_id": "nikadent"})
    sources = sources.model_copy(update={"d2_authored_content": (foreign,)})
    operation = _part("r1", "content", service_id="absent_service", topic_id=None, content_ref=foreign.content_ref)
    with pytest.raises(MaterializationOwnershipError, match="materialization_foreign_material"):
        resolve_d2_operations(_envelope([operation]).blocks, sources, as_of=date(2026, 9, 18))


def test_foreign_direction_stays_fatal_for_content():
    from tests.test_d2_independent_request_parts import _sources_ab, _part, _envelope
    sources = _sources_ab()
    foreign = sources.d2_directions[0].model_copy(update={"source_client_id": "nikadent"})
    sources = sources.model_copy(update={"d2_directions": (foreign,)})
    operation = _part("r1", "content", service_id=None, topic_id=foreign.topic_id, content_ref=None)
    with pytest.raises(MaterializationOwnershipError, match="materialization_foreign_material"):
        resolve_d2_operations(_envelope([operation]).blocks, sources, as_of=date(2026, 9, 18))
