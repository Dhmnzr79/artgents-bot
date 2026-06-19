"""Shared e2e / metadata-first smoke case validation (backward compatible)."""
from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass
from typing import Any

import urllib.error
import urllib.request


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    status: str  # PASS | FAIL | ERROR | SKIP
    reason: str
    coverage_class: str = "UNKNOWN"


def load_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if not isinstance(obj, dict):
        raise ValueError("root must be an object")
    return obj


def here(*parts: str) -> str:
    return os.path.join(os.path.dirname(__file__), *parts)


def norm(s: str) -> str:
    return (s or "").strip().lower()


def contains_ci(haystack: str, needle: str) -> bool:
    return norm(needle) in norm(haystack)


def doc_id_from_meta(meta: dict[str, Any]) -> str:
    if meta.get("doc_id"):
        return str(meta["doc_id"]).strip()
    f = str(meta.get("file") or "").strip()
    if f.endswith(".md"):
        return f[:-3]
    return f


def doc_type_from_doc_id(doc_id: str) -> str:
    """Heuristic aligned with METADATA_FIRST_V1 doc_type rules."""
    d = (doc_id or "").strip().lower()
    if not d:
        return ""
    if d == "clinic__info__contacts" or d.endswith("__contacts"):
        return "contacts"
    if d.startswith("comparison__"):
        return "comparison"
    if d.startswith("doctors__doctor__"):
        return "doctor"
    if "__pricing__" in d:
        return "pricing"
    if "__faq__" in d:
        return "faq"
    if "__service__" in d:
        return "service"
    if "__info__" in d:
        return "info"
    return ""


def str_list_field(row: dict[str, Any], key: str) -> list[str]:
    raw = row.get(key)
    if not isinstance(raw, list) or not all(isinstance(x, str) for x in raw):
        return []
    return [str(x).strip() for x in raw if str(x).strip()]


