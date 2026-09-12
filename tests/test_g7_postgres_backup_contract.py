"""G7 PostgreSQL backup foundation — static offline contract."""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BACKUP_SCRIPT = _REPO_ROOT / "deploy" / "production" / "server" / "backup-postgres.sh"
_VERIFY_SCRIPT = _REPO_ROOT / "deploy" / "production" / "server" / "verify-postgres-backup.sh"
_HELPER = _REPO_ROOT / "deploy" / "production" / "server" / "backup_postgres_g7.py"
_SERVICE = _REPO_ROOT / "deploy" / "production" / "server" / "artgents-postgres-backup.service"
_TIMER = _REPO_ROOT / "deploy" / "production" / "server" / "artgents-postgres-backup.timer"
_DEPLOY_SCRIPT = _REPO_ROOT / "deploy" / "production" / "server" / "deploy-production.sh"
_ROLLBACK_SCRIPT = _REPO_ROOT / "deploy" / "production" / "server" / "rollback-production.sh"
_CI_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
_PUBLISH_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "publish-image.yml"
_CONTRACT_PATH = Path(__file__).resolve()

_RECEIPT_ROOT = "/var/lib/artgents/backups/receipts"
_ARCHIVE_ROOT = "/var/lib/artgents/backups/postgres"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

_G7_STEM = "pgbackup-scheduled-2026-01-02T030405Z-abcdef0123456789"
_G7_BACKUP_ID = "11111111-2222-4333-8444-555555555555"

_REASONS = frozenset({"pre-deploy", "pre-rollback", "scheduled"})


def _make_backup_layout(tmp_path: Path) -> tuple[Path, Path, Path]:
    parent = tmp_path / "backups"
    archive_root = parent / "postgres"
    receipt_root = parent / "receipts"
    parent.mkdir(mode=0o700)
    archive_root.mkdir(mode=0o700)
    receipt_root.mkdir(mode=0o700)
    return parent, archive_root, receipt_root


def _write_valid_pair(
    *,
    archive_root: Path,
    receipt_root: Path,
    stem: str,
    created_at: str,
    backup_id: str = _G7_BACKUP_ID,
) -> tuple[Path, Path]:
    archive = archive_root / f"{stem}.pgdump.custom"
    archive.write_bytes(b"custom-format-bytes")
    receipt = receipt_root / f"{stem}.receipt.json"
    sha = g7.sha256_file(archive)
    payload = g7.build_receipt_payload(
        reason="scheduled",
        source_sha=None,
        created_at=created_at,
        archive_path=str(archive),
        archive_sha256=sha,
        archive_size_bytes=archive.stat().st_size,
        database_name="demo",
        backup_id=backup_id,
    )
    g7.write_receipt_atomic(receipt, payload)
    return archive, receipt


def _load_g7_module():
    spec = importlib.util.spec_from_file_location("backup_postgres_g7", _HELPER)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


g7 = _load_g7_module()


def _backup_text() -> str:
    return _BACKUP_SCRIPT.read_text(encoding="utf-8")


def _verify_text() -> str:
    return _VERIFY_SCRIPT.read_text(encoding="utf-8")


def parse_backup_cli(argv: list[str]) -> tuple[str, str | None]:
    """Mirror backup-postgres CLI grammar (offline)."""
    reason = ""
    source_sha: str | None = None
    source_seen = False
    idx = 0
    while idx < len(argv):
        token = argv[idx]
        if token == "--reason":
            if idx + 1 >= len(argv):
                raise ValueError("missing value for --reason")
            if reason:
                raise ValueError("duplicate --reason")
            reason = argv[idx + 1]
            idx += 2
            continue
        if token == "--source-sha":
            if idx + 1 >= len(argv):
                raise ValueError("missing value for --source-sha")
            if source_seen:
                raise ValueError("duplicate --source-sha")
            source_sha = argv[idx + 1]
            source_seen = True
            idx += 2
            continue
        raise ValueError("unexpected argument")
    if not reason:
        raise ValueError("missing --reason")
    if reason not in _REASONS:
        raise ValueError("invalid reason")
    if reason == "scheduled":
        if source_seen:
            raise ValueError("source-sha not allowed for scheduled backup")
        return reason, None
    if not source_seen or source_sha is None:
        raise ValueError("source-sha required")
    if not _SHA_RE.fullmatch(source_sha):
        raise ValueError("invalid source_sha")
    return reason, source_sha


