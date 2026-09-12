"""A7 attempt-aware topic shadow re-audit over the frozen A6 matrix."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from collections.abc import Callable, Sequence
from typing import Any, TextIO

_EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_EVAL_DIR, "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from evals.v5 import run_topic_shadow_eval as a6_harness

MEASUREMENT_ID = "a7_topic_shadow_attempt_reaudit"

CASE_RESULT_FIELDS = (
    "index",
    "case_id",
    "case_kind",
    "expected_topic",
    "observed_topic",
    "topic_confidence",
    "topic_field_status",
    "topic_field_error",
    "shadow_status",
    "legacy_plan_available",
    "status",
    "reason",
)
CASE_RESULT_KEYS = frozenset(CASE_RESULT_FIELDS)

SHADOW_STATUSES = ("ok", "partial", "not_available", "degraded")
TOPIC_FIELD_STATUSES = ("valid", "missing", "invalid", "defaulted", "unavailable")


def _result(
    *,
    observed_topic: str | None = None,
    topic_confidence: float | None = None,
    topic_field_status: str = "unavailable",
    topic_field_error: str | None = None,
    shadow_status: str = "not_available",
    legacy_plan_available: bool = False,
    status: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "observed_topic": observed_topic,
        "topic_confidence": topic_confidence,
        "topic_field_status": topic_field_status,
        "topic_field_error": topic_field_error,
        "shadow_status": shadow_status,
        "legacy_plan_available": legacy_plan_available,
        "status": status,
        "reason": reason,
    }


def classify_attempt_result(
    *,
    expected_topic: str | None,
    attempt: object | None,
    taxonomy: frozenset[str],
    error: BaseException | None = None,
) -> dict[str, Any]:
    """Classify only the shadow topic axis; never expose raw or exception text."""
    if error is not None:
        return _result(status="ERROR", reason="planner_exception")
    if attempt is None:
        return _result(status="ERROR", reason="planner_unavailable")

    shadow_status = getattr(attempt, "shadow_status", None)
    legacy_available = getattr(attempt, "legacy_plan", None) is not None
    if shadow_status == "not_available":
        return _result(
            shadow_status="not_available",
            legacy_plan_available=legacy_available,
            status="ERROR",
            reason="planner_unavailable",
        )
    if shadow_status == "degraded":
        return _result(
            shadow_status="degraded",
            legacy_plan_available=legacy_available,
            status="ERROR",
            reason="shadow_degraded",
        )
    if shadow_status not in {"ok", "partial"}:
        return _result(
            shadow_status="degraded",
            legacy_plan_available=legacy_available,
            status="ERROR",
            reason="invalid_shadow_metadata",
        )

    frame = getattr(attempt, "shadow_frame", None)
    if frame is None:
        return _result(
            shadow_status="not_available",
            legacy_plan_available=legacy_available,
            status="ERROR",
            reason="planner_unavailable",
        )

    try:
        topic_meta = frame.field_meta.topic
        field_status = str(topic_meta.status)
        field_error = topic_meta.error
        confidence_raw = topic_meta.confidence
        observed = a6_harness.normalize_observed_topic(frame.topic)
    except Exception:
        return _result(
            shadow_status=shadow_status,
            legacy_plan_available=legacy_available,
            status="ERROR",
            reason="invalid_shadow_metadata",
        )

    common = {
        "topic_field_status": field_status,
        "topic_field_error": str(field_error) if field_error is not None else None,
        "shadow_status": shadow_status,
        "legacy_plan_available": legacy_available,
    }
    if field_status == "invalid":
        return _result(
            **common,
            status="ERROR",
            reason="invalid_or_out_of_taxonomy",
        )
    if field_status == "defaulted" or field_status not in {"valid", "missing"}:
        return _result(
            **common,
            status="ERROR",
            reason="invalid_shadow_metadata",
        )
    if not a6_harness._confidence_is_valid(confidence_raw):
        return _result(
            **common,
            status="ERROR",
            reason="invalid_shadow_metadata",
        )

    confidence = float(confidence_raw)
    if field_status == "missing":
        if observed is not None or confidence != 0.0 or field_error is not None:
            return _result(
                **common,
                status="ERROR",
                reason="invalid_shadow_metadata",
            )
    elif observed is None or observed not in taxonomy or field_error is not None:
        return _result(
            **common,
            status="ERROR",
            reason="invalid_shadow_metadata",
        )

    if observed == expected_topic:
        return _result(
            observed_topic=observed,
            topic_confidence=confidence,
            **common,
            status="PASS",
            reason="exact_match",
        )
    return _result(
        observed_topic=observed,
        topic_confidence=confidence,
        **common,
        status="FAIL",
        reason="topic_mismatch",
    )


def _rows_for_a6_summary(case_results: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map new technical reasons into the frozen A6 aggregation columns."""
    rows: list[dict[str, Any]] = []
    for result in case_results:
        row = dict(result)
        if row["reason"] == "shadow_degraded":
            row["reason"] = "planner_unavailable"
        elif row["reason"] == "invalid_shadow_metadata":
            row["reason"] = "invalid_or_out_of_taxonomy"
        rows.append(row)
    return rows


