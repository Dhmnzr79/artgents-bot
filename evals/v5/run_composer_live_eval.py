"""Composer live eval — 15 questions, hard checks + manual tone review block."""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, TextIO

_EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
if _EVAL_DIR not in sys.path:
    sys.path.insert(0, _EVAL_DIR)

from smoke_case_runner import (  # noqa: E402
    here,
    load_json,
    post_ask_json,
    post_ask_stream,
    reset_smoke_session,
    uses_test_client,
)

_DIGITS_ONLY_RX = re.compile(r"[\s\u00a0\u202f.,]")


@dataclass
class HardCheck:
    name: str
    status: str  # PASS | FAIL | n/a
    reason: str = ""


@dataclass
class CaseRun:
    case_id: str
    group: str
    question: str
    expected_path: str
    expected_aspects: list[str]
    answer: str = ""
    answer_path: str = ""
    numeric_gate_action: str = ""
    composer_skip_reason: str = ""
    forbidden_claim_hits: list[str] = field(default_factory=list)
    hard_checks: list[HardCheck] = field(default_factory=list)
    error: str = ""

    @property
    def c1(self) -> str:
        return _check_status(self.hard_checks, "C1")

    @property
    def c2(self) -> str:
        return _check_status(self.hard_checks, "C2")

    @property
    def c6(self) -> str:
        return _check_status(self.hard_checks, "C6")

    @property
    def hard_fail(self) -> bool:
        return any(c.status == "FAIL" for c in self.hard_checks)


def _check_status(checks: list[HardCheck], name: str) -> str:
    for c in checks:
        if c.name == name:
            return c.status
    return "n/a"


def repo_root() -> str:
    return os.path.abspath(os.path.join(_EVAL_DIR, "..", ".."))


def default_output_path() -> str:
    env = (os.getenv("COMPOSER_LIVE_EVAL_OUTPUT") or "").strip()
    if env:
        return env
    return os.path.join(repo_root(), "eval_composer_live_last.txt")


def normalize_digits(text: str) -> str:
    return _DIGITS_ONLY_RX.sub("", text or "")


def amount_in_text(amount: int, text: str) -> bool:
    needle = str(int(amount))
    return needle in normalize_digits(text)


def meta_gate_action(meta: dict[str, Any]) -> str:
    gate = meta.get("numeric_fact_gate")
    if isinstance(gate, dict):
        return str(gate.get("action") or "").strip()
    return ""


def meta_str_list(meta: dict[str, Any], key: str) -> list[str]:
    raw = meta.get(key)
    if not isinstance(raw, list):
        return []
    return [str(x).strip() for x in raw if str(x).strip()]


def evaluate_hard_checks(
    *,
    answer: str,
    meta: dict[str, Any],
    expected_path: str,
    expected_amounts: list[int],
) -> list[HardCheck]:
    answer_path = str(meta.get("answer_path") or "").strip()
    gate_action = meta_gate_action(meta)
    forbidden_hits = meta_str_list(meta, "forbidden_claim_hits")

    checks: list[HardCheck] = []

    # C6 — route
    if answer_path == expected_path:
        checks.append(HardCheck("C6", "PASS"))
    else:
        checks.append(
            HardCheck(
                "C6",
                "FAIL",
                f"answer_path={answer_path!r} expected={expected_path!r}",
            )
        )

    # C1 — amounts + numeric gate
    if expected_amounts:
        missing = [a for a in expected_amounts if not amount_in_text(a, answer)]
        gate_ok = gate_action == "pass"
        if not missing and gate_ok:
            checks.append(HardCheck("C1", "PASS"))
        else:
            parts: list[str] = []
            if missing:
                parts.append(f"missing_amounts={missing}")
            if not gate_ok:
                parts.append(f"numeric_gate={gate_action!r} (expected pass)")
            checks.append(HardCheck("C1", "FAIL", "; ".join(parts)))
    else:
        checks.append(HardCheck("C1", "n/a"))

    # C2 — forbidden claims telemetry
    if forbidden_hits:
        checks.append(
            HardCheck("C2", "FAIL", f"forbidden_claim_hits={forbidden_hits!r}")
        )
    else:
        checks.append(HardCheck("C2", "PASS"))

    return checks


