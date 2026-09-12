from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

import logging_setup as ls


def test_purge_old_log_files_removes_stale_rotated(tmp_path, monkeypatch):
    active = tmp_path / "demo-app.jsonl"
    monkeypatch.setattr(ls, "LOG_DIR", str(tmp_path))
    monkeypatch.setattr(ls, "LOG_FILE", str(active))
    monkeypatch.setattr(ls, "_LOG_RETENTION_DAYS", 7)

    old = tmp_path / "demo-app.jsonl.2"
    old.write_text("{}", encoding="utf-8")
    old_mtime = time.time() - 10 * 86400
    os.utime(old, (old_mtime, old_mtime))

    fresh = tmp_path / "demo-app.jsonl"
    fresh.write_text("{}", encoding="utf-8")

    removed = ls.purge_old_log_files()
    assert removed == ["demo-app.jsonl.2"]
    assert not old.exists()
    assert fresh.exists()


def test_purge_skipped_when_retention_zero(tmp_path, monkeypatch):
    active = tmp_path / "app.jsonl"
    monkeypatch.setattr(ls, "LOG_DIR", str(tmp_path))
    monkeypatch.setattr(ls, "LOG_FILE", str(active))
    monkeypatch.setattr(ls, "_LOG_RETENTION_DAYS", 0)

    stale = tmp_path / "app.jsonl.1"
    stale.write_text("{}", encoding="utf-8")
    old_mtime = time.time() - 30 * 86400
    os.utime(stale, (old_mtime, old_mtime))

    assert ls.purge_old_log_files() == []
    assert stale.exists()


def test_resolve_log_paths_default_is_repo_absolute() -> None:
    log_dir, log_file = ls.resolve_log_paths(log_dir_env="logs", log_file_env="app.jsonl")
    assert Path(log_file).is_absolute()
    assert Path(log_dir).is_absolute()
    assert log_file.endswith("app.jsonl")
    assert log_file.startswith(log_dir)


def test_resolve_log_paths_independent_of_cwd(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.chdir(other)
    log_dir, log_file = ls.resolve_log_paths(
        repo_root=repo,
        log_dir_env="logs",
        log_file_env="nested/app.jsonl",
    )
    assert log_file == str((repo / "logs" / "nested" / "app.jsonl").resolve())
    assert log_dir == str((repo / "logs").resolve())


def test_resolve_log_paths_preserves_absolute_env() -> None:
    abs_dir = (Path(ls._REPO_ROOT) / "abs_logs").resolve()
    abs_file = (abs_dir / "custom.jsonl").resolve()
    log_dir, log_file = ls.resolve_log_paths(
        log_dir_env=str(abs_dir),
        log_file_env=str(abs_file),
    )
    assert log_file == str(abs_file)
    assert log_dir == str(abs_dir)


def test_purge_preserves_stale_active_base_log(tmp_path, monkeypatch) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    active = nested / "app.jsonl"
    active.write_text('{"keep": true}\n', encoding="utf-8")
    old_mtime = time.time() - 30 * 86400
    os.utime(active, (old_mtime, old_mtime))
    monkeypatch.setattr(ls, "LOG_DIR", str(tmp_path))
    monkeypatch.setattr(ls, "LOG_FILE", str(active))
    monkeypatch.setattr(ls, "_LOG_RETENTION_DAYS", 7)

    removed = ls.purge_old_log_files()
    assert removed == []
    assert active.exists()
    assert "keep" in active.read_text(encoding="utf-8")


def test_purge_uses_log_file_parent_for_nested_paths(tmp_path, monkeypatch) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    active = nested / "app.jsonl"
    active.write_text("{}", encoding="utf-8")
    stale_rotated = nested / "app.jsonl.3"
    stale_rotated.write_text("{}", encoding="utf-8")
    old_mtime = time.time() - 10 * 86400
    os.utime(stale_rotated, (old_mtime, old_mtime))
    monkeypatch.setattr(ls, "LOG_DIR", str(tmp_path))
    monkeypatch.setattr(ls, "LOG_FILE", str(active))
    monkeypatch.setattr(ls, "_LOG_RETENTION_DAYS", 7)

    removed = ls.purge_old_log_files()
    assert removed == ["app.jsonl.3"]
    assert active.exists()
    assert not stale_rotated.exists()


def test_resolve_log_paths_rejects_relative_traversal(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    with pytest.raises(ValueError, match="inside LOG_DIR"):
        ls.resolve_log_paths(
            repo_root=repo,
            log_dir_env="logs",
            log_file_env="../escape.jsonl",
        )


def test_startup_event_available_after_shutdown(tmp_path) -> None:
    log_dir = tmp_path / "startup_logs"
    log_dir.mkdir()
    script = """
import json, os, sys
log_dir = sys.argv[1]
os.environ["BOT_LOG_DIR"] = log_dir
os.environ["BOT_LOG_FILE"] = "app.jsonl"
os.environ["BOT_LOG_RETENTION_DAYS"] = "0"
from logging_setup import get_logger, LOG_FILE, _shutdown_logging, log_json
logger = get_logger("retention-startup-test")
log_json(logger, "retention_probe", probe="ok")
_shutdown_logging()
rows = []
with open(LOG_FILE, encoding="utf-8") as fh:
    for raw in fh:
        raw = raw.strip()
        if raw:
            rows.append(json.loads(raw))
startup = [r for r in rows if r.get("msg") == "logging_startup"]
probes = [r for r in rows if r.get("msg") == "retention_probe"]
assert len(startup) == 1, startup
assert len(probes) == 1, probes
print("ok")
"""
    proc = subprocess.run(
        [sys.executable, "-c", script, str(log_dir)],
        cwd=str(Path(__file__).resolve().parents[1]),
        capture_output=True,
        text=True,
        check=True,
    )
    assert proc.stdout.strip().endswith("ok")
    log_file = log_dir / "app.jsonl"
    assert log_file.is_file()
    rows = [json.loads(line) for line in log_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len([r for r in rows if r.get("msg") == "logging_startup"]) == 1
    assert len([r for r in rows if r.get("msg") == "retention_probe"]) == 1
