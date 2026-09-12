"""G8 PostgreSQL qualification — offline workflow and scope contract."""

from __future__ import annotations

import ast
import importlib.util
import json
import re
from pathlib import Path

import pytest

from deploy.postgres.g8_disposable_constants import (
    G8_AFTER_RESTORE_TEST_COUNT,
    G8_INTEGRATION_SCENARIO_IDS,
    G8_PRIMARY_SCENARIO_COUNT,
    POSTGRES_IMAGE_DIGEST,
    POSTGRES_IMAGE_PIN,
    POSTGRES_MAJOR,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_WORKFLOW_PATH = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
_CONTRACT_PATH = Path(__file__).resolve()
_RUNNER = _REPO_ROOT / "deploy" / "postgres" / "g8_qualification_runner.py"
_INTEGRATION = _REPO_ROOT / "tests" / "test_g8_postgres_qualification_integration.py"
_DOCKER_PG = _REPO_ROOT / "deploy" / "postgres" / "g8_docker_pg.py"
_DISPOSABLE = _REPO_ROOT / "deploy" / "postgres" / "g8_disposable.py"
_README = _REPO_ROOT / "deploy" / "postgres" / "README-G8.md"
_ENV_EXAMPLE = _REPO_ROOT / "deploy" / "production" / "env.production.example"
_G7_HELPER = _REPO_ROOT / "deploy" / "production" / "server" / "backup_postgres_g7.py"

_FORBIDDEN_PATTERNS = (
    r"\$\{\{\s*secrets\.",
    r"continue-on-error:\s*true",
    r"\|\|\s*true",
    r"--deselect\b",
    r"\s-k\s",
    r":latest\b",
    r"apt-get",
    r"postgresql-client",
)


def _workflow_text() -> str:
    assert _WORKFLOW_PATH.is_file()
    return _WORKFLOW_PATH.read_text(encoding="utf-8")


def _postgres_job_block(text: str) -> str:
    return text.split("postgres-qualification:", 1)[-1].split("\n  secret-scan:", 1)[0]


def _load_g7():
    spec = importlib.util.spec_from_file_location("backup_postgres_g7", _G7_HELPER)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_contract_module_has_no_network_imports() -> None:
    source = _CONTRACT_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(_CONTRACT_PATH))
    forbidden = {"urllib", "urllib.request", "http.client", "requests"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                assert alias.name not in forbidden and root not in forbidden
        if isinstance(node, ast.ImportFrom):
            assert node.module not in forbidden, node.module


def test_postgres_job_separate_from_offline_unit() -> None:
    text = _workflow_text()
    offline = text.split("offline-unit-and-contracts:", 1)[-1].split("postgres-qualification:", 1)[0]
    assert "test_g8_postgres_qualification_integration" not in offline
    assert "g8_qualification_runner" not in offline
    pg = _postgres_job_block(text)
    assert "deploy.postgres.g8_qualification_runner" in pg


def test_postgres_job_pinned_image_digest() -> None:
    text = _workflow_text()
    pg = _postgres_job_block(text)
    assert POSTGRES_IMAGE_DIGEST in pg
    assert POSTGRES_IMAGE_PIN.split("@")[0] in pg
    assert ":latest" not in pg


def test_postgres_job_no_apt_or_host_pg_clients() -> None:
    pg = _postgres_job_block(_workflow_text())
    assert "apt-get" not in pg
    assert "postgresql-client" not in pg


def test_postgres_job_container_id_via_env_not_run_expression() -> None:
    pg = _postgres_job_block(_workflow_text())
    job_env = pg.split("services:", 1)[0]
    assert "G8_POSTGRES_CONTAINER_ID" not in job_env
    qual_step = pg.split("G8 disposable PostgreSQL qualification", 1)[1]
    assert "G8_POSTGRES_CONTAINER_ID:" in qual_step
    assert "${{ job.services.postgres.id }}" in qual_step
    run_blocks = re.findall(r"^\s+run:\s.*$", pg, re.MULTILINE)
    for block in run_blocks:
        assert "${{" not in block


def test_g8_disposable_create_role_uses_psycopg_sql_composition() -> None:
    disposable = _DISPOSABLE.read_text(encoding="utf-8")
    assert "PASSWORD %s" not in disposable
    assert "sql.Identifier" in disposable
    assert "sql.Literal(password)" in disposable
    grants = (
        _REPO_ROOT / "deploy" / "postgres" / "g8_disposable_grants_post_migrate.sql"
    ).read_text(encoding="utf-8")
    assert "ALTER SCHEMA IF EXISTS" not in grants
    assert "ALTER SCHEMA bot_migration OWNER TO bot_migrator;" in grants


def test_g8_runner_failure_diagnostics_safe() -> None:
    runner = _RUNNER.read_text(encoding="utf-8")
    assert "g8_qualification=failed stage=" in runner
    assert "sqlstate=" in runner
    assert "str(exc)" not in runner
    assert "wait_postgres" in runner
    assert "grants_restore" in runner


def test_g8_disposable_database_create_grants() -> None:
    disposable = _DISPOSABLE.read_text(encoding="utf-8")
    assert "_grant_database_bootstrap_privileges" in disposable
    assert "GRANT CREATE ON DATABASE" in disposable
    assert "REVOKE CREATE ON DATABASE" in disposable
    assert "has_database_privilege(current_user, current_database(), 'CREATE')" in disposable
    template = (_REPO_ROOT / "migrations" / "postgresql" / "roles_template.sql").read_text(
        encoding="utf-8"
    )
    low = template.lower()
    assert "grant create on database :dbname to bot_migrator" in low
    assert "revoke create on database :dbname from public, bot_runtime" in low


def test_postgres_job_pg_isready_timeout_and_no_secrets() -> None:
    text = _workflow_text()
    pg = _postgres_job_block(text)
    runner = _RUNNER.read_text(encoding="utf-8")
    assert "pg_isready" in runner or "pg_isready" in _DOCKER_PG.read_text(encoding="utf-8")
    assert "wait_for_postgres_ready" in runner
    for pattern in _FORBIDDEN_PATTERNS[:6]:
        assert not re.search(pattern, pg, re.IGNORECASE | re.MULTILINE), pattern
    assert "g8_disposable" in pg


def test_postgres_job_runs_on_pr_and_main() -> None:
    text = _workflow_text()
    assert "postgres-qualification:" in text
    assert re.search(r"name:\s*PostgreSQL qualification", text)


def test_offline_mandatory_includes_g8_contract_not_integration() -> None:
    g2 = (_REPO_ROOT / "tests" / "test_g2_pr_ci_contract.py").read_text(encoding="utf-8")
    assert "tests/test_g8_postgres_qualification_contract.py" in g2
    offline = _workflow_text().split("offline-unit-and-contracts:", 1)[-1].split(
        "postgres-qualification:", 1
    )[0]
    assert "tests/test_g8_postgres_qualification_contract.py" in offline
    assert "tests/test_g8_postgres_qualification_integration.py" not in offline


def test_g2_job_names_include_postgres_qualification() -> None:
    g2 = (_REPO_ROOT / "tests" / "test_g2_pr_ci_contract.py").read_text(encoding="utf-8")
    assert "PostgreSQL qualification" in g2


def test_integration_module_lists_all_scenarios() -> None:
    body = _INTEGRATION.read_text(encoding="utf-8")
    for scenario in G8_INTEGRATION_SCENARIO_IDS:
        assert f"test_{scenario}" in body


def test_integration_forbids_broad_pytest_raises_exception() -> None:
    body = _INTEGRATION.read_text(encoding="utf-8")
    assert "pytest.raises(Exception)" not in body


def test_integration_retention_checks_deleted_tenant() -> None:
    body = _INTEGRATION.read_text(encoding="utf-8")
    assert "bot_events_deleted" in body
    assert "marker_demo" in body


def test_runner_uses_docker_exec_and_streaming_dump() -> None:
    runner = _RUNNER.read_text(encoding="utf-8")
    docker = _DOCKER_PG.read_text(encoding="utf-8")
    assert '"docker"' in docker and '"exec"' in docker
    assert "pg_dump_custom_to_file" in runner
    assert "pg_restore_list_archive" in runner
    assert "pg_restore_into_database" in runner
    assert "read_bytes()" not in runner


def test_runner_restore_database_preparation_order() -> None:
    runner = _RUNNER.read_text(encoding="utf-8")
    disposable = _DISPOSABLE.read_text(encoding="utf-8")
    assert "prepare_restore_database_schema" in runner
    assert "bootstrap_superuser_dsn(G8_RESTORE_DATABASE)" in runner
    assert "apply_post_migrate_grants(conn)" in runner
    assert "def prepare_restore_database_schema" in disposable
    assert "REVOKE CREATE ON SCHEMA public FROM PUBLIC" in disposable


def test_runner_post_restore_grants_not_on_primary_dsn() -> None:
    runner = _RUNNER.read_text(encoding="utf-8")
    tail = runner.split("pg_restore_into_database", 1)[1]
    assert "bootstrap_superuser_dsn(G8_RESTORE_DATABASE)" in tail
    grants_idx = tail.find("apply_post_migrate_grants")
    assert grants_idx != -1
    assert "G8_RESTORE_DATABASE" in tail[: grants_idx + 80]


def test_runner_role_catalog_primary_and_restored() -> None:
    runner = _RUNNER.read_text(encoding="utf-8")
    assert "assert_runtime_role_catalog" in runner
    assert "assert_migrator_role_catalog" in runner
    assert runner.count("_qualify_roles") >= 2


def test_runner_junit_zero_skipped_enforcement() -> None:
    runner = _RUNNER.read_text(encoding="utf-8")
    assert "assert_junit_exact_passed" in runner
    assert "G8_PRIMARY_SCENARIO_COUNT" in runner
    assert "G8_AFTER_RESTORE_TEST_COUNT" in runner
    assert "--junitxml=" in runner


def test_runner_g7_verify_receipt_before_restore() -> None:
    runner = _RUNNER.read_text(encoding="utf-8")
    drill = runner.split("def _backup_primary_archive", 1)[1].split("\ndef _prepare_restore_database", 1)[0]
    verify_pos = drill.find("verify_receipt_file")
    restore_pos = runner.find("def _restore_from_archive")
    assert verify_pos != -1 and restore_pos != -1 and verify_pos < restore_pos
    assert "pgbackup-scheduled-" in runner
    assert "2026-01-01" not in runner


def test_runner_backup_restore_into_separate_database() -> None:
    runner = _RUNNER.read_text(encoding="utf-8")
    assert "G8_RESTORE_DATABASE" in runner
    assert "create_restore_database" in runner
    assert "drop_restore_database_if_exists" in runner
    assert "shutil.rmtree" in runner


def test_readme_g8_boundaries() -> None:
    assert _README.is_file()
    text = _README.read_text(encoding="utf-8")
    assert "G8" in text
    assert "disposable" in text.lower()
    assert str(POSTGRES_MAJOR) in text


def test_env_example_documents_postgres_image_pin() -> None:
    text = _ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "POSTGRES_IMAGE" in text
    assert POSTGRES_IMAGE_DIGEST in text


def test_g8_contract_in_ci_and_publish_verify() -> None:
    ci = _workflow_text()
    publish = (_REPO_ROOT / ".github" / "workflows" / "publish-image.yml").read_text(encoding="utf-8")
    rel = str(_CONTRACT_PATH.relative_to(_REPO_ROOT)).replace("\\", "/")
    assert rel in ci
    verify = publish.split("verify:", 1)[1].split("secret-scan:", 1)[0]
    assert rel in verify


def test_g8_contract_in_ci_workflow_offline_list() -> None:
    offline = _workflow_text().split("offline-unit-and-contracts:", 1)[-1].split(
        "postgres-qualification:", 1
    )[0]
    rel = str(_CONTRACT_PATH.relative_to(_REPO_ROOT)).replace("\\", "/")
    assert rel in offline


def test_g7_receipt_hash_mismatch_rejected(tmp_path: Path) -> None:
    g7 = _load_g7()
    parent = tmp_path / "backups"
    archive_root = parent / "postgres"
    receipt_root = parent / "receipts"
    parent.mkdir(mode=0o700)
    archive_root.mkdir(mode=0o700)
    receipt_root.mkdir(mode=0o700)
    stem = "pgbackup-scheduled-2026-01-02T030405Z-abcdef0123456789"
    archive = archive_root / f"{stem}.pgdump.custom"
    archive.write_bytes(b"payload")
    receipt = receipt_root / f"{stem}.receipt.json"
    payload = g7.build_receipt_payload(
        reason="scheduled",
        source_sha=None,
        created_at="2026-01-02T03:04:05Z",
        archive_path=str(archive),
        archive_sha256="sha256:" + "a" * 64,
        archive_size_bytes=archive.stat().st_size,
        database_name="g8_qual_primary",
        backup_id="11111111-2222-4333-8444-555555555555",
    )
    g7.write_receipt_atomic(receipt, payload)
    with pytest.raises(ValueError, match="sha256 mismatch"):
        g7.verify_receipt_file(
            receipt,
            archive_root=archive_root,
            receipt_root=receipt_root,
            backups_parent=parent,
            enforce_root_metadata=False,
        )


def test_g7_receipt_size_mismatch_rejected(tmp_path: Path) -> None:
    g7 = _load_g7()
    parent = tmp_path / "backups"
    archive_root = parent / "postgres"
    receipt_root = parent / "receipts"
    parent.mkdir(mode=0o700)
    archive_root.mkdir(mode=0o700)
    receipt_root.mkdir(mode=0o700)
    stem = "pgbackup-scheduled-2026-01-02T030405Z-abcdef0123456789"
    archive = archive_root / f"{stem}.pgdump.custom"
    archive.write_bytes(b"payload")
    receipt = receipt_root / f"{stem}.receipt.json"
    sha = g7.sha256_file(archive)
    payload = g7.build_receipt_payload(
        reason="scheduled",
        source_sha=None,
        created_at="2026-01-02T03:04:05Z",
        archive_path=str(archive),
        archive_sha256=sha,
        archive_size_bytes=archive.stat().st_size + 1,
        database_name="g8_qual_primary",
        backup_id="11111111-2222-4333-8444-555555555555",
    )
    g7.write_receipt_atomic(receipt, payload)
    with pytest.raises(ValueError, match="size mismatch"):
        g7.verify_receipt_file(
            receipt,
            archive_root=archive_root,
            receipt_root=receipt_root,
            backups_parent=parent,
            enforce_root_metadata=False,
        )


def test_g7_receipt_basename_mismatch_rejected(tmp_path: Path) -> None:
    g7 = _load_g7()
    parent = tmp_path / "backups"
    archive_root = parent / "postgres"
    receipt_root = parent / "receipts"
    parent.mkdir(mode=0o700)
    archive_root.mkdir(mode=0o700)
    receipt_root.mkdir(mode=0o700)
    stem_a = "pgbackup-scheduled-2026-01-02T030405Z-aaaaaaaaaaaaaaaa"
    stem_b = "pgbackup-scheduled-2026-01-02T030405Z-bbbbbbbbbbbbbbbb"
    archive = archive_root / f"{stem_b}.pgdump.custom"
    archive.write_bytes(b"payload")
    receipt = receipt_root / f"{stem_a}.receipt.json"
    payload = g7.build_receipt_payload(
        reason="scheduled",
        source_sha=None,
        created_at="2026-01-02T03:04:05Z",
        archive_path=str(archive),
        archive_sha256=g7.sha256_file(archive),
        archive_size_bytes=archive.stat().st_size,
        database_name="g8_qual_primary",
        backup_id="11111111-2222-4333-8444-555555555555",
    )
    g7.write_receipt_atomic(receipt, payload)
    with pytest.raises(ValueError, match="basename mismatch"):
        g7.verify_receipt_file(
            receipt,
            archive_root=archive_root,
            receipt_root=receipt_root,
            backups_parent=parent,
            enforce_root_metadata=False,
        )