def run_case(
    row: dict[str, Any],
    *,
    bot_url: str,
    timeout_sec: float,
    run_tag: str,
    ts: int,
    use_stream: bool,
) -> CaseRun:
    case_id = str(row.get("id") or "").strip() or "case"
    group = str(row.get("group") or "").strip()
    question = str(row.get("question") or "").strip()
    client_id = str(row.get("client_id") or "demo").strip()
    expected_path = str(row.get("expected_path") or "").strip()
    expected_aspects = [str(x).strip() for x in (row.get("expected_aspects") or []) if str(x).strip()]
    raw_amounts = row.get("expected_amounts") or []
    expected_amounts = [int(x) for x in raw_amounts if x is not None]

    sid = f"composer_live_{case_id}_{ts}_{run_tag}"
    if uses_test_client():
        reset_smoke_session(sid)

    run = CaseRun(
        case_id=case_id,
        group=group,
        question=question,
        expected_path=expected_path,
        expected_aspects=expected_aspects,
    )

    try:
        ask_payload = {"q": question, "sid": sid, "client_id": client_id}
        if use_stream:
            resp = post_ask_stream(bot_url, ask_payload, timeout_sec)
        else:
            resp = post_ask_json(bot_url, ask_payload, timeout_sec)
    except Exception as e:
        run.error = str(e)[:300]
        run.hard_checks = [
            HardCheck("C6", "FAIL", f"request_error: {run.error}"),
            HardCheck("C1", "n/a"),
            HardCheck("C2", "n/a"),
        ]
        return run

    meta = resp.get("meta") if isinstance(resp.get("meta"), dict) else {}
    run.answer = str(resp.get("answer") or "")
    run.answer_path = str(meta.get("answer_path") or "")
    run.numeric_gate_action = meta_gate_action(meta)
    run.composer_skip_reason = str(meta.get("composer_skip_reason") or "")
    run.forbidden_claim_hits = meta_str_list(meta, "forbidden_claim_hits")
    run.hard_checks = evaluate_hard_checks(
        answer=run.answer,
        meta=meta,
        expected_path=expected_path,
        expected_amounts=expected_amounts,
    )
    return run


def print_warning_if_composer_off(out: TextIO) -> None:
    from smoke_case_runner import ensure_repo_on_path

    ensure_repo_on_path()
    from config import COMPOSER_ON

    if not COMPOSER_ON:
        msg = (
            "⚠ COMPOSER_ON=0 — композер не сработает, запусти с COMPOSER_ON=1"
        )
        print(msg, file=out, flush=True)
        print(file=out, flush=True)


def print_results_table(runs: list[CaseRun], out: TextIO) -> None:
    header = (
        f"| {'id':<4} | {'grp':<3} | {'answer_path':<13} | {'C1':<4} | "
        f"{'C2':<4} | {'C6':<4} | {'skip_reason':<16} | {'numeric_gate':<12} |"
    )
    sep = "+" + "-" * 86 + "+"
    print(sep, file=out)
    print(header, file=out)
    print(sep, file=out)
    for r in runs:
        skip = (r.composer_skip_reason or r.error or "")[:16]
        gate = (r.numeric_gate_action or "-")[:12]
        print(
            f"| {r.case_id:<4} | {r.group:<3} | {r.answer_path or '-':<13} | "
            f"{r.c1:<4} | {r.c2:<4} | {r.c6:<4} | {skip:<16} | {gate:<12} |",
            file=out,
        )
        for chk in r.hard_checks:
            if chk.status == "FAIL" and chk.reason:
                print(f"  - {chk.name} FAIL: {chk.reason}", file=out)
    print(sep, file=out)
    print(file=out)


def print_tone_review_block(runs: list[CaseRun], out: TextIO) -> None:
    print("=== Тексты для оценки тона (C3/C4/C5 — вручную) ===", file=out)
    print(file=out)
    for r in runs:
        print(f"--- {r.case_id} ({r.group}) ---", file=out)
        print(f"Вопрос: {r.question}", file=out)
        aspects = ", ".join(r.expected_aspects) if r.expected_aspects else "(нет)"
        print(f"expected_aspects: {aspects}", file=out)
        print(f"answer_path: {r.answer_path or '-'}", file=out)
        if r.error:
            print(f"ERROR: {r.error}", file=out)
        else:
            print("Ответ:", file=out)
            print(r.answer or "(пусто)", file=out)
        print(file=out)


