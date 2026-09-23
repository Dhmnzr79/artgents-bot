"""C08: fail on replaceable legacy semantics reached from real POST /ask."""

from __future__ import annotations

import ast
import inspect
import sys
from contextlib import contextmanager

from tests.d1r_envelope_fixtures import envelope_clinic_policy_only
from tests.test_d2_http_contract import FakeProvider, http_env, post, post_sse, sse_events


FORBIDDEN_MODULES = (
    "orchestration.sales_one_plus_ask_turn",
    "orchestration.finalize_turn",
    "core.sales_fast_widget_runtime",
    "core.sales_one_plus_turn",
    "core.target_composer",
    "core.target_marketing_selector",
    "core.one_call_runtime",
)
FORBIDDEN_SESSION_CALLS = {"mem_add_bot", "mem_add_user", "record_last_bot_payload"}


@contextmanager
def no_legacy_calls(*, ordinary: bool):
    previous = sys.getprofile()
    calls = []

    def observe(frame, event, _arg):
        if event != "call":
            return
        module = frame.f_globals.get("__name__", "")
        name = frame.f_code.co_name
        calls.append((module, name))
        assert not any(module == forbidden or module.startswith(forbidden + ".")
                       for forbidden in FORBIDDEN_MODULES), (module, name)
        if module == "session":
            assert name not in FORBIDDEN_SESSION_CALLS
            if ordinary:
                assert name != "mem_get", "ordinary D2 answer read legacy memory"

    sys.setprofile(observe)
    try:
        yield calls
    finally:
        sys.setprofile(previous)


def test_success_error_and_typed_lead_action_never_call_legacy(http_env):
    client, _, use_provider, _ = http_env
    fake = use_provider(FakeProvider(envelope_clinic_policy_only("no_pediatric_dentistry")))
    with no_legacy_calls(ordinary=True) as calls:
        assert post(client, sid="ordinary").status_code == 200
    assert ("core.d2_dialogue", "run_d2_dialogue_turn") in calls
    assert len(fake.inputs) == 1

    fake.raw = "{invalid"
    with no_legacy_calls(ordinary=True):
        assert post(client, sid="error", request_id="error").status_code != 200

    with no_legacy_calls(ordinary=False) as calls:
        response = post(client, sid="action", request_id="action", q="",
                        situation_action="start")
    assert response.status_code == 200
    assert ("core.d2_dialogue", "run_d2_dialogue_turn") in calls
    assert len(fake.inputs) == 2


def test_json_route_dependency_is_direct_d2_adapter():
    import app
    source = inspect.getsource(app.ask)
    assert "run_d2_ask_json(data, client_id=client_id)" in source
    for old in ("_orchestrate_ask_turn", "_dispatch_orchestration_json",
                "_service_reply", "finalize_ask", "mem_get"):
        assert old not in source


def test_sse_success_error_and_lead_action_never_call_legacy(http_env):
    client, _, use_provider, _ = http_env
    fake = use_provider(FakeProvider(envelope_clinic_policy_only("no_pediatric_dentistry")))
    with no_legacy_calls(ordinary=True) as calls:
        assert sse_events(post_sse(client, sid="sse-ordinary"))[-1][0] == "done"
    assert ("core.d2_dialogue", "run_d2_dialogue_turn") in calls
    fake.raw = "{invalid"
    with no_legacy_calls(ordinary=True):
        assert sse_events(post_sse(client, sid="sse-error", request_id="error"))[-1][0] == "error"
    with no_legacy_calls(ordinary=False) as calls:
        assert sse_events(post_sse(client, sid="sse-action", request_id="action",
                                   q="", situation_action="start"))[-1][0] == "done"
    assert ("core.d2_dialogue", "run_d2_dialogue_turn") in calls


def test_sse_route_dependency_is_direct_d2_adapter():
    import app
    source = inspect.getsource(app.ask_stream)
    assert "run_d2_ask_json(data, client_id=client_id)" in source
    for old in ("_orchestrate_ask_turn", "_stream_ask_turn_response",
                "_dispatch_orchestration_sse", "finalize_ask", "mem_get"):
        assert old not in source


def test_app_has_no_legacy_semantic_wiring():
    import app

    tree = ast.parse(inspect.getsource(app))
    imports = {
        alias.name for node in tree.body if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module for node in tree.body if isinstance(node, ast.ImportFrom)
    }
    assert not imports.intersection({
        "contracts.ask_orchestration",
        "orchestration.sales_one_plus_ask_turn",
        "orchestration.finalize_turn",
        "orchestration.helpers",
        "core.sales_fast_widget_runtime",
        "core.target_composer_executor",
        "core.target_sse_worker_context",
    })
    functions = {
        node.name for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    assert not functions.intersection({
        "_orchestrate_ask_turn", "_orchestrate_ask_turn_inner",
        "_dispatch_orchestration_json", "_dispatch_orchestration_sse",
        "_service_reply", "_build_sse_payload", "_run_sse_worker_turn",
        "_stream_ask_turn_response", "_sse_service_reply",
    })
    assert {"ask", "ask_stream", "create_lead"} <= functions