def test_g7_contract_in_ci_and_publish() -> None:
    ci = _CI_WORKFLOW.read_text(encoding="utf-8")
    publish = _PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    assert str(_CONTRACT_PATH.relative_to(_REPO_ROOT)).replace("\\", "/") in ci
    verify = publish.split("verify:", 1)[1].split("secret-scan:", 1)[0]
    assert str(_CONTRACT_PATH.relative_to(_REPO_ROOT)).replace("\\", "/") in verify


def test_g2_mandatory_list_includes_g7() -> None:
    g2 = (_REPO_ROOT / "tests" / "test_g2_pr_ci_contract.py").read_text(encoding="utf-8")
    assert "tests/test_g7_postgres_backup_contract.py" in g2


def test_g3_publish_verify_includes_g7() -> None:
    g3 = (_REPO_ROOT / "tests" / "test_g3_immutable_image_contract.py").read_text(encoding="utf-8")
    assert "tests/test_g7_postgres_backup_contract.py" in g3


def test_backup_script_strict_mode_and_paths() -> None:
    text = _backup_text()
    assert text.startswith("#!/usr/bin/env bash")
    assert "set -Eeuo pipefail" in text
    assert "must run as root" in text
    assert "artgents-postgres-backup.lock" in text
    assert "artgents-production-deploy.lock" not in text
    assert "flock -n 8" in text
    assert "/etc/artgents/production.env" in text
    assert "--format=custom" in text
    assert "pg_restore --list" in text
    assert "eval" not in text
    assert "bash -c" not in text
    assert "sh -c" not in text
    assert "BOT_PG_DSN" not in text
    assert "POSTGRES_PASSWORD" not in text


def test_backup_umask_work_dir_and_exit_trap() -> None:
    text = _backup_text()
    assert "umask 077" in text
    assert 'mktemp -d "${ARCHIVE_ROOT}/.work.XXXXXX"' in text
    assert "verify_work_dir_containment" in text
    assert "trap cleanup_on_exit EXIT" in text
    assert "rm -rf \"$WORK_DIR\"" not in text


def test_backup_explicit_pg_dump_username_and_dbname() -> None:
    text = _backup_text()
    assert "parse-targets" in text
    assert '--username "$POSTGRES_USER_NAME"' in text
    assert '--dbname "$DATABASE_NAME"' in text
    assert "--format=custom" in text
    assert "compose exec -T postgres pg_dump" in text
    dump_block = text.split("compose exec -T postgres pg_dump", 1)[1].split(">", 1)[0]
    assert "--username" in dump_block and "--dbname" in dump_block


def test_backup_helper_mode_contract() -> None:
    text = _backup_text()
    assert 'backup helper must be mode 0750' in text
    verify = _verify_text()
    assert 'backup helper must be mode 0750' in verify
    readme = (_REPO_ROOT / "deploy/production/server/README.md").read_text(encoding="utf-8")
    assert "backup-postgres-g7.py" in readme and "`0750`" in readme
    assert "0644" not in readme


def test_backup_directory_must_be_exactly_0700() -> None:
    text = _backup_text()
    assert 'must be mode 0700' in text
    assert "BACKUPS_PARENT" in text


def test_backup_uses_compose_exec_postgres_only() -> None:
    text = _backup_text()
    assert "compose exec -T postgres pg_dump" in text
    assert "--username" in text and "--dbname" in text
    assert "5432" not in text