def print_summary(runs: list[CaseRun], out: TextIO) -> None:
    composer_n = sum(1 for r in runs if r.answer_path == "composer")
    single_n = sum(1 for r in runs if r.answer_path == "single_source")
    hard_fails = sum(1 for r in runs if r.hard_fail)
    composite = [r for r in runs if r.expected_path == "composer"]
    skip_counts: dict[str, int] = {}
    for r in composite:
        if r.composer_skip_reason:
            key = r.composer_skip_reason
            skip_counts[key] = skip_counts.get(key, 0) + 1

    print("=== Сводка ===", file=out)
    print(f"Всего кейсов: {len(runs)}", file=out)
    print(f"composer: {composer_n} | single_source: {single_n}", file=out)
    print(f"Жёстких FAIL (C1/C2/C6): {hard_fails}", file=out)
    if composite:
        skipped = sum(1 for r in composite if r.composer_skip_reason)
        print(
            f"Откаты на составных (expected composer): {skipped}/{len(composite)}",
            file=out,
        )
        if skip_counts:
            print("composer_skip_reason на составных:", file=out)
            for reason, cnt in sorted(skip_counts.items()):
                print(f"  - {reason}: {cnt}", file=out)
    print(file=out)


def run_eval(
    *,
    spec_path: str,
    bot_url: str,
    timeout_sec: float,
    filter_ids: set[str] | None,
    output_path: str,
    use_stream: bool,
) -> int:
    spec = load_json(spec_path)
    cases = spec.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("cases must be a non-empty array")

    rows = [r for r in cases if isinstance(r, dict)]
    if filter_ids is not None:
        rows = [r for r in rows if str(r.get("id") or "").strip() in filter_ids]
        if not rows:
            raise ValueError(f"no cases match filter {sorted(filter_ids)!r}")

    ts = int(time.time())
    run_tag = uuid.uuid4().hex[:8]
    runs: list[CaseRun] = []
    for row in rows:
        runs.append(
            run_case(
                row,
                bot_url=bot_url,
                timeout_sec=timeout_sec,
                run_tag=run_tag,
                ts=ts,
                use_stream=use_stream,
            )
        )

    lines: list[str] = []

    class _Tee:
        def write(self, s: str) -> int:
            sys.stdout.write(s)
            lines.append(s)
            return len(s)

        def flush(self) -> None:
            sys.stdout.flush()

    out: TextIO = _Tee()  # type: ignore[assignment]

    print("=== Composer Live Eval ===", file=out)
    print(f"spec: {spec_path}", file=out)
    door = "/ask/stream (widget)" if use_stream else "/ask (json)"
    print(f"bot: {bot_url} | door={door} | test_client={uses_test_client()}", file=out)
    print(file=out)

    print_warning_if_composer_off(out)

    print_results_table(runs, out)
    print_tone_review_block(runs, out)
    print_summary(runs, out)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("".join(lines))
    print(f"Saved: {output_path}", flush=True)

    return 1 if any(r.hard_fail for r in runs) else 0


def main(argv: list[str] | None = None) -> int:
    argv = list(argv or [])
    ap = argparse.ArgumentParser(
        description="Composer live eval (hard checks + manual tone block)",
        allow_abbrev=False,
    )
    ap.add_argument("--case-id", action="append", default=None, metavar="ID")
    ap.add_argument(
        "--json",
        action="store_true",
        help="Use POST /ask JSON door instead of default /ask/stream (widget).",
    )
    ns, unknown = ap.parse_known_args(argv)
    if unknown:
        print(f"WARNING: ignored unknown args: {unknown!r}", file=sys.stderr, flush=True)

    spec_path = (os.getenv("COMPOSER_LIVE_EVAL_PATH") or "").strip() or here(
        "composer_live.json"
    )
    bot_url = (os.getenv("BOT_URL") or "http://localhost:5000/ask").strip()
    timeout_sec = float(os.getenv("BOT_TIMEOUT_SEC") or os.getenv("COMPOSER_LIVE_TIMEOUT_SEC") or "90")
    output_path = default_output_path()

    filter_ids: set[str] | None = None
    if ns.case_id:
        filter_ids = {str(x).strip() for x in ns.case_id if str(x).strip()}

    return run_eval(
        spec_path=spec_path,
        bot_url=bot_url,
        timeout_sec=timeout_sec,
        filter_ids=filter_ids,
        output_path=output_path,
        use_stream=not ns.json,
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
