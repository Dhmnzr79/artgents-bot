from __future__ import annotations

import json
import shutil
import socket
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from contracts.response_plan import SessionKey
from contracts.response_plan_materialization import D2DirectionAuthority, D2PartFailureAuthority
from core.d2_dialogue import run_d2_dialogue_turn
from core.d2_dialogue_store import D2DialogueStore
from core.one_call_envelope_protocol import production_envelope_template
from core.response_plan_materialization import resolve_d2_envelope_response
from tests.test_d2_multi_request import _envelope as materialization_envelope
from tests.test_d2_multi_request import _sources as materialization_sources
from tests.test_target_offer_projection import _bundle


NOW = datetime(2026, 9, 25, 12, tzinfo=timezone.utc)


class RawFakeProvider:
    def __init__(self, raw: str) -> None:
        self.raw = raw
        self.inputs = []

    def generate(self, request):
        self.inputs.append(request)
        return self.raw


def _exact_price(
    service_id: str,
    *,
    extent: str,
    commitment: str = "reported",
    continuity: str = "new",
    deferred_service_id: str | None = None,
) -> str:
    requests: list[dict[str, object]] = [{
        "request_id": "r1",
        "kind": "price",
        "subject_id": None,
        "context": "general_information",
        "topic_id": "implantation",
        "service_id": service_id,
        "statement_mode": "question",
        "situation": {
            "scope_commitment": commitment,
            "extent": extent,
            "tooth_count": None,
            "jaw": "unknown",
            "continuity": continuity,
        },
    }]
    if deferred_service_id is not None:
        requests.append({
            "request_id": "r2",
            "kind": "price",
            "subject_id": None,
            "context": "general_information",
            "topic_id": "implantation",
            "service_id": deferred_service_id,
            "statement_mode": "question",
            "situation": None,
        })
    return json.dumps(
        production_envelope_template(
            commercial_intent="price",
            primary_price_request_id="r1",
            request_understanding={
                "subjects": [],
                "requests": requests,
            },
        ),
        ensure_ascii=False,
    )


def _run(
    *,
    raw: str,
    clients: Path,
    database: Path,
    key: SessionKey,
    now: datetime = NOW,
):
    provider = RawFakeProvider(raw)
    with D2DialogueStore(database) as store:
        turn = run_d2_dialogue_turn(
            session_key=key,
            user_message="Тестовый вопрос о цене",
            provider=provider,
            clients_root=clients,
            store=store,
            now=now,
        )
        saved = store.read(key)
    assert len(provider.inputs) == 1
    return turn, saved, provider


def _demo_clients(tmp_path: Path) -> Path:
    clients = tmp_path / "clients"
    shutil.copytree(Path("clients") / "demo", clients / "demo")
    return clients


def test_exact_all_on_4_uses_ascending_published_prices_and_keeps_typed_state(
    tmp_path, monkeypatch
) -> None:
    def forbidden_network(*_args, **_kwargs):
        raise AssertionError("network forbidden in D2 stage 3")

    monkeypatch.setattr(socket.socket, "connect", forbidden_network)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden_network)
    monkeypatch.setattr(socket, "create_connection", forbidden_network)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden_network)
    clients = _demo_clients(tmp_path)
    key = SessionKey(client_id="demo", sid="stage3-all-on-4")

    turn, saved, _ = _run(
        raw=_exact_price("all_on_4", extent="full_arch"),
        clients=clients,
        database=tmp_path / "dialogue.sqlite",
        key=key,
    )

    rows = turn.response.resolved.d2_price_block.rows
    assert tuple(row.offer_id for row in rows) == (
        "all_on_4.jaw.implantium",
        "all_on_4.jaw.impro",
        "all_on_4.jaw.nobel",
    )
    assert turn.response.resolved.session_delta.shown_price_offer_ids == (
        "all_on_4.jaw.implantium",
        "all_on_4.jaw.impro",
        "all_on_4.jaw.nobel",
    )
    assert tuple(item.offer_id for item in saved.state.d2_shown_price_offer_refs) == (
        "all_on_4.jaw.implantium",
        "all_on_4.jaw.impro",
        "all_on_4.jaw.nobel",
    )
    assert saved.state.situation_state is not None
    assert saved.state.situation_state.extent == "full_arch"
    assert [(row.mode, row.amount, row.currency, row.billing_unit) for row in rows] == [
        ("fixed", 318_000, "RUB", "jaw"),
        ("fixed", 368_000, "RUB", "jaw"),
        ("fixed", 428_000, "RUB", "jaw"),
    ]
    assert all(row.condition_texts == ("КТ и костная пластика по показаниям — отдельно",) for row in rows)
    assert "КТ и костная пластика по показаниям — отдельно" in turn.response.rendered_text