def test_backup_stdout_last_line_receipt_only() -> None:
    text = _backup_text()
    assert "printf '%s\\n' \"$RECEIPT_FINAL\"" in text
    assert "log_safe" in text


def test_backup_atomic_archive_and_receipt() -> None:
    text = _backup_text()
    assert 'mv -f "$ARCHIVE_TMP" "$ARCHIVE_FINAL"' in text
    assert 'mv -f "$RECEIPT_TMP" "$RECEIPT_FINAL"' in text
    assert "fsync_path" in text
    assert "chmod 600" in text
    assert "backup path collision" in text


def test_backup_retention_after_success() -> None:
    text = _backup_text()
    pos_dump = text.find("pg_dump")
    pos_retention = text.find("run-retention")
    pos_stdout = text.find('printf \'%s\\n\' "$RECEIPT_FINAL"')
    assert pos_dump != -1 and pos_retention != -1 and pos_stdout != -1
    assert pos_retention < pos_stdout


def test_g4_g5_backup_invocation_compatibility() -> None:
    deploy = _DEPLOY_SCRIPT.read_text(encoding="utf-8")
    rollback = _ROLLBACK_SCRIPT.read_text(encoding="utf-8")
    assert '"$BACKUP_BIN" --reason pre-deploy --source-sha "$SOURCE_SHA"' in deploy
    assert '"$BACKUP_BIN" --reason pre-rollback --source-sha "$CURRENT_SOURCE_SHA"' in rollback
    assert "tail -n 1" in deploy and "tail -n 1" in rollback


def test_systemd_timer_daily_persistent() -> None:
    timer = _TIMER.read_text(encoding="utf-8")
    assert "OnCalendar=daily" in timer
    assert "Persistent=true" in timer
    service = _SERVICE.read_text(encoding="utf-8")
    assert "Type=oneshot" in service
    assert "/opt/artgents/bin/backup-postgres --reason scheduled" in service
    assert "User=root" in service


def test_verifier_read_only_no_production_restore() -> None:
    text = _verify_text()
    lowered = text.lower()
    assert "pg_restore --list" in text
    assert "pg_restore -d" not in text
    assert "dropdb" not in lowered
    assert "createdb" not in lowered
    assert "psql" not in lowered
    assert "g8" in lowered or "unknown" in lowered


@pytest.mark.parametrize(
    "argv",
    [
        ["--reason", "pre-deploy", "--source-sha", "a" * 40],
        ["--reason", "pre-rollback", "--source-sha", "b" * 40],
        ["--reason", "scheduled"],
    ],
)
def test_cli_valid_combinations(argv: list[str]) -> None:
    reason, sha = parse_backup_cli(argv)
    assert reason in _REASONS
    if reason == "scheduled":
        assert sha is None


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["--reason", "evil"],
        ["--reason", "pre-deploy"],
        ["--reason", "scheduled", "--source-sha", "c" * 40],
        ["--reason", "pre-deploy", "--source-sha", "A" * 40],
        ["--reason", "pre-deploy", "--source-sha", "c" * 39],
        ["--extra", "--reason", "scheduled"],
        ["--reason", "pre-deploy", "--source-sha", "c" * 40, "evil"],
        ["--reason", "pre-deploy", "--source-sha", f"{'d' * 40}\n"],
    ],
)
def test_cli_invalid_combinations(argv: list[str]) -> None:
    with pytest.raises(ValueError):
        parse_backup_cli(argv)


def test_receipt_schema_and_no_secrets(tmp_path: Path) -> None:
    _, archive_root, _ = _make_backup_layout(tmp_path)
    archive = archive_root / f"{_G7_STEM}.pgdump.custom"
    archive.write_bytes(b"x" * 100)
    payload = g7.build_receipt_payload(
        reason="scheduled",
        source_sha=None,
        created_at="2026-01-02T03:04:05Z",
        archive_path=str(archive),
        archive_sha256="sha256:" + "a" * 64,
        archive_size_bytes=100,
        database_name="artgents",
        backup_id=_G7_BACKUP_ID,
    )
    blob = json.dumps(payload)
    assert "password" not in blob.lower()
    assert "dsn" not in blob.lower()
    assert payload["source_sha"] is None


