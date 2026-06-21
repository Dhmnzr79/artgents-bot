from __future__ import annotations

import os
import time
from pathlib import Path

import logging_setup as ls


def test_purge_old_log_files_removes_stale_rotated(tmp_path, monkeypatch):
    monkeypatch.setattr(ls, "LOG_DIR", str(tmp_path))
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
    monkeypatch.setattr(ls, "LOG_DIR", str(tmp_path))
    monkeypatch.setattr(ls, "_LOG_RETENTION_DAYS", 0)

    stale = tmp_path / "app.jsonl.1"
    stale.write_text("{}", encoding="utf-8")
    old_mtime = time.time() - 30 * 86400
    os.utime(stale, (old_mtime, old_mtime))

    assert ls.purge_old_log_files() == []
    assert stale.exists()