def test_exact_classic_is_another_ascending_multi_offer_service(tmp_path) -> None:
    turn, _, _ = _run(
        raw=_exact_price("classic", extent="one_tooth"),
        clients=_demo_clients(tmp_path),
        database=tmp_path / "classic.sqlite",
        key=SessionKey(client_id="demo", sid="stage3-classic"),
    )

    assert tuple(row.offer_id for row in turn.response.resolved.d2_price_block.rows) == (
        "classic.one_tooth.implantium",
        "classic.one_tooth.impro",
        "classic.one_tooth.nobel",
    )


def test_exact_service_unknown_and_correction_never_multiply_or_repeat_scope_menu(tmp_path) -> None:
    clients = _demo_clients(tmp_path)
    unknown, _, _ = _run(
        raw=_exact_price("all_on_4", extent="unknown", commitment="reported"),
        clients=clients,
        database=tmp_path / "unknown.sqlite",
        key=SessionKey(client_id="demo", sid="stage3-unknown"),
    )
    correction, _, _ = _run(
        raw=_exact_price("all_on_4", extent="full_arch", commitment="correction"),
        clients=clients,
        database=tmp_path / "correction.sqlite",
        key=SessionKey(client_id="demo", sid="stage3-correction"),
    )

    assert unknown.response.resolved.d2_price_scope_decision is None
    assert unknown.response.ui_projection.quick_replies == ()
    assert [row.amount for row in unknown.response.resolved.d2_price_block.rows] == [318_000, 368_000, 428_000]
    assert [row.amount for row in correction.response.resolved.d2_price_block.rows] == [318_000, 368_000, 428_000]


def _direct_service_multi_extent_sources():
    bundle_payload = _bundle().model_dump()
    extents = {
        "generic_fixed": "one_tooth",
        "option_a_from": "few_teeth",
        "option_c_range": "full_arch",
    }
    for offer in bundle_payload["offers"]:
        if offer["offer_id"] in extents:
            offer["applies_to_extents"] = [extents[offer["offer_id"]]]
    bundle = _bundle().__class__.model_validate(bundle_payload)
    base = materialization_sources(bundle)
    payload = base.model_dump()
    payload["d2_directions"][0]["ordered_offer_ids"] = list(extents)
    return type(base).model_validate(payload)


def _direct_service_envelope(*, extent: str, commitment: str):
    envelope = materialization_envelope()
    understanding = envelope.request_understanding
    assert understanding is not None
    first_payload = understanding.requests[0].model_dump()
    first_payload["situation"] = {
        "scope_commitment": commitment,
        "extent": extent,
        "tooth_count": None,
        "jaw": "unknown",
        "continuity": "new",
    }
    first = understanding.requests[0].__class__.model_validate(first_payload)
    return envelope.model_copy(update={"request_understanding": understanding.model_copy(
        update={"requests": (first, *understanding.requests[1:])}
    )})


def test_exact_service_filters_by_its_own_typed_extent_before_price_sort() -> None:
    sources = _direct_service_multi_extent_sources()
    known = resolve_d2_envelope_response(
        _direct_service_envelope(extent="few_teeth", commitment="correction"),
        sources,
        as_of=date(2026, 9, 25),
        common_route_direct_service_only=True,
    )
    unknown = resolve_d2_envelope_response(
        _direct_service_envelope(extent="unknown", commitment="reported"),
        sources,
        as_of=date(2026, 9, 25),
        common_route_direct_service_only=True,
    )

    assert [row.offer_id for row in known.resolved.d2_price_block.rows] == ["option_a_from"]
    assert known.resolved.d2_price_scope_decision is None
    assert known.ui_projection.quick_replies == ()
    assert [row.offer_id for row in unknown.resolved.d2_price_block.rows] == [
        "option_a_from", "option_c_range", "generic_fixed",
    ]
    assert unknown.ui_projection.quick_replies == ()