def expand_cases(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Duplicate rows with `clients: [...]` into per-client runs."""
    out: list[dict[str, Any]] = []
    for row in cases:
        if not isinstance(row, dict):
            continue
        clients = row.get("clients")
        if isinstance(clients, list) and all(isinstance(x, str) for x in clients):
            base_id = str(row.get("id") or "").strip() or "case"
            for cid in clients:
                cid_s = str(cid).strip()
                if not cid_s:
                    continue
                copy = {k: v for k, v in row.items() if k != "clients"}
                copy["client_id"] = cid_s
                copy["id"] = f"{base_id}@{cid_s}"
                copy["_template_id"] = base_id
                out.append(copy)
        else:
            out.append(dict(row))
    return out


def infer_route_from_response(resp: dict[str, Any]) -> str:
    meta = resp.get("meta") or {}
    if not isinstance(meta, dict):
        meta = {}
    quick_replies = resp.get("quick_replies") or []

    svc = str(meta.get("service_route") or "").strip().lower()
    if svc:
        return svc

    orch = str(meta.get("orch_route") or "").strip().lower()
    if orch:
        return orch

    ingress_route = str(meta.get("ingress_route") or "").strip().lower()
    if ingress_route and ingress_route != "normal":
        return f"ingress_{ingress_route}"

    if bool(meta.get("handoff_filter")):
        return "handoff_filter"
    if bool(meta.get("lead_flow")) or bool(meta.get("booking_intent")):
        return "lead_flow"
    if bool(meta.get("low_score")):
        return "low_score_fallback"
    if str(meta.get("error") or "") == "rate_limited":
        return "rate_limited"

    intent = str(meta.get("intent") or "").strip().lower()
    if intent in {"price_lookup", "price_concern"}:
        return intent
    if intent == "offtopic":
        return "offtopic"
    if intent == "catalog_facts":
        return "catalog_facts"

    file = str(meta.get("file") or "").strip()
    if file == "clinic__info__contacts.md":
        return "contacts_chunk"
    if "__pricing__" in file:
        return "price_lookup"
    if file:
        return "retrieval_chunk"

    if isinstance(quick_replies, list) and len(quick_replies) > 0:
        return "guided"

    return ""


def validate_smoke_case(
    *,
    row: dict[str, Any],
    resp: dict[str, Any],
    answer: str,
    route: str,
) -> CaseResult | None:
    """
    Return CaseResult on FAIL/SKIP, or None if all checks pass.
    """
    case_id = str(row.get("id") or "").strip()
    cov = str(row.get("coverage_class") or row.get("testability") or "UNKNOWN").strip().upper()

    if row.get("skip"):
        return CaseResult(case_id=case_id, status="SKIP", reason="marked skip", coverage_class=cov)

    expected_route = row.get("expected_route")
    if expected_route is not None:
        expected_route = str(expected_route).strip()
    expected_route_any = row.get("expected_route_any")
    if expected_route_any is not None:
        if isinstance(expected_route_any, list) and all(isinstance(x, str) for x in expected_route_any):
            expected_route_any = [str(x).strip() for x in expected_route_any if str(x).strip()]
        else:
            expected_route_any = None

    if expected_route_any:
        if norm(route) not in {norm(x) for x in expected_route_any}:
            return CaseResult(
                case_id=case_id,
                status="FAIL",
                reason=f"route: got={route!r} want_any={expected_route_any!r}",
                coverage_class=cov,
            )
    elif expected_route and norm(route) != norm(expected_route):
        return CaseResult(
            case_id=case_id,
            status="FAIL",
            reason=f"route: got={route!r} want={expected_route!r}",
            coverage_class=cov,
        )

    meta = resp.get("meta") if isinstance(resp.get("meta"), dict) else {}
    got_doc_id = doc_id_from_meta(meta)
    got_doc_type = doc_type_from_doc_id(got_doc_id)

    expected_doc_id = row.get("expected_doc_id")
    if expected_doc_id is not None:
        want = str(expected_doc_id).strip()
        if want and norm(got_doc_id) != norm(want):
            return CaseResult(
                case_id=case_id,
                status="FAIL",
                reason=f"doc_id: got={got_doc_id!r} want={want!r}",
                coverage_class=cov,
            )

    expected_doc_id_any = str_list_field(row, "expected_doc_id_any")
    if expected_doc_id_any and norm(got_doc_id) not in {norm(x) for x in expected_doc_id_any}:
        return CaseResult(
            case_id=case_id,
            status="FAIL",
            reason=f"doc_id: got={got_doc_id!r} want_any={expected_doc_id_any!r}",
            coverage_class=cov,
        )

    got_service_id = str(meta.get("matched_service_id") or meta.get("service_id") or "").strip()
    expected_service_id = row.get("expected_service_id")
    if expected_service_id is not None:
        want_svc = str(expected_service_id).strip()
        if want_svc and norm(got_service_id) != norm(want_svc):
            return CaseResult(
                case_id=case_id,
                status="FAIL",
                reason=f"service_id: got={got_service_id!r} want={want_svc!r}",
                coverage_class=cov,
            )

    expected_service_id_any = str_list_field(row, "expected_service_id_any")
    if expected_service_id_any and norm(got_service_id) not in {norm(x) for x in expected_service_id_any}:
        return CaseResult(
            case_id=case_id,
            status="FAIL",
            reason=f"service_id: got={got_service_id!r} want_any={expected_service_id_any!r}",
            coverage_class=cov,
        )

    forbidden_doc_id = str_list_field(row, "forbidden_doc_id")
    if forbidden_doc_id and norm(got_doc_id) in {norm(x) for x in forbidden_doc_id}:
        return CaseResult(
            case_id=case_id,
            status="FAIL",
            reason=f"forbidden_doc_id hit: {got_doc_id!r}",
            coverage_class=cov,
        )

    forbidden_doc_type = str_list_field(row, "forbidden_doc_type")
    if forbidden_doc_type and got_doc_type and norm(got_doc_type) in {norm(x) for x in forbidden_doc_type}:
        return CaseResult(
            case_id=case_id,
            status="FAIL",
            reason=f"forbidden_doc_type hit: {got_doc_type!r}",
            coverage_class=cov,
        )

    # Phase 2+: only when test hook exposes metadata_first telemetry on response meta
    if row.get("expected_fallback_used") is not None:
        mf = meta.get("metadata_first")
        if not isinstance(mf, dict):
            return CaseResult(
                case_id=case_id,
                status="SKIP",
                reason="expected_fallback_used requires meta.metadata_first (test hook)",
                coverage_class=cov,
            )
        want_fb = bool(row.get("expected_fallback_used"))
        got_fb = bool(mf.get("fallback_used"))
        if got_fb != want_fb:
            return CaseResult(
                case_id=case_id,
                status="FAIL",
                reason=f"fallback_used: got={got_fb} want={want_fb}",
                coverage_class=cov,
            )

    if row.get("expected_doc_type") is not None:
        want_dt = str(row.get("expected_doc_type") or "").strip().lower()
        mf = meta.get("metadata_first")
        if isinstance(mf, dict) and str(mf.get("selected_doc_type") or "").strip():
            got_dt = str(mf.get("selected_doc_type") or "").strip().lower()
        else:
            got_dt = norm(got_doc_type)
        if want_dt and got_dt != want_dt:
            return CaseResult(
                case_id=case_id,
                status="FAIL",
                reason=f"doc_type: got={got_dt!r} want={want_dt!r}",
                coverage_class=cov,
            )

    must_contain = str_list_field(row, "must_contain")
    missing = [x for x in must_contain if x and not contains_ci(answer, x)]
    if missing:
        return CaseResult(
            case_id=case_id,
            status="FAIL",
            reason=f"must_contain_missing: {missing[:3]}",
            coverage_class=cov,
        )

    answer_signals_any = str_list_field(row, "answer_signals_any")
    if answer_signals_any and not any(contains_ci(answer, x) for x in answer_signals_any):
        return CaseResult(
            case_id=case_id,
            status="FAIL",
            reason=f"answer_signals_any: none of {answer_signals_any[:4]!r}",
            coverage_class=cov,
        )

    must_match_any_regex = str_list_field(row, "must_match_any_regex")
    if must_match_any_regex:
        if not any(re.search(pat, answer, re.IGNORECASE) for pat in must_match_any_regex):
            return CaseResult(
                case_id=case_id,
                status="FAIL",
                reason=f"must_match_any_regex: no match in {must_match_any_regex[:2]!r}",
                coverage_class=cov,
            )

    must_not_contain = str_list_field(row, "must_not_contain")
    forbidden_hit = [x for x in must_not_contain if x and contains_ci(answer, x)]
    if forbidden_hit:
        return CaseResult(
            case_id=case_id,
            status="FAIL",
            reason=f"must_not_contain_hit: {forbidden_hit[:3]}",
            coverage_class=cov,
        )

    slots_meta = meta.get("answer_slots") if isinstance(meta.get("answer_slots"), dict) else {}
    appended_slots = [
        str(x).strip()
        for x in (slots_meta.get("appended") or [])
        if isinstance(x, str) and str(x).strip()
    ]
    expected_answer_slots = str_list_field(row, "expected_answer_slots")
    if expected_answer_slots:
        got_norm = {norm(x) for x in appended_slots}
        missing_slots = [x for x in expected_answer_slots if norm(x) not in got_norm]
        if missing_slots:
            return CaseResult(
                case_id=case_id,
                status="FAIL",
                reason=f"expected_answer_slots missing: {missing_slots!r} got={appended_slots!r}",
                coverage_class=cov,
            )
    forbidden_answer_slots = str_list_field(row, "forbidden_answer_slots")
    if forbidden_answer_slots:
        hit = [x for x in forbidden_answer_slots if norm(x) in {norm(s) for s in appended_slots}]
        if hit:
            return CaseResult(
                case_id=case_id,
                status="FAIL",
                reason=f"forbidden_answer_slots hit: {hit!r}",
                coverage_class=cov,
            )

    return None


def uses_test_client() -> bool:
    return (os.getenv("E2E_USE_TEST_CLIENT") or "").strip().lower() in {"1", "true", "yes"}


def ensure_repo_on_path() -> str:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    return repo_root


def reset_smoke_session(sid: str) -> None:
    ensure_repo_on_path()
    from session import mem_reset

    mem_reset(sid)


def apply_session_seed(sid: str, seed: dict[str, Any]) -> None:
    ensure_repo_on_path()
    from session import set_pending_lead_offer

    if seed.get("pending_lead_offer"):
        set_pending_lead_offer(sid, True)


def http_post_json(url: str, payload: dict[str, Any], timeout_sec: float) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    out = json.loads(raw)
    if not isinstance(out, dict):
        raise ValueError("response is not a JSON object")
    return out


def post_ask_json(bot_url: str, payload: dict[str, Any], timeout_sec: float) -> dict[str, Any]:
    if uses_test_client():
        ensure_repo_on_path()
        from app import app

        _ = bot_url
        _ = timeout_sec
        client = app.test_client()
        resp = client.post("/ask", json=payload)
        out = resp.get_json()
        if not isinstance(out, dict):
            raise ValueError("response is not a JSON object")
        return out
    return http_post_json(bot_url, payload, timeout_sec=timeout_sec)


def debug_fail_must_contain(
    *,
    case_id: str,
    route: str,
    must_contain: list[str],
    missing: list[str],
    answer: str,
    resp: dict[str, Any],
) -> None:
    print("\n--- SMOKE_DEBUG_FAIL (must_contain) ---", flush=True)
    print(f"case_id: {case_id!r}", flush=True)
    print(f"route: {route!r}", flush=True)
    print(f"must_contain (declared): {must_contain!r}", flush=True)
    print(f"missing needles repr: {[repr(x) for x in missing]}", flush=True)
    print(f"answer[:300] repr: {answer[:300]!r}", flush=True)
    meta = resp.get("meta")
    if isinstance(meta, dict) and meta.get("file"):
        print(f"meta.file: {meta.get('file')!r}", flush=True)
    print("--- end SMOKE_DEBUG_FAIL ---\n", flush=True)


def print_table(rows: list[CaseResult]) -> None:
    w_id = max(10, max((len(r.case_id) for r in rows), default=10))
    w_status = 6
    w_reason = max(20, min(80, max((len(r.reason) for r in rows), default=20)))

    def line(a: str, b: str, c: str) -> str:
        return f"| {a:<{w_id}} | {b:<{w_status}} | {c:<{w_reason}} |"

    sep = f"+-{'-' * w_id}-+-{'-' * w_status}-+-{'-' * w_reason}-+"
    print(sep)
    print(line("id", "status", "reason (если fail)"))
    print(sep)
    for r in rows:
        print(line(r.case_id, r.status, r.reason[:w_reason]))
    print(sep)


def print_coverage_summary(results: list[CaseResult]) -> None:
    classes = ["STRONG", "MEDIUM", "WEAK", "TEMPLATE", "UNKNOWN"]
    by_tot = {c: 0 for c in classes}
    by_ok = {c: 0 for c in classes}
    for r in results:
        cc = r.coverage_class if r.coverage_class in by_tot else "UNKNOWN"
        by_tot[cc] = by_tot.get(cc, 0) + 1
        if r.status == "PASS":
            by_ok[cc] = by_ok.get(cc, 0) + 1
    print("+--------------+---------+---------+")
    print("| class        | passed  | total   |")
    print("+--------------+---------+---------+")
    for c in classes:
        if by_tot[c]:
            print(f"| {c:<12} | {by_ok[c]:>7} | {by_tot[c]:>7} |")
    print("+--------------+---------+---------")


def run_smoke_suite(
    *,
    spec_path: str,
    bot_url: str,
    timeout_sec: float,
    client_filter: str | None,
    filter_ids: set[str] | None,
    expand_multiclient: bool = True,
) -> int:
    spec = load_json(spec_path)
    baseline = spec.get("baseline")
    cases = spec.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("cases must be a non-empty array")
    if baseline is not None and not isinstance(baseline, int):
        raise ValueError("baseline must be null or int")

    if expand_multiclient:
        cases = expand_cases([r for r in cases if isinstance(r, dict)])

    if filter_ids is not None:
        cases = [r for r in cases if str(r.get("id") or "").strip() in filter_ids]
        if not cases:
            raise ValueError(f"no cases match filter {sorted(filter_ids)!r}")

    default_client = (os.getenv("CLIENT_ID") or "demo").strip().lower()
    if client_filter is not None:
        cases = [
            r
            for r in cases
            if str(r.get("client_id") or default_client).strip().lower() == client_filter
        ]
        if not cases:
            raise ValueError(f"no cases for client {client_filter!r}")

    results: list[CaseResult] = []
    passed = failed = errors = skipped = 0
    ts = int(time.time())
    run_tag = uuid.uuid4().hex[:8]

    for row in cases:
        case_id = str(row.get("id") or "").strip() or f"case_{uuid.uuid4().hex[:8]}"
        history = row.get("history") or []
        question = str(row.get("question") or "")
        client_id = str(row.get("client_id") or "").strip() or os.getenv("CLIENT_ID") or "demo"
        cov = str(row.get("coverage_class") or row.get("testability") or "UNKNOWN").strip().upper()

        sid = f"smoke_{case_id}_{ts}_{run_tag}"
        if uses_test_client():
            reset_smoke_session(sid)

        if isinstance(history, list):
            for h in history:
                if isinstance(h, dict) and str(h.get("question") or "").strip():
                    try:
                        post_ask_json(
                            bot_url,
                            {"q": str(h.get("question")), "sid": sid, "client_id": client_id},
                            timeout_sec,
                        )
                    except Exception:
                        pass

        session_seed = row.get("session_seed")
        if isinstance(session_seed, dict) and session_seed:
            if not uses_test_client():
                errors += 1
                results.append(
                    CaseResult(
                        case_id=case_id,
                        status="ERROR",
                        reason="session_seed requires E2E_USE_TEST_CLIENT=1",
                        coverage_class=cov,
                    )
                )
                continue
            apply_session_seed(sid, session_seed)

        try:
            resp = post_ask_json(
                bot_url, {"q": question, "sid": sid, "client_id": client_id}, timeout_sec
            )
        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            errors += 1
            results.append(
                CaseResult(case_id=case_id, status="ERROR", reason=f"http_error: {e!s}"[:120], coverage_class=cov)
            )
            continue
        except Exception as e:
            errors += 1
            results.append(
                CaseResult(
                    case_id=case_id, status="ERROR", reason=f"request_failed: {e!s}"[:120], coverage_class=cov
                )
            )
            continue

        answer = str(resp.get("answer") or "")
        route = infer_route_from_response(resp)
        fail = validate_smoke_case(row=row, resp=resp, answer=answer, route=route)
        if fail is not None:
            if fail.status == "SKIP":
                skipped += 1
            else:
                if "must_contain_missing" in fail.reason:
                    debug_fail_must_contain(
                        case_id=case_id,
                        route=route,
                        must_contain=str_list_field(row, "must_contain"),
                        missing=str_list_field(row, "must_contain"),
                        answer=answer,
                        resp=resp,
                    )
                failed += 1
            results.append(fail)
            continue

        passed += 1
        results.append(CaseResult(case_id=case_id, status="PASS", reason="ok", coverage_class=cov))

    print_table(results)
    total = passed + failed + errors + skipped
    acc = (passed / total) if total else 0.0
    print(
        f"SUMMARY: passed={passed}, failed={failed}, errors={errors}, skipped={skipped}, "
        f"total={total} (accuracy={acc:.1%})"
    )
    print()
    print_coverage_summary(results)

    if filter_ids is not None:
        return 0 if errors == 0 and failed == 0 else (2 if errors > 0 else 1)
    if baseline is None:
        return 0 if errors == 0 else 2
    min_ok = max(0, int(baseline) - 2)
    return 0 if passed >= min_ok else 1
