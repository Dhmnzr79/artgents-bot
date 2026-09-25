"""D2-S4: one frozen response plan combines prose and exact tenant facts."""

from __future__ import annotations

import json
import shutil
import socket
from datetime import datetime, timezone
from pathlib import Path

from contracts.response_plan import SessionKey
from core.d2_dialogue import run_d2_dialogue_turn
from core.d2_dialogue_store import D2DialogueStore
from core.one_call_envelope_protocol import production_envelope_template


NOW = datetime(2026, 9, 25, 12, tzinfo=timezone.utc)


class RawFakeProvider:
    def __init__(self, raw: str) -> None:
        self.raw = raw
        self.inputs = []

    def generate(self, request):
        self.inputs.append(request)
        return self.raw


def _clients(tmp_path: Path) -> Path:
    clients = tmp_path / "clients"
    shutil.copytree(Path("clients") / "demo", clients / "demo")
    return clients


def _raw(
    *,
    policy: bool = False,
    contact: bool = False,
    price_service_id: str = "all_on_4",
) -> str:
    price_topic_id = "prosthetics" if price_service_id == "veneers" else "implantation"
    price_situation = None if price_service_id == "veneers" else {
        "scope_commitment": "reported",
        "extent": "full_arch",
        "tooth_count": None,
        "jaw": "unknown",
        "continuity": "new",
    }
    requests: list[dict[str, object]] = [
        {
            "request_id": "r1",
            "kind": "price",
            "subject_id": None,
            "context": "general_information",
            "topic_id": price_topic_id,
            "service_id": price_service_id,
            "statement_mode": "question",
            "situation": price_situation,
        },
        {
            "request_id": "r2",
            "kind": "content",
            "subject_id": None,
            "context": "general_information",
            "topic_id": "implantation",
            "service_id": "all_on_4",
            "content_text": "Живой ответ модели о восстановлении всей челюсти.",
        },
    ]
    if policy:
        requests.append({
            "request_id": "r3",
            "kind": "clinic_policy",
            "subject_id": None,
            "context": "general_information",
            "policy_ids": ["no_pediatric_dentistry"],
            "payment_scheme": "unspecified",
            "payment_scheme_intent": "not_requested",
            "contact_fields": [],
            "content_text": None,
        })
    if contact:
        requests.append({
            "request_id": "r3",
            "kind": "contact",
            "subject_id": None,
            "context": "general_information",
            "policy_ids": [],
            "payment_scheme": "unspecified",
            "payment_scheme_intent": "not_requested",
            "contact_fields": ["contact_address"],
            "content_text": None,
        })
    return json.dumps(production_envelope_template(
        commercial_intent="price",
        primary_price_request_id="r1",
        request_understanding={"subjects": [], "requests": requests},
    ), ensure_ascii=False)


def _run(tmp_path: Path, raw: str, monkeypatch, *, no_price: bool = False):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("network forbidden in D2 stage 4")

    for name in ("connect", "connect_ex", "sendto"):
        monkeypatch.setattr(socket.socket, name, forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    provider = RawFakeProvider(raw)
    key = SessionKey(client_id="demo", sid="stage4")
    clients = _clients(tmp_path)
    if no_price:
        offer_file = clients / "demo" / "target_response" / "pricebook" / "services" / "veneers.default.json"
        offer_data = json.loads(offer_file.read_text(encoding="utf-8"))
        offer_data["active"] = False
        offer_file.write_text(json.dumps(offer_data), encoding="utf-8")
    with D2DialogueStore(tmp_path / "dialogue.sqlite") as store:
        turn = run_d2_dialogue_turn(
            session_key=key,
            user_message="Тестовый составной вопрос",
            provider=provider,
            clients_root=clients,
            store=store,
            now=NOW,
            request_id="mixed",
        )
        saved = store.read_latest_completion(key)
    assert len(provider.inputs) == 1
    assert saved is not None
    return turn, saved, provider


def test_content_price_and_policy_are_one_frozen_ordered_plan(tmp_path, monkeypatch) -> None:
    import core.response_plan_materialization as materialization

    render_calls = 0
    project_calls = 0
    original_render = materialization.render_response_text
    original_project = materialization.project_response_ui

    def render_once(plan):
        nonlocal render_calls
        render_calls += 1
        return original_render(plan)

    def project_once(plan):
        nonlocal project_calls
        project_calls += 1
        return original_project(plan)

    monkeypatch.setattr(materialization, "render_response_text", render_once)
    monkeypatch.setattr(materialization, "project_response_ui", project_once)
    turn, saved, _ = _run(tmp_path, _raw(policy=True), monkeypatch)

    assert [(part.request_id, part.kind, part.status) for part in turn.response.resolved.d2_request_parts] == [
        ("r1", "price", "answered"),
        ("r2", "content", "answered"),
        ("r3", "clinic_policy", "answered"),
    ]
    assert [row.offer_id for row in turn.response.resolved.d2_price_block.rows] == [
        "all_on_4.jaw.impro", "all_on_4.jaw.implantium", "all_on_4.jaw.nobel",
    ]
    assert len(turn.response.resolved.d2_policy_blocks) == 1
    assert "Живой ответ модели" in turn.response.rendered_text
    assert turn.response.resolved.d2_policy_blocks[0].display_text in turn.response.rendered_text
    assert saved.response.rendered_text == turn.response.rendered_text
    assert saved.response.ui_projection == turn.response.ui_projection
    assert render_calls == 1
    assert project_calls == 1


def test_unavailable_price_keeps_content_and_contact_in_degraded_frozen_plan(tmp_path, monkeypatch) -> None:
    turn, saved, _ = _run(
        tmp_path,
        _raw(contact=True, price_service_id="veneers"),
        monkeypatch,
        no_price=True,
    )

    assert [(part.request_id, part.status) for part in turn.response.resolved.d2_request_parts] == [
        ("r1", "unavailable"), ("r2", "answered"), ("r3", "answered"),
    ]
    assert turn.response.resolved.d2_result_status == "degraded"
    assert turn.response.resolved.d2_price_block is None
    assert "Живой ответ модели" in turn.response.rendered_text
    assert turn.response.resolved.d2_part_failure_blocks[0].display_text in turn.response.rendered_text
    assert turn.response.resolved.d2_contact_blocks[0].display_text in turn.response.rendered_text
    assert turn.response.resolved.d2_canonical_contact is not None
    assert turn.response.resolved.d2_canonical_contact == turn.response.resolved.ui_plan.contact
    assert turn.response.resolved.ui_plan.contact is not None
    assert [button.action_kind for button in turn.response.resolved.ui_plan.buttons].count("contact") == 1
    assert saved.response.rendered_text == turn.response.rendered_text
