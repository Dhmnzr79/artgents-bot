from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from evals.v5.medical_boundary_eval_contract import (
    DEFAULT_LIVE_ARTIFACT_PATHS,
    FROZEN_LIVE_RAW_SHA256,
    FROZEN_LIVE_RESULT_SHA256,
    LIVE_AUDIT_MANIFEST_PATH,
    validate_frozen_live_artifact_hashes,
)
from evals.v5.run_medical_boundary_eval import main, write_json_exclusive


def test_frozen_live_artifact_sha256_matches_owner_record() -> None:
    validate_frozen_live_artifact_hashes()


def test_audit_manifest_documents_first_live_run() -> None:
    manifest = json.loads(LIVE_AUDIT_MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["do_not_rerun"] is True
    assert manifest["status"] == "LIVE_ALREADY_RUN_ONCE"
    assert manifest["matrix_git_blob_hash"] == "7218e044b2f34b1be5c71b385d407e9ee8fb759d"
    assert manifest["artifacts"]["raw_sha256"] == FROZEN_LIVE_RAW_SHA256
    assert manifest["artifacts"]["result_sha256"] == FROZEN_LIVE_RESULT_SHA256
    assert manifest["run_record"]["total_cases"] == 26
    assert manifest["run_record"]["backend_calls"] == 26
    assert manifest["run_record"]["cli_exit_code"] == 0
    assert manifest["run_record"]["threshold_verdict"] == "PASS"
    assert manifest["run_record"]["exact_count"] == 25
    assert manifest["run_record"]["non_exact_cases"][0]["case_id"] == "mb_border_01"
    assert manifest["model"]["provenance_source"] == "first_live_run_stdout_llm_usage_log"


def test_live_backend_has_no_product_runtime_imports() -> None:
    source = Path("evals/v5/medical_boundary_eval_live_backend.py").read_text(encoding="utf-8")
    import_lines = "\n".join(
        line for line in source.splitlines() if line.startswith(("import ", "from "))
    ).lower()
    forbidden = (
        "app.",
        "orchestration",
        "session",
        "widget",
        "ingress",
        "turn_frame",
        "composer",
        "product",
    )
    assert all(token not in import_lines for token in forbidden)


def test_cli_default_without_live_is_fail_closed(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["--dry-run"])
    assert exit_code == 0
    exit_code = main([])
    captured = capsys.readouterr()
    assert exit_code == 3
    assert "LIVE_NOT_CONFIGURED" in captured.err


def test_cli_live_blocks_when_default_artifacts_exist(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    raw_path = tmp_path / "raw.json"
    result_path = tmp_path / "result.json"
    raw_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        "evals.v5.run_medical_boundary_eval.DEFAULT_LIVE_ARTIFACT_PATHS",
        (raw_path, result_path),
    )
    exit_code = main(
        [
            "--live",
            "--raw-output",
            str(tmp_path / "unused_raw.json"),
            "--output",
            str(tmp_path / "unused_result.json"),
        ]
    )
    assert exit_code == 2


def test_cli_live_pass_exits_zero(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    raw_path = tmp_path / "raw.json"
    result_path = tmp_path / "result.json"
    monkeypatch.setattr(
        "evals.v5.run_medical_boundary_eval.DEFAULT_LIVE_ARTIFACT_PATHS",
        (tmp_path / "guard_raw.json", tmp_path / "guard_result.json"),
    )

    def _fake_harness(**kwargs: object) -> dict[str, object]:
        _ = kwargs
        return {
            "summary": {
                "threshold_verdict": {"verdict": "PASS"},
            },
            "case_results": [],
        }

    monkeypatch.setattr("evals.v5.run_medical_boundary_eval.run_harness_with_backend_factory", _fake_harness)
    exit_code = main(
        [
            "--live",
            "--raw-output",
            str(raw_path),
            "--output",
            str(result_path),
        ]
    )
    assert exit_code == 0
    assert raw_path.exists()
    assert result_path.exists()


def test_cli_live_threshold_fail_exits_four(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    raw_path = tmp_path / "raw.json"
    result_path = tmp_path / "result.json"
    monkeypatch.setattr(
        "evals.v5.run_medical_boundary_eval.DEFAULT_LIVE_ARTIFACT_PATHS",
        (tmp_path / "guard_raw.json", tmp_path / "guard_result.json"),
    )

    def _fake_harness(**kwargs: object) -> dict[str, object]:
        _ = kwargs
        return {
            "summary": {
                "threshold_verdict": {"verdict": "FAIL"},
            },
            "case_results": [],
        }

    monkeypatch.setattr("evals.v5.run_medical_boundary_eval.run_harness_with_backend_factory", _fake_harness)
    exit_code = main(
        [
            "--live",
            "--raw-output",
            str(raw_path),
            "--output",
            str(result_path),
        ]
    )
    assert exit_code == 4


def test_write_json_exclusive_refuses_overwrite(tmp_path: Path) -> None:
    path = tmp_path / "artifact.json"
    write_json_exclusive(path, {"first": True})
    with pytest.raises(Exception, match="silent overwrite forbidden"):
        write_json_exclusive(path, {"second": True})


def test_default_live_artifact_paths_match_contract() -> None:
    assert DEFAULT_LIVE_ARTIFACT_PATHS[0].name == "medical_boundary_eval_live_raw.json"
    assert DEFAULT_LIVE_ARTIFACT_PATHS[1].name == "medical_boundary_eval_live_result.json"


def test_live_backend_not_imported_on_default_cli() -> None:
    script = (
        "import sys; "
        "import evals.v5.run_medical_boundary_eval as m; "
        "assert 'evals.v5.medical_boundary_eval_live_backend' not in sys.modules"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
