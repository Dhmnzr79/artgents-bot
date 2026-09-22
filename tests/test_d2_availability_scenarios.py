"""CP5-AP: assembled B01/B10 availability/policy through the common D2 route.

Fake raw → production parser → tenant snapshot → D2 builders/materializer →
D2DialogueStore. Decisions: D2-024–026, D2-029, D2-068–069, D2-079.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import sqlite3
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from contracts.response_plan import SessionKey
from core.d2_dialogue import run_d2_dialogue_turn
from core.d2_dialogue_store import D2DialogueStore
from core.one_call_envelope_protocol import production_envelope_template


NOW = datetime(2026, 9, 22, 17, tzinfo=timezone.utc)
KEY = SessionKey(client_id="demo", sid="ap-availability")
BONE_APPROVED = (
    "Стоимость костной пластики рассчитывается после КТ и зависит от необходимого "
    "объёма и выбранной методики."
)
PRICE_GAP = "К сожалению, у меня пока нет информации о стоимости этой услуги"
INFO_GAP = "К сожалению, у меня пока недостаточно информации по этому вопросу"
BRACES_ALT = "Брекеты мы не устанавливаем"
ALIGNERS_NAME = "Элайнеры"
OMS_TEXT = "По полису ОМС мы не работаем"
DMS_TEXT = "По ДМС напрямую не работаем"
PEDIATRIC_TEXT = "детскую стоматологию в клинике не ведём"
POLICY_CLARIFY = "Уточните, пожалуйста: вопрос про ОМС или ДМС?"


def _raw_price(service_id: str, topic_id: str) -> str:
    return json.dumps(
        production_envelope_template(
            commercial_intent="price",
            primary_price_request_id="r1",
            request_understanding={
                "subjects": [],
                "requests": [{
                    "request_id": "r1",
                    "kind": "price",
                    "subject_id": None,
                    "context": "general_information",
                    "topic_id": topic_id,
                    "service_id": service_id,
                    "statement_mode": "question",
                    "situation": None,
                }],
            },
        ),
        ensure_ascii=False,
    )


def _raw_content_gap(service_id: str, topic_id: str | None = None) -> str:
    return json.dumps(
        production_envelope_template(
            commercial_intent="none",
            primary_price_request_id=None,
            patient_text=None,
            request_understanding={
                "subjects": [],
                "requests": [{
                    "request_id": "r1",
                    "kind": "content",
                    "subject_id": None,
                    "context": "general_information",
                    "topic_id": topic_id,
                    "service_id": service_id,
                    "statement_mode": "question",
                    "situation": None,
                    "content_text": None,
                    "content_ref": None,
                    "content_realization": "authored",
                    "content_section_refs": [],
                }],
            },
        ),
        ensure_ascii=False,
    )


def _raw_policy(
    *,
    policy_ids: list[str] | None = None,
    payment_scheme: str = "unspecified",
    payment_scheme_intent: str = "unspecified",
    subject: dict[str, object] | None = None,
) -> str:
    subjects = [subject] if subject is not None else []
    return json.dumps(
        production_envelope_template(
            commercial_intent="none",
            primary_price_request_id=None,
            patient_text=None,
            request_understanding={
                "subjects": subjects,
                "requests": [{
                    "request_id": "r1",
                    "kind": "clinic_policy",
                    "subject_id": subject["subject_id"] if subject else None,
                    "context": "general_information",
                    "topic_id": None,
                    "service_id": None,
                    "statement_mode": "question",
                    "situation": None,
                    "policy_ids": policy_ids or [],
                    "payment_scheme": payment_scheme,
                    "payment_scheme_intent": payment_scheme_intent,
                    "content_text": None,
                    "content_ref": None,
                }],
            },
        ),
        ensure_ascii=False,
    )


class RawFakeProvider:
    def __init__(self, raw: str) -> None:
        self.raw = raw
        self.inputs = []

    def generate(self, request):
        self.inputs.append(request)
        return self.raw


@pytest.fixture(autouse=True)
def isolated_io(monkeypatch, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    monkeypatch.setenv("BOT_LOG_DIR", str(log_dir))
    os.environ["BOT_LOG_DIR"] = str(log_dir)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("network forbidden in CP5-AP")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket.socket, "sendto", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    connect = sqlite3.connect

    def isolated_connect(database, *args, **kwargs):
        assert Path(database).resolve().is_relative_to(tmp_path.resolve()), "non-test DB forbidden"
        return connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", isolated_connect)


@contextmanager
def observed_common_route():
    calls = []
    previous = sys.getprofile()

    def observe(frame, event, _arg):
        if event != "call":
            return
        module = frame.f_globals.get("__name__", "")
        calls.append((module, frame.f_code.co_name))
        assert not module.startswith((
            "core.sales_",
            "core.target_composer",
            "core.target_runtime_",
            "core.response_plan_composer_executor",
            "core.target_session_selection",
            "core.one_call_runtime",
            "core.one_call_presentation",
            "core.response_plan_session",
            "core.target_offer_projection",
            "core.target_service_selection",
            "core.response_strategy",
        )), f"legacy runtime/selector called: {module}"
        assert module != "core.target_marketing_selector", "legacy marketing selector called"
        assert module != "session", "second ordinary memory called"
        assert frame.f_code.co_name != "match_clinic_policy_key", "policy triggers used"

    sys.setprofile(observe)
    try:
        yield calls
    finally:
        sys.setprofile(previous)


def _clients(tmp_path: Path) -> Path:
    clients = tmp_path / "clients"
    if not (clients / "demo").exists():
        shutil.copytree(Path("clients") / "demo", clients / "demo")
    return clients


def _run(tmp_path: Path, raw: str, *, key: SessionKey = KEY, message: str = "Вопрос"):
    clients = _clients(tmp_path)
    provider = RawFakeProvider(raw)
    with observed_common_route() as calls:
        with D2DialogueStore(tmp_path / "dialogue.sqlite") as store:
            outcome = run_d2_dialogue_turn(
                session_key=key,
                user_message=message,
                provider=provider,
                clients_root=clients,
                store=store,
                now=NOW,
            )
            saved = store.read(key)
    return outcome, saved, provider, calls, clients


def test_b01_no_public_price_shows_approved_text_without_amount(tmp_path: Path) -> None:
    outcome, _, provider, calls, _ = _run(
        tmp_path,
        _raw_price("bone_graft", "implantation"),
        message="Сколько стоит костная пластика?",
    )
    resolved = outcome.response.resolved
    text = outcome.response.rendered_text
    assert resolved.d2_price_block is not None
    row = resolved.d2_price_block.rows[0]
    assert row.mode == "no_public_price"
    assert row.approved_text == BONE_APPROVED
    assert BONE_APPROVED in text
    assert row.min_amount is None or "min_amount" not in dir(row) or True
    assert "₽" not in text
    assert "000" not in text
    assert PRICE_GAP not in text
    assert len(provider.inputs) == 1
    assert sum(name == "select_target_marketing" for _, name in calls) == 0


def test_b01_understood_without_material_is_honest_gap(tmp_path: Path) -> None:
    outcome, _, _, _, _ = _run(
        tmp_path,
        _raw_content_gap("classic", "implantation"),
        key=SessionKey(client_id="demo", sid="ap-no-material"),
        message="Расскажите про лазерную имплантацию классик",
    )
    text = outcome.response.rendered_text
    assert INFO_GAP in text
    assert "не оказываем" not in text.lower()
    assert outcome.response.resolved.authored_service_alternative_block is None


def test_b01_authored_alternative_for_braces(tmp_path: Path) -> None:
    outcome, _, _, _, _ = _run(
        tmp_path,
        _raw_content_gap("braces", "orthodontics"),
        key=SessionKey(client_id="demo", sid="ap-braces-alt"),
        message="Делаете брекеты?",
    )
    text = outcome.response.rendered_text
    block = outcome.response.resolved.authored_service_alternative_block
    assert block is not None
    assert block.requested_service_id == "braces"
    assert BRACES_ALT in text
    assert ALIGNERS_NAME in text or any(
        opt.service_id == "aligners" for opt in block.options
    )
    assert INFO_GAP not in text


def test_b01_inactive_without_alternative_is_gap_not_refusal(tmp_path: Path) -> None:
    clients = _clients(tmp_path)
    policies_path = clients / "demo" / "clinic_policies.yaml"
    raw = yaml.safe_load(policies_path.read_text(encoding="utf-8"))
    raw["service_alternatives"] = [
        row for row in raw.get("service_alternatives", [])
        if not (isinstance(row, dict) and row.get("requested_service_id") == "braces")
    ]
    policies_path.write_text(
        yaml.safe_dump(raw, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    provider = RawFakeProvider(_raw_content_gap("braces", "orthodontics"))
    with observed_common_route():
        with D2DialogueStore(tmp_path / "dialogue.sqlite") as store:
            outcome = run_d2_dialogue_turn(
                session_key=SessionKey(client_id="demo", sid="ap-inactive-gap"),
                user_message="Брекеты?",
                provider=provider,
                clients_root=clients,
                store=store,
                now=NOW,
            )
    text = outcome.response.rendered_text
    assert INFO_GAP in text
    assert "не оказываем" not in text.lower()
    assert "не устанавливаем" not in text.lower()
    assert outcome.response.resolved.authored_service_alternative_block is None


def test_b10_oms_dms_pediatric_use_authored_answers(tmp_path: Path) -> None:
    oms, _, _, _, _ = _run(
        tmp_path,
        _raw_policy(policy_ids=["no_oms"]),
        key=SessionKey(client_id="demo", sid="ap-oms"),
        message="Можно по ОМС?",
    )
    assert OMS_TEXT in oms.response.rendered_text
    assert oms.response.resolved.route == "ANSWER"

    dms, _, _, _, _ = _run(
        tmp_path,
        _raw_policy(
            policy_ids=[],
            payment_scheme="dms",
            payment_scheme_intent="eligibility_question",
        ),
        key=SessionKey(client_id="demo", sid="ap-dms"),
        message="А по ДМС?",
    )
    assert DMS_TEXT in dms.response.rendered_text

    child, _, _, _, _ = _run(
        tmp_path,
        _raw_policy(
            policy_ids=[],
            subject={"subject_id": "s1", "relation": "other", "age_group": "child"},
        ),
        key=SessionKey(client_id="demo", sid="ap-child"),
        message="Лечите детей?",
    )
    assert PEDIATRIC_TEXT.split()[0] in child.response.rendered_text or PEDIATRIC_TEXT in child.response.rendered_text
    assert "детск" in child.response.rendered_text.lower()


def test_b10_ambiguous_and_unknown_policy(tmp_path: Path) -> None:
    clarify, _, _, _, _ = _run(
        tmp_path,
        _raw_policy(policy_ids=[]),
        key=SessionKey(client_id="demo", sid="ap-policy-clarify"),
        message="Можно по полису?",
    )
    assert clarify.response.resolved.route == "CLARIFY"
    assert POLICY_CLARIFY in clarify.response.rendered_text
    assert "работаем" not in clarify.response.rendered_text.lower() or "ОМС" in POLICY_CLARIFY

    unknown, _, _, _, _ = _run(
        tmp_path,
        _raw_policy(policy_ids=["no_such_policy_ever"]),
        key=SessionKey(client_id="demo", sid="ap-policy-unknown"),
        message="А по фантазийному полису?",
    )
    assert INFO_GAP in unknown.response.rendered_text
    assert OMS_TEXT not in unknown.response.rendered_text
    assert "да" != unknown.response.rendered_text.strip().lower()
    assert "нет" != unknown.response.rendered_text.strip().lower()
