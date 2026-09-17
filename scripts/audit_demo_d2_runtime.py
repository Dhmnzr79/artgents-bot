"""Read-only offline runtime audit; no provider/network and no checkout changes.

Historical Python sources are loaded from a Git archive in memory. Demo data and
test files remain in the workspace; comparison requires unchanged data/tests.
All runtime logs and session databases go to an OS temporary directory.
"""
from __future__ import annotations

import argparse
import importlib.abc
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


class RevisionSources(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def __init__(self, revision: str):
        archive = subprocess.check_output(["git", "archive", "--format=zip", revision], cwd=ROOT)
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            self.sources = {n: z.read(n) for n in z.namelist() if n.endswith(".py")}

    def find_spec(self, fullname, path=None, target=None):
        if fullname == "tests" or fullname.startswith("tests."):
            return None
        rel = fullname.replace(".", "/")
        for candidate, package in ((rel + "/__init__.py", True), (rel + ".py", False)):
            if candidate in self.sources:
                spec = importlib.util.spec_from_file_location(
                    fullname, ROOT / candidate, loader=self,
                    submodule_search_locations=[str(ROOT / rel)] if package else None,
                )
                spec.loader_state = candidate
                return spec
        return None

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        exec(compile(self.sources[module.__spec__.loader_state], module.__file__, "exec"), module.__dict__)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--revision", default="working")
    parser.add_argument("--mode", choices=("probes", "tests"), default="probes")
    parser.add_argument("tests", nargs="*")
    args = parser.parse_args()
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    sandbox = Path(tempfile.mkdtemp(prefix="artgents-d2-audit-"))
    os.environ.update(BOT_LOG_DIR=str(sandbox / "logs"), BOT_LOG_RETENTION_DAYS="0",
                      BOT_PG_DSN="", BOT_TEST_PG_DSN="", CHAT_API_KEY="offline-audit",
                      DASHSCOPE_API_KEY="offline-audit")
    if args.revision != "working":
        sys.meta_path.insert(0, RevisionSources(args.revision))
    network_attempts = []

    def blocked(*args, **kwargs):
        network_attempts.append("blocked")
        raise RuntimeError("AUDIT_NETWORK_FORBIDDEN")

    socket.socket.connect = blocked
    socket.create_connection = blocked
    import core.client_runtime as client_runtime
    client_runtime.sqlite_path_for_client = lambda client_id=None: str(sandbox / f"{client_id or 'demo'}.db")
    import session
    session.sqlite_path_for_client = client_runtime.sqlite_path_for_client
    import llm
    llm.chat_client.chat.completions.create = blocked
    print(json.dumps({"revision": args.revision, "temporary_artifacts": str(sandbox)}), flush=True)
    if args.mode == "tests":
        import pytest
        result = pytest.main(["-q", "-p", "no:cacheprovider", "--basetemp", str(sandbox / "pytest"),
                              "--tb=line", "--show-capture=no", "--disable-warnings", "-o", "log_cli=false",
                              *args.tests])
        print(json.dumps({"network_attempts": len(network_attempts), "exit_code": result}), flush=True)
        return int(result)

    import app
    import orchestration.sales_fast_widget_turn as widget_turn
    import core.sales_fast_widget_runtime as runtime
    from core.one_call_envelope_protocol import production_envelope_template
    from core.target_runtime_session import read_target_runtime_session
    from dataclasses import asdict
    captured = {}
    rebuild = runtime._rebuild_authoritative_context

    def capture_rebuild(**kwargs):
        result = rebuild(**kwargs)
        frame, bound, scope, commerce, strategy, semantic = result
        captured.update(service=semantic.service_id, topic=frame.topic,
                        extent=scope.extent, extent_source=scope.extent_axis.source,
                        bound_type=type(bound).__name__)
        return result

    runtime._rebuild_authoritative_context = capture_rebuild
    client = app.app.test_client()

    def env(text="Информация клиники.", kind="content", **overrides):
        req = {"request_id": "r1", "kind": kind, "subject_id": None,
               "context": "current_care"}
        if kind == "content":
            req["content_text"] = text
        return production_envelope_template(
            patient_text=None,
            request_understanding={"subjects": [], "requests": [req]},
            primary_price_request_id="r1" if kind == "price" else None,
            **overrides,
        )

    def turn(name, question, payload, sid=None):
        captured.clear()
        calls = []

        class Fake:
            def generate(self, invocation, /):
                calls.append(1)
                return json.dumps(payload, ensure_ascii=False)

        widget_turn._default_sales_fast_backend = Fake
        sid = sid or "audit-" + name
        response = client.post("/ask", json={"q": question, "sid": sid, "client_id": "demo"})
        body = response.get_json()
        with session.session_client_scope("demo"):
            facts = read_target_runtime_session(sid).patient_facts
        result = {"case": name, "http": response.status_code, "fake_calls": len(calls),
                  "route": body.get("meta", {}).get("service_route"), "answer": body.get("answer"),
                  "quick_replies": body.get("quick_replies"), "video": bool(body.get("video")),
                  "facts": asdict(facts) if facts else None, "scope": dict(captured)}
        print("AUDIT_RESULT " + json.dumps(result, ensure_ascii=True), flush=True)

    turn("pain_generic", "А я боюсь боли", env("Сведения об обезболивании.", scenario="pain_fear"))
    turn("pain_named", "Боюсь боли при имплантации", env(
        "Сведения об обезболивании.", scenario="pain_fear", service_id="classic",
        service_reference_status="resolved", requested_service_id="classic"))
    turn("warranty_valid", "А гарантия у вас есть?", env("Условия гарантии фиксируются в договоре."))
    for value in (None, "r1"):
        malformed = env()
        malformed["request_understanding"]["primary_price_request_id"] = value
        turn("nested_price_id_" + str(value), "А гарантия у вас есть?", malformed)
    clarify = env(kind="price", route="CLARIFY", commercial_intent="price",
                  clarify_axis="extent", service_id="classic", service_reference_status="resolved",
                  requested_service_id="classic")
    clarify["patient_text"] = "Сколько зубов нужно восстановить?"
    clarify["request_understanding"]["requests"].append(
        {"request_id": "r2", "kind": "other", "subject_id": None, "context": "unknown"})
    turn("clarify_empty_other", "Сколько стоит имплантация?", clarify)
    report = env(kind="price", service_id="classic", extent="one_tooth", commercial_intent="price",
                 service_reference_status="resolved", requested_service_id="classic")
    if args.revision == "working":
        report["request_understanding"].update(scope_commitment="reported", tooth_count=1)
    turn("self_scope", "У меня нет одного зуба. Сколько стоит восстановить?", report, "audit-subject")
    other = env(kind="price", commercial_intent="price", service_id="classic",
                service_reference_status="resolved", requested_service_id="classic")
    other["request_understanding"]["subjects"] = [{"subject_id": "s1", "relation": "other", "age_group": "adult"}]
    other["request_understanding"]["requests"][0]["subject_id"] = "s1"
    turn("other_subject", "Теперь спрашиваю для другого человека, сколько стоит имплантация?", other, "audit-subject")
    # Control: the authored pain card has usable UI when its identity is supplied.
    from core.target_presentation_decision import _cap_secondary_content, TargetPresentationCadenceState
    replies, video, situation, update, dropped = _cap_secondary_content(
        md_root=ROOT / "clients/demo/md", client_id="demo",
        primary_content_ref="implantation__faq__pain.md", used_content_refs=(),
        content_followups=(), cadence=TargetPresentationCadenceState(), allow_situation=True,
    )
    print("AUDIT_CONTROL " + json.dumps({"case": "pain_source_supplied",
          "quick_replies": replies, "video": bool(video), "situation": situation,
          "dropped": dropped}, ensure_ascii=True), flush=True)
    print(json.dumps({"network_attempts": len(network_attempts)}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
