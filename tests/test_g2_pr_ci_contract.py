"""G2 PR CI workflow contract — regressions fail without editing product code."""

from __future__ import annotations

import ast
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_WORKFLOW_PATH = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
_CONTRACT_PATH = Path(__file__).resolve()

_CHECKOUT_SHA = "d23441a48e516b6c34aea4fa41551a30e30af803"
_SETUP_PYTHON_SHA = "ece7cb06caefa5fff74198d8649806c4678c61a1"
_GITLEAKS_SHA = "e0c47f4f8be36e29cdc102c57e68cb5cbf0e8d1e"
_GITLEAKS_DEFAULT_VERSION = "8.24.3"

_SHA_USES_RE = re.compile(
    r"^\s*-\s*uses:\s*([^\s@]+)@([0-9a-f]{40})\b",
    re.IGNORECASE | re.MULTILINE,
)

_FORBIDDEN_SECRET_PATTERNS = (
    r"\$\{\{\s*secrets\.",
    r"^\s*DASHSCOPE_API_KEY:",
    r"^\s*SMTP_PASSWORD:",
    r"^\s*SMTP_USER:",
    r"^\s*BOT_PG_DSN:",
    r"^\s*BOT_MIGRATOR_PG_DSN:",
    r"^\s*BOT_TEST_PG_DSN:",
    r"^\s*ADMIN_DASHBOARD_TOKEN:",
    r"SSH_PRIVATE_KEY",
    r"pull_request_target",
    r"continue-on-error:\s*true",
)

_FORBIDDEN_DEPLOY_PATTERNS = (
    r"docker\s+push",
    r"ghcr\.io",
    r"workflow_call:",
    r"\benvironment:\s*production\b",
    r"uses:\s*docker/",
)

_MANDATORY_OFFLINE_MODULES = (
    "tests/test_g2_pr_ci_contract.py",
    "tests/test_g4_manual_deploy_contract.py",
    "tests/test_turn_planner_llm.py",
    "tests/test_turn_planner_wiring.py",
    "tests/test_tenant_resource_isolation_offline.py",
    "tests/test_one_call_tenant_isolation_offline.py",
    "tests/test_tenant_ingress_prod_boundary_offline.py",
    "tests/test_session_tenant_binding_hardening_offline.py",
    "tests/test_tenant_lead_routing_context_offline.py",
    "tests/test_tenant_lead_pending_question_offline.py",
    "tests/test_pg_tenant_context_offline.py",
    "tests/test_pg_tenant_write_contract_offline.py",
    "tests/test_pg_schema_readiness_offline.py",
    "tests/test_pg_sink_tenant_worker_offline.py",
    "tests/test_pg_sink_connection_reuse_offline.py",
    "tests/test_pg_retention_non_admin_tenant_offline.py",
    "tests/test_pg_retention_trusted_registry_offline.py",
    "tests/test_user_text_privacy_contract_offline.py",
    "tests/test_leads_pg_no_pii_offline.py",
    "tests/test_observability_pii.py",
    "tests/test_admin_dashboard_tenant_offline.py",
    "tests/test_admin_dashboard_schema_health_offline.py",
    "tests/test_t6b_pass1_health_runtime_offline.py",
    "tests/test_t6b_pass2_postgres_migrate_offline.py",
    "tests/test_t6b_pass3_production_deploy_offline.py",
    "tests/test_migrations_postgresql_static.py",
    "tests/test_migration_002_constraint_drift.py",
    "tests/test_validate_client_pack.py",
    "tests/test_composer_live_eval.py",
)

_EXCLUDED_INTEGRATION = "tests/test_pg_tenant_rls_integration.py"

_REQUIRED_JOB_NAMES = (
    "Lint and validate",
    "Offline unit and contracts",
    "Secret scan",
)

_PYTEST_DESELECT_FORBIDDEN = (
    r"\s-k\s",
    r"--ignore\b",
    r"--deselect\b",
)


def _workflow_text() -> str:
    assert _WORKFLOW_PATH.is_file(), f"missing workflow: {_WORKFLOW_PATH}"
    return _WORKFLOW_PATH.read_text(encoding="utf-8")


def _offline_pytest_block(text: str) -> str:
    return text.split("offline-unit-and-contracts:", 1)[-1]