def test_receipt_write_and_verify_roundtrip(tmp_path: Path) -> None:
    parent, archive_root, receipt_root = _make_backup_layout(tmp_path)
    archive, receipt = _write_valid_pair(
        archive_root=archive_root,
        receipt_root=receipt_root,
        stem=_G7_STEM,
        created_at="2026-01-02T03:04:05Z",
    )
    verified = g7.verify_receipt_file(
        receipt,
        archive_root=archive_root,
        receipt_root=receipt_root,
        backups_parent=parent,
        enforce_root_metadata=False,
    )
    assert verified["archive_sha256"] == g7.sha256_file(archive)


def test_retention_respects_cutoff_and_skips_damaged(tmp_path: Path) -> None:
    parent, archive_root, receipt_root = _make_backup_layout(tmp_path)
    now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    old_time = (now - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh_time = (now - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")

    old_arch, old_rec = _write_valid_pair(
        archive_root=archive_root,
        receipt_root=receipt_root,
        stem=f"pgbackup-scheduled-{g7.created_at_to_filename_timestamp(old_time)}-1111111111111111",
        created_at=old_time,
        backup_id="22222222-2222-4333-8444-555555555555",
    )
    fresh_arch, fresh_rec = _write_valid_pair(
        archive_root=archive_root,
        receipt_root=receipt_root,
        stem=f"pgbackup-scheduled-{g7.created_at_to_filename_timestamp(fresh_time)}-2222222222222222",
        created_at=fresh_time,
        backup_id="33333333-3333-4333-8444-555555555555",
    )
    damaged = receipt_root / "damaged.receipt.json"
    damaged.write_text('{"schema_version": 1, "status": "success"}', encoding="utf-8")

    candidates = g7.retention_candidates(
        archive_root=archive_root,
        receipt_root=receipt_root,
        backups_parent=parent,
        retention_days=7,
        now=now,
        enforce_root_metadata=False,
    )
    paths = {(a, r) for a, r in candidates}
    assert (old_arch.resolve(), old_rec.resolve()) in paths
    assert all(fresh_arch.resolve() != a for a, _ in paths)
    assert damaged.exists()

    g7.delete_retention_pair(old_arch, old_rec)
    assert not old_arch.exists() and not old_rec.exists()
    assert fresh_arch.exists() and fresh_rec.exists()


def test_outside_root_rejected(tmp_path: Path) -> None:
    archive_root = tmp_path / "archives"
    receipt_root = tmp_path / "receipts"
    archive_root.mkdir()
    receipt_root.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        g7.verify_receipt_file(outside, archive_root=archive_root, receipt_root=receipt_root)


def test_symlink_receipt_rejected(tmp_path: Path) -> None:
    archive_root = tmp_path / "archives"
    receipt_root = tmp_path / "receipts"
    archive_root.mkdir()
    receipt_root.mkdir()
    target = receipt_root / "real.receipt.json"
    target.write_text("{}", encoding="utf-8")
    link = receipt_root / "link.receipt.json"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlink not supported on this filesystem")
    with pytest.raises(ValueError):
        g7.verify_receipt_file(link, archive_root=archive_root, receipt_root=receipt_root)


def test_parse_postgres_targets(tmp_path: Path) -> None:
    env = tmp_path / "production.env"
    env.write_text(
        "POSTGRES_PASSWORD=secret\n"
        "POSTGRES_USER=bot_owner\n"
        "POSTGRES_DB=clinic_db\n"
        "BOT_PG_DSN=postgres://x\n",
        encoding="utf-8",
    )
    user, db = g7.parse_postgres_targets(env)
    assert user == "bot_owner"
    assert db == "clinic_db"
    assert g7.parse_postgres_db_name(env) == "clinic_db"


def test_shell_scripts_bash_n_if_available() -> None:
    from shutil import which

    bash = which("bash")
    if not bash:
        pytest.skip("bash not available")
    for path in (_BACKUP_SCRIPT, _VERIFY_SCRIPT):
        proc = subprocess.run([bash, "-n", str(path)], capture_output=True, text=True)
        if proc.returncode != 0 and "WSL" in (proc.stderr or ""):
            pytest.skip("bash available but cannot syntax-check (WSL not installed)")
        proc.check_returncode()


def test_helper_compiles() -> None:
    subprocess.run([sys.executable, "-m", "py_compile", str(_HELPER)], check=True)


def test_server_readme_documents_g7_g10_unknown() -> None:
    readme = (_REPO_ROOT / "deploy/production/server/README.md").read_text(encoding="utf-8")
    assert "G7" in readme
    assert "G10" in readme
    assert "G8" in readme
    assert "off-host" in readme.lower() or "Off-host" in readme


def test_production_readme_mentions_backup_paths() -> None:
    readme = (_REPO_ROOT / "deploy/production/README.md").read_text(encoding="utf-8")
    assert _ARCHIVE_ROOT in readme or "backups/postgres" in readme


def test_verifier_checks_env_before_docker() -> None:
    text = _verify_text()
    assert "check_env_permissions" in text
    assert "check_helper_metadata" in text
    docker_pos = text.find("docker compose")
    env_pos = text.find("check_env_permissions")
    assert env_pos != -1 and docker_pos != -1 and env_pos < docker_pos


def test_unknown_receipt_keys_rejected(tmp_path: Path) -> None:
    _, archive_root, _ = _make_backup_layout(tmp_path)
    archive = archive_root / f"{_G7_STEM}.pgdump.custom"
    archive.write_bytes(b"x")
    payload = g7.build_receipt_payload(
        reason="scheduled",
        source_sha=None,
        created_at="2026-01-02T03:04:05Z",
        archive_path=str(archive),
        archive_sha256=g7.sha256_file(archive),
        archive_size_bytes=1,
        database_name="demo",
        backup_id=_G7_BACKUP_ID,
    )
    payload["extra_field"] = 1
    with pytest.raises(ValueError, match="unknown or missing"):
        g7.validate_receipt_payload(payload)


def test_impossible_created_at_rejected() -> None:
    with pytest.raises(ValueError, match="invalid created_at"):
        g7.validate_created_at_utc("2026-02-30T12:00:00Z")


def test_invalid_backup_id_rejected() -> None:
    with pytest.raises(ValueError, match="invalid backup_id"):
        g7.validate_backup_id("not-a-uuid")


def test_directory_mode_0755_rejected(tmp_path: Path) -> None:
    loose = tmp_path / "loose"
    loose.mkdir(mode=0o755)
    with pytest.raises(ValueError, match="0700"):
        g7.assert_trusted_directory(loose, label="dir", enforce_root_metadata=True)


def test_symlink_to_valid_receipt_rejected(tmp_path: Path) -> None:
    parent, archive_root, receipt_root = _make_backup_layout(tmp_path)
    _, receipt = _write_valid_pair(
        archive_root=archive_root,
        receipt_root=receipt_root,
        stem=_G7_STEM,
        created_at="2026-01-02T03:04:05Z",
    )
    alias = receipt_root / "alias.receipt.json"
    try:
        alias.symlink_to(receipt)
    except OSError:
        pytest.skip("symlink not supported")
    with pytest.raises(ValueError, match="symlink"):
        g7.verify_receipt_file(
            alias,
            archive_root=archive_root,
            receipt_root=receipt_root,
            backups_parent=parent,
            enforce_root_metadata=False,
        )


def test_dangling_symlink_receipt_rejected(tmp_path: Path) -> None:
    parent, archive_root, receipt_root = _make_backup_layout(tmp_path)
    dangling = receipt_root / f"{_G7_STEM}.receipt.json"
    try:
        dangling.symlink_to("missing-target.receipt.json")
    except OSError:
        pytest.skip("symlink not supported")
    with pytest.raises(ValueError):
        g7.verify_receipt_file(
            dangling,
            archive_root=archive_root,
            receipt_root=receipt_root,
            backups_parent=parent,
            enforce_root_metadata=False,
        )


def test_symlinked_receipt_root_rejected(tmp_path: Path) -> None:
    real_root = tmp_path / "real_receipts"
    real_root.mkdir(mode=0o700)
    link_root = tmp_path / "link_receipts"
    try:
        link_root.symlink_to(real_root)
    except OSError:
        pytest.skip("symlink not supported")
    with pytest.raises(ValueError, match="symlink"):
        g7.retention_candidates(
            archive_root=tmp_path / "archives",
            receipt_root=link_root,
            backups_parent=tmp_path / "backups",
            retention_days=7,
            enforce_root_metadata=False,
        )


def test_retention_skips_wrong_filename_suffix(tmp_path: Path) -> None:
    parent, archive_root, receipt_root = _make_backup_layout(tmp_path)
    _write_valid_pair(
        archive_root=archive_root,
        receipt_root=receipt_root,
        stem=f"pgbackup-scheduled-{g7.created_at_to_filename_timestamp('2000-01-01T00:00:00Z')}-abcdef0123456789",
        created_at="2000-01-01T00:00:00Z",
    )
    wrong_name = receipt_root / "legacy-backup.receipt.json"
    arch = archive_root / "legacy.pgdump.custom"
    arch.write_bytes(b"x")
    payload = g7.build_receipt_payload(
        reason="scheduled",
        source_sha=None,
        created_at="2000-01-01T00:00:00Z",
        archive_path=str(arch),
        archive_sha256=g7.sha256_file(arch),
        archive_size_bytes=1,
        database_name="demo",
        backup_id="44444444-4444-4333-8444-555555555555",
    )
    g7.write_receipt_atomic(wrong_name, payload)
    candidates = g7.retention_candidates(
        archive_root=archive_root,
        receipt_root=receipt_root,
        backups_parent=parent,
        retention_days=7,
        now=datetime(2026, 1, 1, tzinfo=timezone.utc),
        enforce_root_metadata=False,
    )
    assert len(candidates) == 1
    assert wrong_name.exists()


def test_g7_allowlist_file_count() -> None:
    paths = [
        ".github/workflows/ci.yml",
        ".github/workflows/publish-image.yml",
        "deploy/production/README.md",
        "deploy/production/server/README.md",
        "deploy/production/server/artgents-postgres-backup.service",
        "deploy/production/server/artgents-postgres-backup.timer",
        "deploy/production/server/backup-postgres.sh",
        "deploy/production/server/backup_postgres_g7.py",
        "deploy/production/server/verify-postgres-backup.sh",
        "tests/test_g2_pr_ci_contract.py",
        "tests/test_g3_immutable_image_contract.py",
        "tests/test_g7_postgres_backup_contract.py",
    ]
    assert len(paths) == 12
    for rel in paths:
        assert (_REPO_ROOT / rel).is_file()


def test_helper_git_mode_is_executable() -> None:
    import subprocess

    out = subprocess.check_output(
        ["git", "ls-files", "-s", "deploy/production/server/backup_postgres_g7.py"],
        cwd=_REPO_ROOT,
        text=True,
    ).strip()
    assert out.startswith("100755 ")


def test_no_host_uuidgen_dependency() -> None:
    text = _backup_text()
    assert "uuidgen" not in text
    assert "new-backup-identity" in text
    assert "load_backup_identity" in text


def _assert_increasing_positions(text: str, *needles: str) -> None:
    positions = [text.find(needle) for needle in needles]
    assert all(pos != -1 for pos in positions), f"missing markers: {needles}"
    assert positions == sorted(positions), list(zip(needles, positions))


def test_backup_transactional_cleanup_state() -> None:
    text = _backup_text()
    assert "rollback_uncommitted_backup_pair" in text
    assert "safe_remove_run_artifact" in text
    assert "validate-run-artifact" in text
    assert 'rm -f "$ARCHIVE_FINAL"' not in text
    assert 'if [ "$BACKUP_COMMITTED" -eq 1 ]; then' in text
    assert text.find('mv -f "$ARCHIVE_TMP" "$ARCHIVE_FINAL"') < text.find(
        "ARCHIVE_FINAL_CREATED=1"
    )
    assert text.find('mv -f "$RECEIPT_TMP" "$RECEIPT_FINAL"') < text.find(
        "RECEIPT_FINAL_CREATED=1"
    )

    archive_seg = text.split('mv -f "$ARCHIVE_TMP" "$ARCHIVE_FINAL"', 1)[1].split(
        "RECEIPT_TMP=", 1
    )[0]
    _assert_increasing_positions(
        archive_seg,
        "ARCHIVE_FINAL_CREATED=1",
        'RUN_ARCHIVE_FINAL="$ARCHIVE_FINAL"',
        'ARCHIVE_TMP=""',
        'chmod 600 "$ARCHIVE_FINAL"',
        'fsync_path "$ARCHIVE_FINAL"',
    )

    receipt_seg = text.split('mv -f "$RECEIPT_TMP" "$RECEIPT_FINAL"', 1)[1].split(
        "cleanup_work", 1
    )[0]
    _assert_increasing_positions(
        receipt_seg,
        "RECEIPT_FINAL_CREATED=1",
        'RUN_RECEIPT_FINAL="$RECEIPT_FINAL"',
        'RECEIPT_TMP=""',
        'chmod 600 "$RECEIPT_FINAL"',
        'fsync_path "$RECEIPT_FINAL"',
        "mark_backup_committed",
    )

    committed_fn = text.split("mark_backup_committed() {", 1)[1].split("\n}", 1)[0]
    assert "BACKUP_COMMITTED=1" in committed_fn
    assert "RECEIPT_FINAL_CREATED" not in committed_fn
    assert "ARCHIVE_FINAL_CREATED" not in committed_fn


def test_pre_commit_chmod_fsync_failure_rolls_back_both_final_artifacts() -> None:
    text = _backup_text()
    receipt_seg = text.split('mv -f "$RECEIPT_TMP" "$RECEIPT_FINAL"', 1)[1].split(
        "cleanup_work", 1
    )[0]
    assert receipt_seg.find('chmod 600 "$RECEIPT_FINAL"') < receipt_seg.find(
        "mark_backup_committed"
    )
    assert receipt_seg.find('fsync_path "$RECEIPT_FINAL"') < receipt_seg.find(
        "mark_backup_committed"
    )
    rollback = text.split("rollback_uncommitted_backup_pair() {", 1)[1].split("\n}", 1)[0]
    receipt_pos = rollback.find("RECEIPT_FINAL_CREATED")
    archive_pos = rollback.find("ARCHIVE_FINAL_CREATED")
    assert receipt_pos != -1 and archive_pos != -1 and receipt_pos < archive_pos


def test_retention_failure_after_committed_does_not_rollback() -> None:
    text = _backup_text()
    block = text.split('fsync_path "$RECEIPT_FINAL"', 1)[1].split("run-retention", 1)[0]
    assert "mark_backup_committed" in block
    assert "BACKUP_COMMITTED=1" in text.split("mark_backup_committed() {", 1)[1].split("\n}", 1)[0]


def test_failure_window_receipt_write_failure_rolls_back_via_exit() -> None:
    text = _backup_text()
    write_fail = text.split("write-receipt", 1)[1].split("fail \"failed to write backup receipt\"", 1)[0]
    assert "ARCHIVE_FINAL_CREATED=1" in text.split("write-receipt", 1)[0]
    assert 'rm -f "$ARCHIVE_FINAL"' not in write_fail


def test_failure_window_archive_without_receipt_uses_rollback() -> None:
    text = _backup_text()
    rollback = text.split("rollback_uncommitted_backup_pair() {", 1)[1].split("\n}", 1)[0]
    assert "ARCHIVE_FINAL_CREATED" in rollback
    assert "RUN_ARCHIVE_FINAL" in rollback


def test_generate_backup_identity_contract() -> None:
    backup_id, suffix = g7.generate_backup_identity()
    g7.validate_backup_id(backup_id)
    assert len(suffix) == 16
    assert re.fullmatch(r"[0-9a-f]{16}", suffix)


def test_pair_basename_mismatch_rejected(tmp_path: Path) -> None:
    parent, archive_root, receipt_root = _make_backup_layout(tmp_path)
    stem_b = "pgbackup-scheduled-2026-01-02T030405Z-bbbbbbbbbbbbbbbb"
    _, receipt = _write_valid_pair(
        archive_root=archive_root,
        receipt_root=receipt_root,
        stem=_G7_STEM,
        created_at="2026-01-02T03:04:05Z",
    )
    wrong_archive = archive_root / f"{stem_b}.pgdump.custom"
    wrong_archive.write_bytes(b"custom-format-bytes")
    data = json.loads(receipt.read_text(encoding="utf-8"))
    data["archive_path"] = str(wrong_archive)
    receipt.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="basename mismatch"):
        g7.verify_receipt_file(
            receipt,
            archive_root=archive_root,
            receipt_root=receipt_root,
            backups_parent=parent,
            enforce_root_metadata=False,
        )


def test_pair_filename_reason_mismatch_rejected(tmp_path: Path) -> None:
    parent, archive_root, receipt_root = _make_backup_layout(tmp_path)
    stem = "pgbackup-pre-deploy-2026-01-02T030405Z-abcdef0123456789"
    _write_valid_pair(
        archive_root=archive_root,
        receipt_root=receipt_root,
        stem=stem,
        created_at="2026-01-02T03:04:05Z",
        backup_id="66666666-6666-4666-8666-666666666666",
    )
    receipt = receipt_root / f"{stem}.receipt.json"
    data = json.loads(receipt.read_text(encoding="utf-8"))
    data["reason"] = "scheduled"
    data["source_sha"] = None
    receipt.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="reason mismatch"):
        g7.verify_receipt_file(
            receipt,
            archive_root=archive_root,
            receipt_root=receipt_root,
            backups_parent=parent,
            enforce_root_metadata=False,
        )