def test_first_price_is_frozen_second_is_deferred_and_followup_keeps_ordered_refs(tmp_path) -> None:
    clients = _demo_clients(tmp_path)
    database = tmp_path / "continuation.sqlite"
    key = SessionKey(client_id="demo", sid="stage3-continuation")
    first, saved_first, _ = _run(
        raw=_exact_price("all_on_4", extent="full_arch", deferred_service_id="classic"),
        clients=clients,
        database=database,
        key=key,
    )
    followup, saved_followup, provider = _run(
        raw=_exact_price("all_on_4", extent="full_arch", continuity="same"),
        clients=clients,
        database=database,
        key=key,
        now=NOW + timedelta(minutes=1),
    )

    assert [(item.request_id, item.status) for item in first.response.resolved.d2_request_parts] == [
        ("r1", "answered"), ("r2", "deferred"),
    ]
    assert [item.offer_id for item in saved_first.state.d2_shown_price_offer_refs] == [
        "all_on_4.jaw.impro", "all_on_4.jaw.implantium", "all_on_4.jaw.nobel",
    ]
    carried = provider.inputs[0].context.ordinary.d2_shown_price_offer_refs
    assert [item.offer_id for item in carried] == [
        "all_on_4.jaw.impro", "all_on_4.jaw.implantium", "all_on_4.jaw.nobel",
    ]
    assert all(not hasattr(item, "display_text") for item in carried)
    assert tuple(row.offer_id for row in followup.response.resolved.d2_price_block.rows) == tuple(
        item.offer_id for item in saved_followup.state.d2_shown_price_offer_refs
    )


def _sources_with_no_price_failure(*, ambiguous: bool):
    base = materialization_sources(_bundle())
    payload = base.model_dump()
    payload["d2_part_failures"] = [D2PartFailureAuthority(
        source_client_id="demo",
        message_id="no-price",
        reason="d2_no_price_candidates",
        display_text="Нет опубликованной цены.",
    ).model_dump()]
    if ambiguous:
        payload["d2_directions"] = list(payload["d2_directions"])
        payload["d2_directions"].append(D2DirectionAuthority(
            source_client_id="demo",
            topic_id="other_direction",
            service_ids=("service_one",),
            ordered_offer_ids=("generic_fixed",),
        ).model_dump())
    return type(base).model_validate(payload)


def test_exact_service_ignores_absent_order_and_multiple_content_directions() -> None:
    for ambiguous in (False, True):
        with patch(
            "core.response_plan_materialization.project_target_service_offers",
            side_effect=AssertionError("legacy catalog selector must not run"),
        ):
            outcome = resolve_d2_envelope_response(
                materialization_envelope(),
                _sources_with_no_price_failure(ambiguous=ambiguous),
                as_of=date(2026, 9, 25),
                common_route_direct_service_only=True,
            )
        assert [row.offer_id for row in outcome.resolved.d2_price_block.rows] == [
            "option_a_from", "option_c_range", "generic_fixed",
        ]
        assert outcome.resolved.d2_request_parts[0].status == "answered"


def test_exact_service_no_public_price_remains_a_frozen_no_public_row() -> None:
    payload = _bundle(no_public_active=True).model_dump()
    for offer in payload["offers"]:
        offer["active"] = offer["offer_id"] == "generic_no_public"
    bundle = _bundle().__class__.model_validate(payload)
    base = materialization_sources(bundle)
    sources_payload = base.model_dump()
    sources_payload["d2_directions"][0]["ordered_offer_ids"] = ["generic_no_public"]
    sources = type(base).model_validate(sources_payload)

    outcome = resolve_d2_envelope_response(
        materialization_envelope(),
        sources,
        as_of=date(2026, 9, 25),
        common_route_direct_service_only=True,
    )

    row = outcome.resolved.d2_price_block.rows[0]
    assert row.offer_id == "generic_no_public"
    assert row.mode == "no_public_price"
    assert row.amount is None and row.billing_unit is None