def test_contract_module_has_no_network_imports() -> None:
    source = _CONTRACT_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(_CONTRACT_PATH))
    forbidden = {"urllib", "urllib.request", "urllib.error", "http.client", "requests"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                assert alias.name not in forbidden and root not in forbidden, alias.name
        if isinstance(node, ast.ImportFrom):
            assert node.module not in forbidden, node.module
            if node.module:
                root = node.module.split(".", 1)[0]
                assert root not in forbidden, node.module


def test_workflow_name_is_ci() -> None:
    text = _workflow_text()
    assert re.search(r"^name:\s*CI\s*$", text, re.MULTILINE)


def test_triggers_pr_and_push_main_only() -> None:
    text = _workflow_text()
    assert "pull_request_target" not in text
    assert re.search(
        r"pull_request:\s*\n\s*branches:\s*\n\s*-\s*main\b",
        text,
    )
    push_block = re.search(r"push:\s*\n\s*branches:\s*\n((?:\s*-\s*.+\n)+)", text)
    assert push_block, "push.branches block missing"
    branches = re.findall(r"-\s*(\S+)", push_block.group(1))
    assert branches == ["main"]
    assert "paths:" not in text
    assert "paths-ignore:" not in text


def test_top_level_permissions_contents_read_only() -> None:
    text = _workflow_text()
    perms = re.findall(r"^permissions:\s*\n\s*contents:\s*read\s*$", text, re.MULTILINE)
    assert len(perms) == 1, "expected exactly one top-level permissions: contents: read"
    assert "packages: write" not in text
    jobs_block = text.split("jobs:", 1)[-1]
    assert re.search(r"^\s{2,}permissions:\s*$", jobs_block, re.MULTILINE) is None


def test_stable_job_display_names_exactly_once() -> None:
    text = _workflow_text()
    for name in _REQUIRED_JOB_NAMES:
        matches = re.findall(rf"^\s*name:\s*{re.escape(name)}\s*$", text, re.MULTILINE)
        assert len(matches) == 1, f"job name '{name}' count={len(matches)}"


def test_all_uses_pins_are_full_sha() -> None:
    text = _workflow_text()
    uses_entries = _SHA_USES_RE.findall(text)
    assert len(uses_entries) == 6, f"expected 6 pinned uses, got {uses_entries}"
    for action, sha in uses_entries:
        assert len(sha) == 40, action
        assert not action.endswith("@v"), action


def test_expected_action_shas_present() -> None:
    text = _workflow_text()
    assert _CHECKOUT_SHA in text
    assert _SETUP_PYTHON_SHA in text
    assert _GITLEAKS_SHA in text
    assert "actions/checkout@v" not in text
    assert "actions/setup-python@v" not in text
    assert "gitleaks/gitleaks-action@v" not in text


def test_checkout_persist_credentials_false_on_all_three() -> None:
    text = _workflow_text()
    assert text.count("persist-credentials: false") == 3


def test_secret_scan_full_history_and_gitleaks_safeguards() -> None:
    text = _workflow_text()
    secret_job = text.split("secret-scan:", 1)[-1]
    assert "fetch-depth: 0" in secret_job
    assert f"gitleaks/gitleaks-action@{_GITLEAKS_SHA}" in secret_job
    assert 'GITLEAKS_ENABLE_COMMENTS: "false"' in secret_job
    assert 'GITLEAKS_ENABLE_UPLOAD_ARTIFACT: "false"' in secret_job
    assert 'GITLEAKS_ENABLE_SUMMARY: "false"' in secret_job
    assert f'GITLEAKS_VERSION: "{_GITLEAKS_DEFAULT_VERSION}"' in secret_job
    assert "GITLEAKS_REDACT" not in secret_job
    assert "GITLEAKS_LICENSE" not in secret_job
    assert re.search(r'GITLEAKS_VERSION:\s*["\']latest["\']', secret_job, re.IGNORECASE) is None


def test_no_repository_secrets_or_write_permissions() -> None:
    text = _workflow_text()
    for pattern in _FORBIDDEN_SECRET_PATTERNS:
        assert not re.search(pattern, text, re.IGNORECASE | re.MULTILINE), pattern
    assert "unset DASHSCOPE_API_KEY" in text


def test_no_deploy_docker_publish_steps() -> None:
    text = _workflow_text()
    for pattern in _FORBIDDEN_DEPLOY_PATTERNS:
        assert not re.search(pattern, text, re.IGNORECASE), pattern


def test_offline_pytest_safeguards_present() -> None:
    offline = _offline_pytest_block(_workflow_text())
    assert "PYTHONDONTWRITEBYTECODE" in offline
    assert "-p no:cacheprovider" in offline
    assert "--basetemp" in offline
    assert "--tb=short" in offline
    assert "unset DASHSCOPE_API_KEY" in offline


def test_offline_pytest_has_no_deselection_or_bypass() -> None:
    offline = _offline_pytest_block(_workflow_text())
    for pattern in _PYTEST_DESELECT_FORBIDDEN:
        assert not re.search(pattern, offline), pattern
    assert "test_render_bot_answer_html_escapes_markup" not in offline
    assert re.search(r"^\s+if:\s", offline, re.MULTILINE) is None


def test_mandatory_offline_modules_in_pytest_list() -> None:
    offline = _offline_pytest_block(_workflow_text())
    for module in _MANDATORY_OFFLINE_MODULES:
        assert module in offline, module
    assert _EXCLUDED_INTEGRATION not in offline


def test_g2_contract_runs_in_offline_unit_and_contracts_job() -> None:
    text = _workflow_text()
    offline = _offline_pytest_block(text)
    assert "tests/test_g2_pr_ci_contract.py" in offline
    assert offline.index("tests/test_g2_pr_ci_contract.py") < offline.index("secret-scan:")


def test_planner_modules_required_in_ci() -> None:
    offline = _offline_pytest_block(_workflow_text())
    assert "tests/test_turn_planner_llm.py" in offline
    assert "tests/test_turn_planner_wiring.py" in offline


def test_lint_job_includes_validate_and_compile() -> None:
    text = _workflow_text()
    lint = text.split("offline-unit-and-contracts:", 1)[0]
    assert "validate_client_pack.py --client-id demo" in lint
    assert "validate_client_pack.py --client-id _template" in lint
    assert "PYTHONPYCACHEPREFIX" in lint
    assert 'python -c "import app"' in lint or "import app" in lint


def test_concurrency_groups_by_pr_or_ref() -> None:
    text = _workflow_text()
    assert "github.event.pull_request.number" in text
    assert "cancel-in-progress: true" in text
