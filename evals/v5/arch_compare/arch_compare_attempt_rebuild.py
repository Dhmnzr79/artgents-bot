"""Offline rebuild of architecture comparison LIVE attempt reports (read-only source)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evals.v5.arch_compare.arch_compare_live_report_v2 import (
    AttemptPersistenceCounters,
    compute_persistence_counters,
    write_rebuilt_reports,
)

READONLY_SOURCE_FILES = (
    "manifest.json",
    "schedule.json",
    "call_ledger.json",
    "raw_turns.json",
    "structured_turns.json",
    "blind_review.md",
    "blind_review.json",
    "technical_report.md",
    "blind_variant_mapping.json",
    "error_report.json",
    "run_stdout.log",
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_readonly_attempt_artifacts(source_dir: Path) -> dict[str, Any]:
    if not source_dir.is_dir():
        raise FileNotFoundError(f"attempt_source_missing:{source_dir}")
    manifest = _read_json(source_dir / "manifest.json")
    schedule = _read_json(source_dir / "schedule.json")
    ledger = _read_json(source_dir / "call_ledger.json")
    raw_turns = _read_json(source_dir / "raw_turns.json")
    structured_turns = _read_json(source_dir / "structured_turns.json")
    mapping_path = source_dir / "blind_variant_mapping.json"
    blind_mapping = _read_json(mapping_path) if mapping_path.exists() else {}
    auth = manifest.get("authorization") or {}
    source_attempt_sha = auth.get("expected_head") or manifest.get("head_sha")
    counters = compute_persistence_counters(
        ledger=ledger,
        structured_turns=structured_turns,
        raw_turns=raw_turns,
    )
    return {
        "manifest": manifest,
        "schedule": schedule,
        "call_ledger": ledger,
        "raw_turns": raw_turns,
        "structured_turns": structured_turns,
        "blind_variant_mapping": blind_mapping.get("mapping") or blind_mapping,
        "persistence_counters": counters,
        "source_attempt_sha": source_attempt_sha,
        "status": manifest.get("status"),
        "head_sha": manifest.get("head_sha"),
        "matrix_digest": manifest.get("matrix_digest"),
        "config_digest": manifest.get("config_digest"),
        "mode": "live_rebuilt_offline",
        "measurement_id": manifest.get("measurement_id"),
        "preflight": manifest.get("authorization"),
        "provider_call_total": manifest.get("provider_call_total"),
        "measurement_errors": manifest.get("measurement_errors") or [],
    }


def rebuild_attempt_reports(
    *,
    source_dir: Path,
    output_dir: Path,
    rebuilt_with_sha: str,
) -> dict[str, Path]:
    """Rebuild v2 blind/technical reports into a derived directory."""

    if output_dir.exists():
        raise FileExistsError(f"rebuild_output_exists:{output_dir}")
    source_dir = source_dir.resolve()
    output_dir = output_dir.resolve()
    if source_dir == output_dir:
        raise ValueError("rebuild_output_must_differ_from_source")

    before = {name: (source_dir / name).stat().st_mtime_ns for name in READONLY_SOURCE_FILES if (source_dir / name).exists()}
    run_result = load_readonly_attempt_artifacts(source_dir)
    attempt_id = str(run_result["manifest"]["attempt_id"])
    paths = write_rebuilt_reports(
        output_dir=output_dir,
        attempt_id=attempt_id,
        run_result=run_result,
        rebuilt_with_sha=rebuilt_with_sha,
    )
    # verify source untouched
    after = {name: (source_dir / name).stat().st_mtime_ns for name in before}
    if before != after:
        raise RuntimeError("source_artifacts_modified_during_rebuild")
    return paths


def default_attempt02_paths(repo_root: Path) -> tuple[Path, Path]:
    root = repo_root / "evals" / "v5" / "artifacts" / "arch_compare"
    source = root / "arch_compare_live_v1_2026-08-30-02"
    output = root / "arch_compare_live_v1_2026-08-30-02_rebuilt_corrected"
    return source, output
