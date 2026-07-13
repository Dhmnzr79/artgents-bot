"""A6 direct-planner harness for frozen native-topic quality matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from collections import Counter
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, TextIO

_EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_EVAL_DIR, "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

FROZEN_MATRIX_PATH = os.path.join(_REPO_ROOT, "evals", "v5", "demo", "topic_shadow_matrix.json")
FROZEN_PRESERVATION_PATH = os.path.join(_REPO_ROOT, "evals", "v5", "demo", "preservation.json")
FROZEN_MATRIX_HASH = "dc356c9c738fb80a10cf0035508d7e8c8247979d"
FROZEN_PRESERVATION_HASH = "c2072ca74c2da73bf657d793195d2eb6c8ba7bd5"
CANONICAL_CLIENT_ID = "demo"

TOP_LEVEL_KEYS = frozenset(
    {
        "schema_version",
        "suite_id",
        "client_id",
        "execution_mode",
        "fresh_session_per_case",
        "authority",
        "taxonomy_source",
        "expected_taxonomy_ordered",
        "scoring_contract",
        "cases",
    }
)

CASE_KEYS = frozenset(
    {
        "id",
        "case_kind",
        "question",
        "expected_topic",
        "source_doc_id",
        "rationale",
    }
)

FORBIDDEN_CASE_KEYS = frozenset(
    {
        "observed_topic",
        "current",
        "actual",
        "pass",
    }
)

FROZEN_TAXONOMY_ORDERED = [
    "clinic",
    "doctors",
    "extraction",
    "implantation",
    "orthodontics",
    "periodontology",
    "prosthetics",
    "treatment",
    "whitening",
]

FROZEN_SCORING_CONTRACT: dict[str, Any] = {
    "scored_field": "turn_plan.topic",
    "confidence_field": "turn_plan.topic_confidence",
    "match_rule": "exact_normalized_or_null",
    "one_live_call_per_case": True,
    "retry_failed_case": False,
    "confidence_is_descriptive_only": True,
    "confidence_pass_threshold": None,
    "required_metrics": [
        "overall_exact_match",
        "per_topic_exact_match",
        "ambiguous_null_exact_match",
        "confusion_matrix",
        "planner_unavailable_count",
        "invalid_or_out_of_taxonomy_count",
        "confidence_by_correctness_descriptive",
    ],
    "authority_decision_allowed": False,
}

CONFUSION_ROWS = [*FROZEN_TAXONOMY_ORDERED, "__null__"]
CONFUSION_COLS = [*FROZEN_TAXONOMY_ORDERED, "__null__", "__planner_unavailable__", "__invalid__"]

CASE_RESULT_KEYS = frozenset(
    {
        "index",
        "case_id",
        "case_kind",
        "expected_topic",
        "observed_topic",
        "topic_confidence",
        "status",
        "reason",
    }
)


class HarnessConfigError(Exception):
    """Spec/hash/taxonomy/source/CLI configuration error (exit 2)."""


def git_blob_hash(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def _read_bytes(path: str) -> bytes:
    with open(path, "rb") as handle:
        return handle.read()


def canonical_git_blob_bytes(path: str) -> bytes:
    """Working-tree bytes normalized to LF for git-blob hash parity."""
    return _read_bytes(path).replace(b"\r\n", b"\n")


def validate_frozen_file_hash(*, path: str, expected_hash: str, label: str) -> None:
    actual = git_blob_hash(canonical_git_blob_bytes(path))
    if actual != expected_hash:
        raise HarnessConfigError(f"{label} hash mismatch")


def _require_exact_keys(payload: dict[str, Any], *, allowed: frozenset[str], label: str) -> None:
    keys = set(payload.keys())
    if keys != allowed:
        missing = sorted(allowed - keys)
        extra = sorted(keys - allowed)
        raise HarnessConfigError(f"{label} key mismatch missing={missing} extra={extra}")


def _validate_top_level(spec: dict[str, Any]) -> None:
    _require_exact_keys(spec, allowed=TOP_LEVEL_KEYS, label="spec top-level")
    if spec["schema_version"] != 1:
        raise HarnessConfigError("schema_version mismatch")
    if spec["suite_id"] != "a6_topic_shadow_quality_matrix":
        raise HarnessConfigError("suite_id mismatch")
    if spec["client_id"] != CANONICAL_CLIENT_ID:
        raise HarnessConfigError("client_id mismatch")
    if spec["execution_mode"] != "planner_direct_live":
        raise HarnessConfigError("execution_mode mismatch")
    if spec["fresh_session_per_case"] is not True:
        raise HarnessConfigError("fresh_session_per_case mismatch")
    if spec["authority"] != "shadow_only":
        raise HarnessConfigError("authority mismatch")
    if spec["taxonomy_source"] != "clients/{client_id}/md/*.md frontmatter.topic":
        raise HarnessConfigError("taxonomy_source mismatch")
    if spec["expected_taxonomy_ordered"] != FROZEN_TAXONOMY_ORDERED:
        raise HarnessConfigError("expected_taxonomy_ordered mismatch")
    if spec["scoring_contract"] != FROZEN_SCORING_CONTRACT:
        raise HarnessConfigError("scoring_contract mismatch")


def _validate_cases(cases: Sequence[dict[str, Any]], *, taxonomy: frozenset[str]) -> None:
    if len(cases) != 33:
        raise HarnessConfigError("cases count mismatch")
    ids = [case["id"] for case in cases]
    if len(set(ids)) != 33:
        raise HarnessConfigError("duplicate case ids")

    grounded = 0
    ambiguous = 0
    per_topic: Counter[str] = Counter()

    for case in cases:
        keys = set(case.keys())
        if keys != CASE_KEYS:
            raise HarnessConfigError(f"case {case.get('id')!r} key mismatch")
        if keys & FORBIDDEN_CASE_KEYS:
            raise HarnessConfigError(f"case {case['id']!r} forbidden keys present")
        question = str(case["question"] or "").strip()
        if not question:
            raise HarnessConfigError(f"case {case['id']!r} empty question")

        kind = case["case_kind"]
        expected = case["expected_topic"]
        source_doc_id = case["source_doc_id"]
        rationale = str(case["rationale"] or "").strip()

        if kind == "grounded_single_topic":
            grounded += 1
            if not isinstance(expected, str) or expected not in taxonomy:
                raise HarnessConfigError(f"case {case['id']!r} invalid grounded expected_topic")
            if not isinstance(source_doc_id, str) or not source_doc_id.strip():
                raise HarnessConfigError(f"case {case['id']!r} missing source_doc_id")
            if not rationale:
                raise HarnessConfigError(f"case {case['id']!r} missing rationale")
            per_topic[expected] += 1
        elif kind == "ambiguous_null":
            ambiguous += 1
            if expected is not None or source_doc_id is not None:
                raise HarnessConfigError(f"case {case['id']!r} ambiguous must be null source/topic")
            if not rationale:
                raise HarnessConfigError(f"case {case['id']!r} missing rationale")
        else:
            raise HarnessConfigError(f"case {case['id']!r} unknown case_kind")

    if grounded != 27 or ambiguous != 6:
        raise HarnessConfigError("grounded/ambiguous counts mismatch")
    for topic in FROZEN_TAXONOMY_ORDERED:
        if per_topic[topic] != 3:
            raise HarnessConfigError(f"per-topic grounded count mismatch for {topic}")


def _demo_doc_topics_by_doc_id() -> dict[str, str]:
    import frontmatter

    md_dir = Path(_REPO_ROOT) / "clients" / "demo" / "md"
    index: dict[str, str] = {}
    for path in sorted(md_dir.rglob("*.md")):
        if not path.is_file():
            continue
        post = frontmatter.load(path.open(encoding="utf-8-sig"))
        doc_id_raw = post.metadata.get("doc_id")
        if doc_id_raw is None:
            continue
        if not isinstance(doc_id_raw, str):
            raise HarnessConfigError("non-string doc_id in client frontmatter")
        doc_id = doc_id_raw.strip()
        if not doc_id:
            raise HarnessConfigError("empty doc_id in client frontmatter")
        if doc_id in index:
            raise HarnessConfigError(f"duplicate doc_id in client pack: {doc_id}")
        topic_raw = post.metadata.get("topic")
        if not isinstance(topic_raw, str):
            raise HarnessConfigError(f"invalid topic type for doc_id {doc_id}")
        topic = topic_raw.strip().lower()
        if not topic:
            raise HarnessConfigError(f"empty topic for doc_id {doc_id}")
        index[doc_id] = topic
    return index


def _validate_client_sources(cases: Sequence[dict[str, Any]], *, taxonomy: frozenset[str]) -> None:
    from core.topic_taxonomy import load_client_topic_taxonomy

    loaded = frozenset(load_client_topic_taxonomy(CANONICAL_CLIENT_ID))
    if loaded != taxonomy:
        raise HarnessConfigError("demo taxonomy mismatch")

    doc_topics = _demo_doc_topics_by_doc_id()
    for case in cases:
        if case["case_kind"] != "grounded_single_topic":
            continue
        source_doc_id = str(case["source_doc_id"])
        expected = str(case["expected_topic"])
        if source_doc_id not in doc_topics:
            raise HarnessConfigError(f"missing source doc_id {source_doc_id}")
        if doc_topics[source_doc_id] != expected:
            raise HarnessConfigError(f"source doc topic mismatch for {source_doc_id}")


def load_and_validate_spec() -> dict[str, Any]:
    validate_frozen_file_hash(
        path=FROZEN_MATRIX_PATH,
        expected_hash=FROZEN_MATRIX_HASH,
        label="matrix",
    )
    validate_frozen_file_hash(
        path=FROZEN_PRESERVATION_PATH,
        expected_hash=FROZEN_PRESERVATION_HASH,
        label="preservation",
    )
    spec = json.loads(_read_bytes(FROZEN_MATRIX_PATH).decode("utf-8"))
    if not isinstance(spec, dict):
        raise HarnessConfigError("spec root must be object")
    _validate_top_level(spec)
    taxonomy = frozenset(FROZEN_TAXONOMY_ORDERED)
    cases = spec["cases"]
    if not isinstance(cases, list):
        raise HarnessConfigError("cases must be list")
    _validate_cases(cases, taxonomy=taxonomy)
    _validate_client_sources(cases, taxonomy=taxonomy)
    return spec


def normalize_observed_topic(raw: object) -> str | None:
    if raw is None:
        return None
    if not isinstance(raw, str):
        return None
    normalized = raw.strip().lower()
    return normalized or None


def _confidence_is_valid(value: object) -> bool:
    if isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        return False
    number = float(value)
    if math.isnan(number) or math.isinf(number):
        return False
    return 0.0 <= number <= 1.0


def classify_plan_result(
    *,
    expected_topic: str | None,
    plan: object | None,
    taxonomy: frozenset[str],
    error: BaseException | None = None,
) -> dict[str, Any]:
    if error is not None:
        return {
            "observed_topic": None,
            "topic_confidence": None,
            "status": "ERROR",
            "reason": "planner_exception",
        }
    if plan is None:
        return {
            "observed_topic": None,
            "topic_confidence": None,
            "status": "ERROR",
            "reason": "planner_unavailable",
        }

    observed = normalize_observed_topic(getattr(plan, "topic", None))
    confidence_raw = getattr(plan, "topic_confidence", None)

    if not _confidence_is_valid(confidence_raw):
        return {
            "observed_topic": None,
            "topic_confidence": None,
            "status": "ERROR",
            "reason": "invalid_or_out_of_taxonomy",
        }

    confidence = float(confidence_raw)
    if observed is None:
        if confidence != 0.0:
            return {
                "observed_topic": None,
                "topic_confidence": None,
                "status": "ERROR",
                "reason": "invalid_or_out_of_taxonomy",
            }
    elif observed not in taxonomy:
        return {
            "observed_topic": None,
            "topic_confidence": None,
            "status": "ERROR",
            "reason": "invalid_or_out_of_taxonomy",
        }

    if observed == expected_topic:
        return {
            "observed_topic": observed,
            "topic_confidence": confidence,
            "status": "PASS",
            "reason": "exact_match",
        }

    return {
        "observed_topic": observed,
        "topic_confidence": confidence,
        "status": "FAIL",
        "reason": "topic_mismatch",
    }


def _empty_confusion_matrix() -> dict[str, dict[str, int]]:
    return {row: {col: 0 for col in CONFUSION_COLS} for row in CONFUSION_ROWS}


def _confusion_row_for_expected(expected_topic: str | None) -> str:
    return expected_topic if expected_topic is not None else "__null__"


def _confusion_col_for_result(result: dict[str, Any]) -> str:
    if result["reason"] in {"planner_unavailable", "planner_exception"}:
        return "__planner_unavailable__"
    if result["reason"] == "invalid_or_out_of_taxonomy":
        return "__invalid__"
    observed = result["observed_topic"]
    return observed if observed is not None else "__null__"


def _confidence_bucket(result: dict[str, Any]) -> str | None:
    if result["reason"] in {"planner_unavailable", "planner_exception"}:
        return None
    if result["reason"] == "invalid_or_out_of_taxonomy":
        return "invalid"
    if result["status"] == "PASS":
        return "correct"
    if result["status"] == "FAIL":
        return "incorrect"
    return None


def _descriptive_bucket(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "values": [], "min": None, "max": None, "mean": None}
    return {
        "count": len(values),
        "values": values,
        "min": min(values),
        "max": max(values),
        "mean": round(sum(values) / len(values), 4),
    }


def build_summary(
    *,
    spec: dict[str, Any],
    case_results: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    if len(case_results) != 33:
        raise ValueError("case_results must contain 33 entries")

    passed = sum(1 for row in case_results if row["status"] == "PASS")
    failed = sum(1 for row in case_results if row["status"] == "FAIL")
    errors = sum(1 for row in case_results if row["status"] == "ERROR")

    confusion = _empty_confusion_matrix()
    for result in case_results:
        row = _confusion_row_for_expected(result["expected_topic"])
        col = _confusion_col_for_result(result)
        confusion[row][col] += 1

    matrix_total = sum(confusion[row][col] for row in CONFUSION_ROWS for col in CONFUSION_COLS)
    if matrix_total != 33:
        raise ValueError("confusion matrix total must be 33")

    per_topic: dict[str, dict[str, Any]] = {}
    for topic in FROZEN_TAXONOMY_ORDERED:
        topic_rows = [r for r in case_results if r["expected_topic"] == topic]
        matched = sum(1 for r in topic_rows if r["status"] == "PASS")
        total = len(topic_rows)
        per_topic[topic] = {
            "matched": matched,
            "total": total,
            "rate": matched / total if total else 0.0,
        }

    ambiguous_rows = [r for r in case_results if r["case_kind"] == "ambiguous_null"]
    ambiguous_matched = sum(1 for r in ambiguous_rows if r["status"] == "PASS")

    confidence_values: dict[str, list[float]] = {
        "correct": [],
        "incorrect": [],
        "invalid": [],
    }
    for result in case_results:
        bucket = _confidence_bucket(result)
        if bucket is None:
            continue
        confidence = result["topic_confidence"]
        if confidence is None:
            continue
        confidence_values[bucket].append(float(confidence))

    return {
        "suite_id": spec["suite_id"],
        "client_id": spec["client_id"],
        "total": 33,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "skipped": 0,
        "overall_exact_match": {
            "matched": passed,
            "total": 33,
            "rate": passed / 33,
        },
        "per_topic_exact_match": per_topic,
        "ambiguous_null_exact_match": {
            "matched": ambiguous_matched,
            "total": 6,
            "rate": ambiguous_matched / 6,
        },
        "confusion_matrix": confusion,
        "planner_unavailable_count": sum(
            1 for r in case_results if r["reason"] in {"planner_unavailable", "planner_exception"}
        ),
        "invalid_or_out_of_taxonomy_count": sum(
            1 for r in case_results if r["reason"] == "invalid_or_out_of_taxonomy"
        ),
        "confidence_by_correctness_descriptive": {
            bucket: _descriptive_bucket(confidence_values[bucket])
            for bucket in ("correct", "incorrect", "invalid")
        },
        "authority_decision_allowed": False,
    }


def _emit_case(line: dict[str, Any], *, out: TextIO) -> None:
    payload = {key: line[key] for key in CASE_RESULT_KEYS}
    print(f"A6_CASE {json.dumps(payload, ensure_ascii=False)}", file=out, flush=True)


def _emit_summary(summary: dict[str, Any], *, out: TextIO) -> None:
    print(f"A6_SUMMARY {json.dumps(summary, ensure_ascii=False)}", file=out, flush=True)


def run_harness(
    *,
    plan_turn_fn: Callable[[str, None, str], object | None] | None = None,
    stdout: TextIO | None = None,
) -> int:
    out = stdout or sys.stdout
    spec = load_and_validate_spec()
    taxonomy = frozenset(FROZEN_TAXONOMY_ORDERED)

    if plan_turn_fn is None:
        from core.turn_planner_llm import plan_turn as plan_turn_fn

    case_results: list[dict[str, Any]] = []
    for index, case in enumerate(spec["cases"], start=1):
        expected_topic = case["expected_topic"]
        try:
            plan = plan_turn_fn(case["question"], None, CANONICAL_CLIENT_ID)
            classified = classify_plan_result(
                expected_topic=expected_topic,
                plan=plan,
                taxonomy=taxonomy,
            )
        except Exception as exc:
            classified = classify_plan_result(
                expected_topic=expected_topic,
                plan=None,
                taxonomy=taxonomy,
                error=exc,
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

    summary = build_summary(spec=spec, case_results=case_results)
    _emit_summary(summary, out=out)

    if summary["failed"] == 0 and summary["errors"] == 0 and summary["passed"] == 33:
        return 0
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    parser = argparse.ArgumentParser(
        description="A6 direct planner topic shadow eval",
        allow_abbrev=False,
    )
    _args, unknown = parser.parse_known_args(argv)
    if unknown:
        print("ERROR: unexpected CLI arguments", file=sys.stderr, flush=True)
        return 2

    try:
        return run_harness()
    except HarnessConfigError as exc:
        print(f"A6_CONFIG_ERROR {exc}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