def build_attempt_summary(
    *,
    spec: dict[str, Any],
    case_results: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    base = a6_harness.build_summary(
        spec=spec,
        case_results=_rows_for_a6_summary(case_results),
    )
    shadow_counts = Counter(str(row["shadow_status"]) for row in case_results)
    topic_status_counts = Counter(str(row["topic_field_status"]) for row in case_results)
    passed = sum(1 for row in case_results if row["status"] == "PASS")
    failed = sum(1 for row in case_results if row["status"] == "FAIL")

    base.update(
        {
            "measurement_id": MEASUREMENT_ID,
            "scoreable_count": passed + failed,
            "shadow_status_counts": {
                status: shadow_counts[status] for status in SHADOW_STATUSES
            },
            "topic_field_status_counts": {
                status: topic_status_counts[status] for status in TOPIC_FIELD_STATUSES
            },
            "legacy_plan_available_count": sum(
                1 for row in case_results if row["legacy_plan_available"]
            ),
            "planner_unavailable_count": sum(
                1
                for row in case_results
                if row["reason"] in {"planner_unavailable", "planner_exception"}
            ),
            "shadow_degraded_count": sum(
                1 for row in case_results if row["reason"] == "shadow_degraded"
            ),
            "invalid_or_out_of_taxonomy_count": sum(
                1
                for row in case_results
                if row["reason"] == "invalid_or_out_of_taxonomy"
            ),
            "invalid_shadow_metadata_count": sum(
                1 for row in case_results if row["reason"] == "invalid_shadow_metadata"
            ),
            "technical_unavailable_count": sum(
                1
                for row in case_results
                if row["reason"]
                in {"planner_unavailable", "planner_exception", "shadow_degraded"}
            ),
            "authority_decision_allowed": False,
        }
    )
    return base


def _emit_case(row: dict[str, Any], *, out: TextIO) -> None:
    payload = {field: row[field] for field in CASE_RESULT_FIELDS}
    print(f"A7_CASE {json.dumps(payload, ensure_ascii=False)}", file=out, flush=True)


def _emit_summary(summary: dict[str, Any], *, out: TextIO) -> None:
    print(f"A7_SUMMARY {json.dumps(summary, ensure_ascii=False)}", file=out, flush=True)


def run_harness(
    *,
    plan_turn_attempt_fn: Callable[[str, None, str], object] | None = None,
    stdout: TextIO | None = None,
) -> int:
    out = stdout or sys.stdout
    spec = a6_harness.load_and_validate_spec()
    taxonomy = frozenset(a6_harness.FROZEN_TAXONOMY_ORDERED)

    if plan_turn_attempt_fn is None:
        from core.turn_planner_llm import plan_turn_attempt as plan_turn_attempt_fn

    case_results: list[dict[str, Any]] = []
    for index, case in enumerate(spec["cases"], start=1):
        expected_topic = case["expected_topic"]
        try:
            attempt = plan_turn_attempt_fn(
                case["question"],
                None,
                a6_harness.CANONICAL_CLIENT_ID,
            )
        except Exception as exc:
            classified = classify_attempt_result(
                expected_topic=expected_topic,
                attempt=None,
                taxonomy=taxonomy,
                error=exc,
            )
        else:
            classified = classify_attempt_result(
                expected_topic=expected_topic,
                attempt=attempt,
                taxonomy=taxonomy,
            )

        row = {
            "index": index,
            "case_id": case["id"],
            "case_kind": case["case_kind"],
            "expected_topic": expected_topic,
            **classified,
        }
        case_results.append(row)
        _emit_case(row, out=out)

    summary = build_attempt_summary(spec=spec, case_results=case_results)
    _emit_summary(summary, out=out)
    if summary["passed"] == 33 and summary["failed"] == 0 and summary["errors"] == 0:
        return 0
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    parser = argparse.ArgumentParser(
        description="A7 PlannerAttempt topic shadow re-audit",
        allow_abbrev=False,
    )
    _args, unknown = parser.parse_known_args(argv)
    if unknown:
        print("A7_CONFIG_ERROR unexpected CLI arguments", file=sys.stderr, flush=True)
        return 2
    try:
        return run_harness()
    except a6_harness.HarnessConfigError as exc:
        print(f"A7_CONFIG_ERROR {exc}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
