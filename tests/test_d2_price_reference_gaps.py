"""1B: ordinary absent price references preserve real JSON/SSE completions."""
import pytest

from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore
from tests.d2_ci_http import FakeProvider, completed_context, http_env, raw, send
from tests.test_d2_af1b_contacts_http import DEMO_ADDRESS
from tests.test_d2_http_contract import post, post_sse, sse_events


@pytest.fixture(autouse=True)
def audit_off(monkeypatch):
    monkeypatch.setenv("D2_FULL_AUDIT_LOG", "0")


def price(kind="service", identifier="absent_service", request_id="r1"):
    return {"kind": "price", "request_id": request_id,
            "target": {"type": kind, "id": identifier}}


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("target", [("service", "absent_service"),
    ("topic", "absent_topic"), ("topic", "whitening")])
@pytest.mark.parametrize("address_position", [None, "before", "after"])
def test_absent_price_is_a_part_gap_and_keeps_address(http_env, transport, target, address_position):
    client, db, use, _ = http_env
    blocks = [price(*target)]
    address = {"kind": "contact", "request_id": "r2", "contact_fields": ["contact_address"]}
    if address_position:
        blocks.insert(0 if address_position == "before" else 1, address)
    fake = use(FakeProvider(raw(*blocks)))
    args = dict(sid="price-gap", request_id="gap", q="Сколько стоит и где вы находитесь?")
    body = send(client, transport, **args)
    assert "цена не указана" in body["answer"]
    assert "администратора" in body["answer"]
    assert (DEMO_ADDRESS in body["answer"]) is bool(address_position)
    assert "₽" not in body["answer"]
    if address_position:
        assert (body["answer"].index(DEMO_ADDRESS) < body["answer"].index("цена не указана")) is (address_position == "before")
    key = SessionKey(client_id="demo", sid="price-gap")
    with D2DialogueStore(db) as store:
        resolved = store.read_latest_completion(key).response.resolved
        assert resolved.d2_result_status == ("degraded" if address_position else "failed")
        assert resolved.d2_price_block is None
        assert resolved.finalized_commercial_ids.price_offer_ids == ()
        part = next(p for p in resolved.d2_request_parts if p.request_id == "r1")
        assert (part.status, part.failure_reason) == ("unavailable", "d2_no_price_candidates")
        assert len(resolved.d2_part_failure_blocks) == 1
        assert completed_context(store, key).ordinary.d2_shown_price_offer_refs == ()
    assert send(client, transport, **args) == body
    assert len(fake.inputs) == 1


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_unknown_explicit_price_detail_remains_strict(http_env, transport):
    client, db, use, _ = http_env
    operation = price()
    operation.update(kind="price_detail", price_detail_aspect="includes")
    fake = use(FakeProvider(raw(operation)))
    response = (post if transport == "json" else post_sse)(client, sid="detail")
    if transport == "json":
        assert response.status_code == 400
    else:
        events = dict(sse_events(response))
        assert "error" in events and "ui" not in events and "done" not in events
    with D2DialogueStore(db) as store:
        assert store.read_latest_completion(SessionKey(client_id="demo", sid="detail")) is None
    assert len(fake.inputs) == 1


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_price_gap_clears_previous_offers_in_next_real_provider_context(http_env, transport):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(price(identifier="classic"))))
    send(client, transport, sid="continuation", request_id="price", q="Цена имплантации?")
    fake.raw = raw(price())
    send(client, transport, sid="continuation", request_id="gap", q="Цена другой услуги?")
    assert fake.inputs[-1].context.ordinary.d2_shown_price_offer_refs
    fake.raw = raw({"kind": "contact", "request_id": "r1", "contact_fields": ["contact_address"]})
    body = send(client, transport, sid="continuation", request_id="next", q="А адрес?")
    assert DEMO_ADDRESS in body["answer"]
    assert fake.inputs[-1].context.ordinary.d2_shown_price_offer_refs == ()
    assert len(fake.inputs) == 3


@pytest.mark.parametrize("fault", ["session", "view"])
def test_absent_price_does_not_soften_confirmed_snapshot_identity_violation(fault):
    from dataclasses import replace
    from pathlib import Path
    from core.d2_tenant_snapshot import load_d2_tenant_snapshot, build_d2_model_view
    from core.d2_snapshot_sources import build_d2_snapshot_sources, D2SnapshotBindingError
    snapshot = load_d2_tenant_snapshot("demo", clients_root=Path("clients"))
    view = build_d2_model_view(snapshot)
    key = SessionKey(client_id="nikadent" if fault == "session" else "demo", sid="foreign")
    if fault == "view":
        view = replace(view, client_id="nikadent")
    with pytest.raises(D2SnapshotBindingError, match="snapshot_.*mismatch"):
        build_d2_snapshot_sources(snapshot, model_view=view, operations=(), session_key=key)


def test_foreign_direction_authority_remains_fatal():
    from datetime import date
    from contracts.response_plan_materialization import MaterializationOwnershipError
    from core.response_plan_materialization import resolve_d2_operations
    from tests.test_d2_independent_request_parts import _sources_ab, _part, _envelope
    sources = _sources_ab()
    direction = sources.d2_directions[0]
    sources = sources.model_copy(update={"d2_directions": (
        direction.model_copy(update={"source_client_id": "nikadent"}),)})
    operation = _part("r1", "price", service_id=None, topic_id=direction.topic_id)
    with pytest.raises(MaterializationOwnershipError, match="materialization_foreign_material"):
        resolve_d2_operations(_envelope([operation]).blocks, sources, as_of=date(2026, 9, 18))


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("absent_first", [False, True])
def test_no_switch_to_a_later_price_when_first_is_absent(http_env, transport, absent_first):
    client, db, use, _ = http_env
    first, second = (("absent_service", "classic") if absent_first else ("classic", "absent_service"))
    fake = use(FakeProvider(raw(price(identifier=first), price(identifier=second, request_id="r2"))))
    body = send(client, transport, sid="prices", q="Две цены?")
    with D2DialogueStore(db) as store:
        resolved = store.read_latest_completion(SessionKey(client_id="demo", sid="prices")).response.resolved
    assert [p.status for p in resolved.d2_request_parts] == ["unavailable" if absent_first else "answered", "deferred"]
    if absent_first:
        assert resolved.d2_price_block is None and "₽" not in body["answer"]
    else:
        assert {r.service_id for r in resolved.d2_price_block.rows} == {"classic"}
        assert {r.offer_id for r in resolved.d2_price_block.rows} == {
            "classic.one_tooth.implantium", "classic.one_tooth.impro", "classic.one_tooth.nobel"}
        assert "₽" in body["answer"]
    assert len(fake.inputs) == 1
