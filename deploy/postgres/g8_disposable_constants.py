"""G8 disposable PostgreSQL qualification — static CI-only values (not production secrets)."""

from __future__ import annotations

# Same major as production (T6B / compose examples use PostgreSQL 16).
POSTGRES_MAJOR = 16
POSTGRES_IMAGE_REPO = "postgres:16.8-bookworm"
POSTGRES_IMAGE_DIGEST = (
    "sha256:e75c0253ec375a157657c75bbb1705a8bbdd844d5f258973f9e3eb33cfcd9e33"
)
POSTGRES_IMAGE_PIN = f"{POSTGRES_IMAGE_REPO}@{POSTGRES_IMAGE_DIGEST}"

# GitHub Actions service / runner-local disposable cluster only.
G8_BOOTSTRAP_USER = "g8_bootstrap"
G8_BOOTSTRAP_PASSWORD = "g8_disposable_bootstrap_ci_only"
G8_PRIMARY_DATABASE = "g8_qual_primary"
G8_RESTORE_DATABASE = "g8_qual_restored"

G8_MIGRATOR_ROLE = "bot_migrator"
G8_RUNTIME_ROLE = "bot_runtime"
G8_MIGRATOR_PASSWORD = "g8_disposable_migrator_ci_only"
G8_RUNTIME_PASSWORD = "g8_disposable_runtime_ci_only"

G8_PG_HOST = "127.0.0.1"
G8_PG_PORT = 5432

PG_ISREADY_TIMEOUT_SEC = 60
PG_ISREADY_INTERVAL_SEC = 2

G8_PRIMARY_SCENARIO_COUNT = 14
G8_AFTER_RESTORE_TEST_COUNT = 6

G8_INTEGRATION_SCENARIO_IDS: tuple[str, ...] = (
    "scenario_01_tenant_a_writes",
    "scenario_02_tenant_b_writes",
    "scenario_03_tenant_a_cannot_read_b",
    "scenario_04_tenant_b_cannot_read_a",
    "scenario_05_runtime_without_tenant_reads_zero",
    "scenario_06_tenant_context_substitution_blocked",
    "scenario_07_connection_reuse_clears_tenant_context",
    "scenario_08_rollback_clears_tenant_context",
    "scenario_09_runtime_cannot_disable_rls",
    "scenario_10_runtime_cannot_execute_ddl",
    "scenario_11_runtime_cannot_read_migration_ledger",
    "scenario_12_migrator_can_apply_migration",
    "scenario_13_retention_limited_to_current_tenant",
    "scenario_14_invalid_unknown_tenant_fail_closed",
)