def test_pair_filename_timestamp_mismatch_rejected(tmp_path: Path) -> None:
    parent, archive_root, receipt_root = _make_backup_layout(tmp_path)
    receipt = receipt_root / f"{_G7_STEM}.receipt.json"
    archive = archive_root / f"{_G7_STEM}.pgdump.custom"
    archive.write_bytes(b"custom-format-bytes")
    payload = g7.build_receipt_payload(
        reason="scheduled",
        source_sha=None,
        created_at="2026-01-03T03:04:05Z",
        archive_path=str(archive),
        archive_sha256=g7.sha256_file(archive),
        archive_size_bytes=archive.stat().st_size,
        database_name="demo",
        backup_id=_G7_BACKUP_ID,
    )
    g7.write_receipt_atomic(receipt, payload)
    with pytest.raises(ValueError, match="timestamp mismatch"):
        g7.verify_receipt_file(
            receipt,
            archive_root=archive_root,
            receipt_root=receipt_root,
            backups_parent=parent,
            enforce_root_metadata=False,
        )


def test_validate_run_artifact_rejects_outside_root(tmp_path: Path) -> None:
    root = tmp_path / "archives"
    root.mkdir(mode=0o700)
    outside = tmp_path / "outside.pgdump.custom"
    outside.write_bytes(b"x")
    with pytest.raises(ValueError):
        g7.validate_run_artifact_path(outside, root, "archive")
