from __future__ import annotations

import json

import pytest

from contracts.service_selection import ServiceSelection
from core.service_selector_llm import (
    _validate_selection,
    build_compact_service_catalog,
    classify_service,
)


def _mock_llm(monkeypatch: pytest.MonkeyPatch, payload: dict):
    def _fake_create(**kwargs):
        captured = kwargs

        class _Msg:
            content = json.dumps(payload)

        class _Choice:
            message = _Msg()

        class _Resp:
            choices = [_Choice()]

        monkeypatch.setattr("core.service_selector_llm.chat_completions_create", _fake_create)
        return captured

    return _fake_create


def test_build_compact_service_catalog_demo_has_extraction_and_pulpitis():
    rows = build_compact_service_catalog("demo")
    ids = {r["service_id"] for r in rows}
    assert "tooth_extraction" in ids
    assert "pulpitis" in ids
    extraction = next(r for r in rows if r["service_id"] == "tooth_extraction")
    assert "удаление" in extraction["title"].lower()


def test_classify_extraction_not_pulpitis(monkeypatch):
    monkeypatch.setattr("core.service_selector_llm.SERVICE_SELECT_LLM_ON", True)
    captured: dict = {}

    def _fake(**kwargs):
        captured.update(kwargs)
        payload = {"service_id": "tooth_extraction", "confidence": 0.92}

        class _Msg:
            content = json.dumps(payload)

        class _Choice:
            message = _Msg()

        class _Resp:
            choices = [_Choice()]

        return _Resp()

    monkeypatch.setattr("core.service_selector_llm.chat_completions_create", _fake)
    sel = classify_service("сколько стоит удаление зуба", client_id="demo", sid="sel-1")
    assert isinstance(sel, ServiceSelection)
    assert sel.service_id == "tooth_extraction"
    assert sel.service_id != "pulpitis"
    user = captured["messages"][1]["content"]
    assert "tooth_extraction" in user
    assert "pulpitis" in user


def test_classify_generic_implantation_returns_null(monkeypatch):
    monkeypatch.setattr("core.service_selector_llm.SERVICE_SELECT_LLM_ON", True)
    _mock_llm(monkeypatch, {"service_id": None, "confidence": 0.8})
    sel = classify_service("сколько стоит имплантация", client_id="demo", sid="sel-2")
    assert sel is not None
    assert sel.service_id is None


def test_classify_classic_implantation(monkeypatch):
    monkeypatch.setattr("core.service_selector_llm.SERVICE_SELECT_LLM_ON", True)
    _mock_llm(monkeypatch, {"service_id": "classic", "confidence": 0.9})
    sel = classify_service("сколько стоит классическая имплантация", client_id="demo", sid="sel-3")
    assert sel is not None
    assert sel.service_id == "classic"


def test_classify_all_on_4(monkeypatch):
    monkeypatch.setattr("core.service_selector_llm.SERVICE_SELECT_LLM_ON", True)
    _mock_llm(monkeypatch, {"service_id": "all_on_4", "confidence": 0.95})
    sel = classify_service("сколько стоит all-on-4", client_id="demo", sid="sel-4")
    assert sel is not None
    assert sel.service_id == "all_on_4"


def test_invalid_llm_output_fail_open(monkeypatch):
    monkeypatch.setattr("core.service_selector_llm.SERVICE_SELECT_LLM_ON", True)

    def _bad(**_kwargs):
        class _Msg:
            content = "not json"

        class _Choice:
            message = _Msg()

        class _Resp:
            choices = [_Choice()]

        return _Resp()

    monkeypatch.setattr("core.service_selector_llm.chat_completions_create", _bad)
    assert classify_service("сколько стоит удаление", client_id="demo", sid="sel-5") is None


def test_unknown_service_id_coerced_to_null():
    allowed = frozenset({"classic", "all_on_4"})
    sel = _validate_selection(
        {"service_id": "not_in_catalog", "confidence": 0.7},
        allowed_ids=allowed,
    )
    assert sel is not None
    assert sel.service_id is None
    assert sel.confidence == 0.7


def test_classify_off_returns_none(monkeypatch):
    monkeypatch.setattr("core.service_selector_llm.SERVICE_SELECT_LLM_ON", False)
    assert classify_service("сколько стоит удаление зуба", client_id="demo", sid="sel-off") is None
