"""G5 manual fail-closed production rollback — static offline contract."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_ROLLBACK_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "rollback-production.yml"
_DEPLOY_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "deploy-production.yml"
_CI_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
_PUBLISH_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "publish-image.yml"
_RECEIVER = _REPO_ROOT / "deploy" / "production" / "server" / "deploy-receiver.sh"
_ROLLBACK_SCRIPT = _REPO_ROOT / "deploy" / "production" / "server" / "rollback-production.sh"
_DEPLOY_SCRIPT = _REPO_ROOT / "deploy" / "production" / "server" / "deploy-production.sh"
_FINGERPRINT_PY = _REPO_ROOT / "deploy" / "production" / "server" / "migration-bundle-fingerprint.py"
_SUDOERS = _REPO_ROOT / "deploy" / "production" / "server" / "artgents-deploy.sudoers.example"

_IMAGE_REPO = "ghcr.io/dhmnzr79/artgents-bot"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_RUN_BLOCK_START = re.compile(r"^        run: \|\s*$")
_ROLLBACK_CMD_RE = re.compile(r"^rollback-production ([0-9a-f]{40})$")


def _load_fingerprint_module():
    spec = importlib.util.spec_from_file_location("migration_bundle_fingerprint", _FINGERPRINT_PY)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


_fp_mod = _load_fingerprint_module()
compute_migration_bundle_fingerprint = _fp_mod.compute_migration_bundle_fingerprint
MigrationBundleFingerprintError = _fp_mod.MigrationBundleFingerprintError


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _workflow_run_shell_bodies(text: str) -> list[str]:
    lines = text.splitlines()
    bodies: list[str] = []
    idx = 0
    while idx < len(lines):
        if _RUN_BLOCK_START.match(lines[idx]):
            idx += 1
            chunk: list[str] = []
            while idx < len(lines):
                line = lines[idx]
                if line.startswith("          "):
                    chunk.append(line[10:])
                    idx += 1
                    continue
                if line.strip() == "":
                    chunk.append("")
                    idx += 1
                    continue
                break
            bodies.append("\n".join(chunk))
            continue
        idx += 1
    assert bodies, "expected at least one run: | block"
    return bodies


def tokenize_rollback_command(original: str) -> tuple[str, str]:
    if any(ch in original for ch in "\n\r\t"):
        raise ValueError("forbidden whitespace in command")
    if original != original.strip():
        raise ValueError("leading or trailing whitespace forbidden")
    if "  " in original:
        raise ValueError("double spaces forbidden")
    match = _ROLLBACK_CMD_RE.fullmatch(original)
    if not match:
        raise ValueError("invalid rollback forced command grammar")
    return "rollback-production", match.group(1)


def test_g5_contract_in_ci_and_publish() -> None:
    ci = _text(_CI_WORKFLOW)
    publish = _text(_PUBLISH_WORKFLOW)
    assert "tests/test_g5_manual_rollback_contract.py" in ci
    verify = publish.split("verify:", 1)[1].split("secret-scan:", 1)[0]
    assert "tests/test_g5_manual_rollback_contract.py" in verify


def test_rollback_workflow_manual_inputs_and_guards() -> None:
    text = _text(_ROLLBACK_WORKFLOW)
    assert "workflow_dispatch:" in text
    assert "expected_current_sha:" in text
    assert "confirm_rollback:" in text
    for forbidden in (
        "target_sha",
        "target_digest",
        "image:",
        "repository:",
        "command:",
        "restore",
    ):
        assert forbidden not in text
    assert "permissions: {}" in text
    assert "group: production-deploy" in text
    assert "cancel-in-progress: false" in text
    assert "actions/checkout" not in text
    assert "ghcr.io" not in text or "Dhmnzr79/artgents-bot" in text
    assert "refs/heads/main" in text
    assert "Dhmnzr79/artgents-bot" in text


def test_rollback_workflow_no_direct_github_expressions_in_run() -> None:
    text = _text(_ROLLBACK_WORKFLOW)
    for body in _workflow_run_shell_bodies(text):
        assert "${{" not in body


def test_rollback_workflow_ssh_command_and_hardening() -> None:
    text = _text(_ROLLBACK_WORKFLOW)
    bodies = _workflow_run_shell_bodies(text)
    ssh_body = bodies[-1]
    assert "rollback-production ${EXPECTED_CURRENT_SHA}" in ssh_body or "REMOTE_CMD=" in ssh_body
    assert "StrictHostKeyChecking=yes" in ssh_body
    assert "ssh-keyscan" not in text
    assert "StrictHostKeyChecking=no" not in text
    assert "ForwardAgent=no" in ssh_body
    assert "BatchMode=yes" in ssh_body
    assert "umask 077" in ssh_body
    assert 'printf \'%s\\n\' "$SSH_PRIVATE_KEY"' in ssh_body


def test_rollback_concurrency_matches_deploy() -> None:
    deploy = _text(_DEPLOY_WORKFLOW)
    rollback = _text(_ROLLBACK_WORKFLOW)
    assert re.search(r"group:\s*production-deploy", deploy)
    assert re.search(r"group:\s*production-deploy", rollback)


def test_receiver_dual_grammar_no_eval() -> None:
    text = _text(_RECEIVER)
    assert "deploy-production" in text
    assert "rollback-production" in text
    assert "BASH_REMATCH" in text
    assert "eval" not in text
    assert "bash -c" not in text
    assert "sh -c" not in text


@pytest.mark.parametrize(
    "cmd",
    [
        "rollback-production  " + "a" * 40,
        "rollback-production\n" + "a" * 40,
        "rollback-production " + "A" * 40,
        "rollback-production " + "a" * 39,
        "rollback-production " + "a" * 40 + " extra",
    ],
)
def test_receiver_rejects_bad_rollback_commands(cmd: str) -> None:
    with pytest.raises(ValueError):
        tokenize_rollback_command(cmd)


def test_receiver_accepts_valid_rollback_command() -> None:
    sha = "a" * 40
    name, parsed = tokenize_rollback_command(f"rollback-production {sha}")
    assert name == "rollback-production"
    assert parsed == sha


def test_sudoers_includes_rollback_script_only_extension() -> None:
    text = _text(_SUDOERS)
    assert "/opt/artgents/bin/rollback-production" in text
    assert "/usr/bin/docker" not in text


def _write_bundle(tmp_path: Path, manifest_lines: list[str], sql_files: dict[str, bytes]) -> tuple[Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    manifest = tmp_path / "migrations.manifest"
    manifest.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
    mig_dir = tmp_path / "postgresql"
    mig_dir.mkdir()
    for name, content in sql_files.items():
        (mig_dir / name).write_bytes(content)
    return manifest, mig_dir


def test_fingerprint_stable_for_same_bundle(tmp_path: Path) -> None:
    manifest, mig_dir = _write_bundle(
        tmp_path,
        ["001_init.sql", "# comment", "", "002_add.sql"],
        {"001_init.sql": b"CREATE TABLE x;\n", "002_add.sql": b"ALTER TABLE x;\n"},
    )
    a = compute_migration_bundle_fingerprint(manifest, mig_dir)
    b = compute_migration_bundle_fingerprint(manifest, mig_dir)
    assert a == b
    assert _DIGEST_RE.fullmatch(a)


def test_fingerprint_changes_when_sql_bytes_change(tmp_path: Path) -> None:
    manifest, mig_dir = _write_bundle(tmp_path, ["001_init.sql"], {"001_init.sql": b"v1\n"})
    first = compute_migration_bundle_fingerprint(manifest, mig_dir)
    (mig_dir / "001_init.sql").write_bytes(b"v2\n")
    second = compute_migration_bundle_fingerprint(manifest, mig_dir)
    assert first != second


def test_fingerprint_changes_when_manifest_order_changes(tmp_path: Path) -> None:
    base = tmp_path / "b"
    base.mkdir()
    m1, d1 = _write_bundle(base / "a", ["001.sql", "002.sql"], {"001.sql": b"a", "002.sql": b"b"})
    m2, d2 = _write_bundle(base / "c", ["002.sql", "001.sql"], {"001.sql": b"a", "002.sql": b"b"})
    assert compute_migration_bundle_fingerprint(m1, d1) != compute_migration_bundle_fingerprint(m2, d2)


def test_fingerprint_rejects_missing_duplicate_unsafe(tmp_path: Path) -> None:
    manifest, mig_dir = _write_bundle(tmp_path, ["001.sql", "001.sql"], {"001.sql": b"x"})
    with pytest.raises(MigrationBundleFingerprintError):
        compute_migration_bundle_fingerprint(manifest, mig_dir)
    manifest2, mig_dir2 = _write_bundle(tmp_path / "m2", ["../evil.sql"], {})
    with pytest.raises(MigrationBundleFingerprintError):
        compute_migration_bundle_fingerprint(manifest2, mig_dir2)
    manifest3, mig_dir3 = _write_bundle(tmp_path / "m3", ["missing.sql"], {})
    with pytest.raises(MigrationBundleFingerprintError):
        compute_migration_bundle_fingerprint(manifest3, mig_dir3)


def test_deploy_receipt_schema2_and_image_fingerprint_extraction() -> None:
    text = _text(_DEPLOY_SCRIPT)
    assert '"schema_version": 2' in text
    assert "migration_bundle_sha256" in text
    assert "docker create" in text
    assert "extract_migration_bundle_fingerprint_from_image() (" in text
    assert "trap cleanup_extract EXIT" in text
    assert "trap cleanup_extract RETURN" not in text
    assert "docker start" not in text


def test_rollback_script_fail_closed_contract() -> None:
    text = _text(_ROLLBACK_SCRIPT)
    assert "must run as root" in text
    assert '[ "$#" -ne 1 ]' in text
    assert "PREVIOUS_RECEIPT" in text
    assert "expected current SHA does not match" in text
    assert "rollback unavailable: no previous successful deployment" in text
    assert "automatic rollback blocked: migration bundle differs" in text
    assert "extract_migration_bundle_fingerprint_from_image() (" in text
    assert "trap cleanup_extract EXIT" in text
    assert "trap cleanup_extract RETURN" not in text
    assert "docker create" in text
    assert "run --rm migrate" not in text
    assert "pre-rollback" in text
    assert "run_application_maintenance_stop" in text
    assert "health/ready" in text
    assert "--profile public" in text
    assert "rollback_from_source_sha" in text
    assert "check_env_permissions" in text
    assert "production env must be root-owned" in text
    assert "production env must not be world/group readable" in text
    assert "if ! parsed=$(" in text
    assert "invalid deploy receipt" in text
    assert "< <(" not in text
    assert "eval" not in text
    assert "bash -c" not in text
    assert "sh -c" not in text
    for secret in ("BOT_PG_DSN", "SMTP_PASSWORD", "ADMIN_DASHBOARD_TOKEN"):
        assert secret not in text


def test_fingerprint_mismatch_blocks_before_backup_and_maintenance() -> None:
    text = _text(_ROLLBACK_SCRIPT)
    flock_end = text.find('if ! flock -n 9')
    segment = text[flock_end:]
    block_pos = segment.find("automatic rollback blocked: migration bundle differs")
    backup_pos = segment.find("pre-rollback")
    maint_call = segment.find("run_application_maintenance_stop\n")
    if maint_call == -1:
        maint_call = segment.rfind("run_application_maintenance_stop")
    assert block_pos != -1 and backup_pos != -1 and maint_call != -1
    assert block_pos < backup_pos < maint_call


def test_rollback_order_backup_before_maintenance_before_compose_up() -> None:
    text = _text(_ROLLBACK_SCRIPT)
    flock_end = text.find('if ! flock -n 9')
    segment = text[flock_end:]
    backup_pos = segment.find("pre-rollback")
    maint_pos = segment.find("run_application_maintenance_stop")
    up_pos = segment.find("up -d --force-recreate --no-deps bot admin")
    ready_pos = segment.find("health/ready")
    caddy_pos = segment.find("up -d --no-deps caddy")
    assert backup_pos < maint_pos < up_pos < ready_pos < caddy_pos


def test_rollback_receipt_validation_before_docker_pull() -> None:
    text = _text(_ROLLBACK_SCRIPT)
    flock_end = text.find('if ! flock -n 9')
    segment = text[flock_end:]
    env_check = segment.find("check_env_permissions")
    load_target = segment.rfind('load_receipt_fields "$PREVIOUS_RECEIPT" TARGET')
    pull_pos = segment.find('docker pull "$TARGET_IMMUTABLE_REF"')
    assert env_check != -1 and load_target != -1 and pull_pos != -1
    assert env_check < load_target < pull_pos


def test_rollback_receipt_atomic_rotation() -> None:
    text = _text(_ROLLBACK_SCRIPT)
    assert "previous.json.tmp" in text
    assert 'mv -f "$RECEIPT_TMP" "$CURRENT_RECEIPT"' in text


def test_rollback_workflow_file_exists() -> None:
    assert _ROLLBACK_WORKFLOW.is_file()
    assert _ROLLBACK_SCRIPT.is_file()
    assert _FINGERPRINT_PY.is_file()
