"""G4 manual fail-closed production deploy — static offline contract."""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEPLOY_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "deploy-production.yml"
_CI_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
_PUBLISH_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "publish-image.yml"
_DOCKERIGNORE = _REPO_ROOT / ".dockerignore"
_RECEIVER = _REPO_ROOT / "deploy" / "production" / "server" / "deploy-receiver.sh"
_ROOT_DEPLOY = _REPO_ROOT / "deploy" / "production" / "server" / "deploy-production.sh"
_SUDOERS = _REPO_ROOT / "deploy" / "production" / "server" / "artgents-deploy.sudoers.example"
_CONTRACT_PATH = Path(__file__).resolve()

_IMAGE_REPO = "ghcr.io/dhmnzr79/artgents-bot"
_CHECKOUT_SHA = "d23441a48e516b6c34aea4fa41551a30e30af803"

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_REMOTE_CMD_RE = re.compile(
    r"^deploy-production [0-9a-f]{40} sha256:[0-9a-f]{64}$"
)
_RECEIVER_CMD_RE = re.compile(
    r"^deploy-production ([0-9a-f]{40}) (sha256:[0-9a-f]{64})$"
)
_BACKUP_RECEIPT_ROOT = "/var/lib/artgents/backups/receipts"
_SSH_USER_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
_FORBIDDEN_HOST_CHARS = re.compile(r"[\s`$;|&<>@]")

_SHA_USES_RE = re.compile(
    r"^\s*(?:-\s*)?uses:\s*([^\s@]+)@([0-9a-f]{40})\b",
    re.IGNORECASE | re.MULTILINE,
)

_RUN_BLOCK_START = re.compile(r"^        run: \|\s*$")


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
    assert bodies, "expected at least one run: | block in deploy workflow"
    return bodies


def validate_source_sha(value: str) -> None:
    if not _SHA_RE.fullmatch(value or ""):
        raise ValueError("invalid source_sha")


def validate_registry_digest(value: str) -> None:
    if not _DIGEST_RE.fullmatch(value or ""):
        raise ValueError("invalid registry_digest")


def validate_immutable_reference(digest: str, *, repository: str = _IMAGE_REPO) -> str:
    validate_registry_digest(digest)
    if repository != _IMAGE_REPO:
        raise ValueError("repository not allowed")
    return f"{repository}@{digest}"


def tokenize_forced_command(original: str) -> tuple[str, str, str]:
    if any(ch in original for ch in "\n\r\t"):
        raise ValueError("forbidden whitespace in command")
    if original != original.strip():
        raise ValueError("leading or trailing whitespace forbidden")
    match = _RECEIVER_CMD_RE.fullmatch(original)
    if not match:
        raise ValueError("invalid forced command grammar")
    sha, digest = match.group(1), match.group(2)
    return "deploy-production", sha, digest


def validate_backup_receipt_candidate_string(path: str) -> None:
    if any(ch in path for ch in "\n\r\t"):
        raise ValueError("unsafe whitespace")
    if ".." in path.split("/"):
        raise ValueError("path traversal")
    if not path.startswith(f"{_BACKUP_RECEIPT_ROOT}/"):
        raise ValueError("outside receipt root")
    if path.rstrip("/") == _BACKUP_RECEIPT_ROOT:
        raise ValueError("receipt root cannot be target file")


def validate_backup_receipt_file_metadata(
    path: Path,
    *,
    receipt_root: Path,
) -> None:
    root_resolved = receipt_root.resolve()
    canonical = path.resolve()
    if canonical == root_resolved:
        raise ValueError("receipt root cannot be the file")
    try:
        canonical.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError("outside receipt root") from exc
    if not canonical.is_file():
        raise ValueError("must be regular file")
    if path.is_symlink():
        raise ValueError("symlink not allowed")
    mode = path.stat().st_mode & 0o777
    if mode & 0o022:
        raise ValueError("group/world writable")
    if path.stat().st_uid != 0:
        raise ValueError("must be root-owned")


def validate_remote_command_line(line: str) -> None:
    if not _REMOTE_CMD_RE.fullmatch(line.strip()):
        raise ValueError("invalid remote command grammar")


def validate_ssh_host(host: str) -> None:
    if not host or _FORBIDDEN_HOST_CHARS.search(host):
        raise ValueError("invalid ssh host")


def validate_ssh_user(user: str) -> None:
    if user == "root":
        raise ValueError("deploy ssh user must not be root")
    if not _SSH_USER_RE.fullmatch(user or ""):
        raise ValueError("invalid ssh user")


def validate_ssh_port(port: str) -> None:
    if not re.fullmatch(r"[0-9]+", port or ""):
        raise ValueError("invalid ssh port")
    num = int(port)
    if num < 1 or num > 65535:
        raise ValueError("ssh port out of range")


def _deploy_text() -> str:
    assert _DEPLOY_WORKFLOW.is_file(), f"missing {_DEPLOY_WORKFLOW}"
    return _DEPLOY_WORKFLOW.read_text(encoding="utf-8")


def _receiver_text() -> str:
    return _RECEIVER.read_text(encoding="utf-8")


def _root_deploy_text() -> str:
    return _ROOT_DEPLOY.read_text(encoding="utf-8")


def test_contract_module_has_no_network_imports() -> None:
    source = _CONTRACT_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(_CONTRACT_PATH))
    forbidden = {"urllib", "urllib.request", "urllib.error", "http.client", "requests", "socket"}
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


def test_workflow_manual_dispatch_only() -> None:
    text = _deploy_text()
    assert re.search(r"^name:\s*Deploy production\s*$", text, re.MULTILINE)
    assert "workflow_dispatch:" in text
    assert re.search(r"^\s*push:\s*$", text, re.MULTILINE) is None
    assert re.search(r"^\s*pull_request:\s*$", text, re.MULTILINE) is None
    assert re.search(r"^\s*schedule:\s*$", text, re.MULTILINE) is None


def test_workflow_inputs_minimal() -> None:
    text = _deploy_text()
    assert "source_sha:" in text
    assert "confirm_production:" in text
    assert re.search(r"^\s*type:\s*boolean\s*$", text, re.MULTILINE)
    for forbidden in ("digest:", "host:", "command:", "image:", "reason:", "path:"):
        assert forbidden not in text.split("workflow_dispatch:", 1)[-1].split("jobs:", 1)[0], forbidden


def test_workflow_guards_and_concurrency() -> None:
    text = _deploy_text()
    assert 'refs/heads/main' in text
    assert "Dhmnzr79/artgents-bot" in text
    assert re.search(r"\^\[0-9a-f\]\{40\}\$", text)
    assert "confirm_production must be true" in text
    assert "merge-base --is-ancestor" in text
    assert "git rev-parse HEAD" in text or 'MAIN_HEAD="$(git rev-parse HEAD)"' in text
    assert "git fetch origin" not in text
    assert "group: production-deploy" in text
    assert "cancel-in-progress: false" in text
    assert re.search(r"\benvironment:\s*production\b", text) is None


def test_workflow_gh_api_get_without_post() -> None:
    text = _deploy_text()
    locate = text.split("Locate successful G3 publish run", 1)[1].split("Download and validate", 1)[0]
    assert "gh api --method GET" in locate
    assert '"/repos/${WORKFLOW_REPOSITORY}/actions/workflows/publish-image.yml/runs"' in locate
    assert "jq --arg sha" in locate
    assert "env.INPUT_SHA" not in locate
    assert "RUNS_RAW" in locate


def test_workflow_run_blocks_no_direct_github_expression_interpolation() -> None:
    text = _deploy_text()
    for body in _workflow_run_shell_bodies(text):
        assert "${{" not in body, "run shell must not embed GitHub expressions"
    assert "WORKFLOW_REF" in text
    assert "WORKFLOW_REPOSITORY" in text
    assert "GHCR_TOKEN" in text
    ghcr_block = text.split("Verify GHCR SHA tag digest matches receipt", 1)[1].split("Export validated", 1)[0]
    assert "GHCR_TOKEN" in ghcr_block
    assert 'docker login ghcr.io -u "$GITHUB_ACTOR"' in ghcr_block
    assert "secrets.GITHUB_TOKEN" not in ghcr_block
    assert "github.actor" not in ghcr_block


def test_workflow_g3_receipt_and_ghcr_verify() -> None:
    text = _deploy_text()
    assert "publish-image.yml" in text
    assert 'event=="push"' in text or ".event==\"push\"" in text
    assert "publish-receipt-" in text
    assert "publish-receipt.json" in text
    assert _IMAGE_REPO in text
    assert "immutable_reference" in text
    assert "buildx imagetools inspect" in text
    assert "docker push" not in text
    assert "docker/build-push-action" not in text
    assert re.search(r"\bdocker build\b", text) is None
    assert ":latest" not in text


def test_workflow_jobs_permissions_and_needs() -> None:
    text = _deploy_text()
    resolve = text.split("resolve-image:", 1)[1].split("deploy:", 1)[0]
    deploy = text.split("deploy:", 1)[1]
    assert "actions: read" in resolve
    assert "packages: read" in resolve
    assert "packages: write" not in text
    assert re.search(r"^\s*permissions:\s*\{\}\s*$", deploy, re.MULTILINE)
    assert "needs: resolve-image" in deploy
    assert "name: Deploy immutable image" in text
    assert "PRODUCTION_SSH_HOST" in deploy
    assert "PRODUCTION_SSH_PRIVATE_KEY" in deploy
    assert "PRODUCTION_SSH_KNOWN_HOSTS" in deploy
    assert "StrictHostKeyChecking=yes" in deploy
    assert "ssh-keyscan" not in text
    assert "StrictHostKeyChecking=no" not in text
    assert "appleboy/" not in text
    assert "ssh-action" not in text
    assert "ForwardAgent=no" in deploy
    assert "AllowAgentForwarding" not in text
    assert "SSH user must not be root" in deploy


def test_workflow_ssh_remote_grammar_and_no_secret_transfer() -> None:
    text = _deploy_text()
    deploy = text.split("deploy:", 1)[1]
    assert re.search(
        r"deploy-production \$\{SOURCE_SHA\} \$\{REGISTRY_DIGEST\}",
        deploy,
    )
    for forbidden in (
        "BOT_PG_DSN",
        "SMTP_PASSWORD",
        "DASHSCOPE_API_KEY",
        "GITHUB_TOKEN",
        "GHCR",
        "docker login",
    ):
        assert forbidden not in deploy, forbidden


def test_workflow_actions_pinned_full_sha() -> None:
    text = _deploy_text()
    uses_entries = _SHA_USES_RE.findall(text)
    assert len(uses_entries) >= 1
    for action, sha in uses_entries:
        assert len(sha) == 40, action
        assert not action.endswith("@v"), action
    assert _CHECKOUT_SHA in text
    assert "actions/checkout@v" not in text


def test_receiver_forced_command_contract() -> None:
    text = _receiver_text()
    assert "SSH_ORIGINAL_COMMAND" in text
    assert "deploy-production" in text
    assert "DEPLOY_SCRIPT=/opt/artgents/bin/deploy-production" in text
    assert 'exec sudo -n "$DEPLOY_SCRIPT"' in text
    assert "id -u" in text
    assert "eval" not in text
    assert "bash -c" not in text
    assert "sh -c" not in text
    assert "read -r -a" not in text
    assert "read -a" not in text
    assert "BASH_REMATCH" in text


def test_root_deploy_script_staged_fail_closed() -> None:
    text = _root_deploy_text()
    assert "id -u" in text and "must run as root" in text
    assert _IMAGE_REPO in text
    assert "@" in text and ":latest" not in text
    assert "flock" in text
    assert "/opt/artgents/bin/backup-postgres" in text
    assert "pre-deploy" in text
    assert "run --rm migrate" in text
    assert '[ "$#" -ne 2 ]' in text or '[ "$#" -eq 2 ]' in text
    assert "--no-deps bot admin" in text
    assert "--no-deps caddy" in text
    assert "ps --status healthy" not in text
    assert "docker inspect" in text
    assert "State.Health.Status" in text or ".State.Health" in text
    assert "stop_service_if_present 1 caddy" in text
    assert "|| true" not in text
    assert "RepoDigests" in text
    assert "{{index .RepoDigests 0}}" not in text
    assert "realpath -e --" in text
    assert "validate_current_receipt_metadata" in text
    assert "current deploy receipt must not be a symlink" in text
    assert "failed to inspect" in text
    assert "docker image inspect failed" in text
    assert "ps --all -q" in text
    assert "stop_service_if_present" in text
    assert "run_application_maintenance_stop" in text
    assert "< <(compose" not in text
    assert "< <(docker" not in text
    assert "/var/lib/artgents/backups/receipts" in text
    assert "|| echo \"null\"" not in text
    assert "'source_sha': '$SOURCE_SHA'" not in text
    assert "DEPLOY_SOURCE_SHA" in text
    assert "read_previous_digest_or_empty" in text or "CURRENT_RECEIPT_PATH" in text
    assert "health/ready" in text
    assert "--profile public" in text
    assert "current.json" in text
    assert "previous.json" in text
    assert "rollback not performed" in text.lower()
    assert "G5" in _REPO_ROOT.joinpath("deploy/production/server/README.md").read_text(encoding="utf-8")
    assert "eval" not in text
    for secret in ("SMTP_PASSWORD", "BOT_PG_DSN", "ADMIN_DASHBOARD_TOKEN"):
        assert secret not in text


def _main_deploy_body(text: str) -> str:
    """Script body after flock/preflight through success (excludes helper definitions)."""
    start = text.find('STARTED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")')
    assert start != -1
    return text[start:]


def test_root_deploy_order_backup_before_migrate() -> None:
    full = _root_deploy_text()
    main = _main_deploy_body(full)
    backup_pos = main.find("pre-deploy")
    maintenance_call = main.find("run_application_maintenance_stop")
    migrate_pos = main.find("run --rm migrate")
    readiness_pos = main.find("health/ready")
    caddy_up = main.find("up -d --no-deps caddy")
    assert backup_pos != -1 and maintenance_call != -1 and migrate_pos != -1
    assert backup_pos < maintenance_call < migrate_pos
    assert readiness_pos != -1 and caddy_up != -1 and readiness_pos < caddy_up

    maint_block = full.split("run_application_maintenance_stop() {", 1)[1].split("\n}", 1)[0]
    caddy_stop = maint_block.find("stop_service_if_present 1 caddy")
    bot_stop = maint_block.find("stop_service_if_present 0 bot")
    admin_stop = maint_block.find("stop_service_if_present 0 admin")
    verify_caddy = maint_block.find("verify_service_not_running_or_restarting 1 caddy")
    verify_bot = maint_block.find("verify_service_not_running_or_restarting 0 bot")
    verify_admin = maint_block.find("verify_service_not_running_or_restarting 0 admin")
    assert caddy_stop != -1 and bot_stop != -1 and admin_stop != -1
    assert caddy_stop < verify_caddy < bot_stop < admin_stop
    assert verify_bot != -1 and verify_admin != -1 and verify_admin < len(maint_block)


def test_compose_ps_failure_is_not_absence() -> None:
    text = _root_deploy_text()
    assert "compose_ps_all_output" in text
    assert "if ! output=$(compose_public ps --all -q" in text
    assert "if ! output=$(compose ps --all -q" in text
    assert "failed to inspect" in text
    assert "expected at most one" in text


def test_current_receipt_metadata_contract() -> None:
    text = _root_deploy_text()
    assert "validate_current_receipt_metadata" in text
    idx = text.find("validate_current_receipt_metadata")
    migrate_idx = text.find("run_application_maintenance_stop")
    assert idx != -1 and migrate_idx != -1 and idx < migrate_idx
    assert "group/world writable" in text


def test_sudoers_minimal_contract() -> None:
    text = _SUDOERS.read_text(encoding="utf-8")
    assert "NOPASSWD: /opt/artgents/bin/deploy-production" in text
    assert " ALL=(ALL) " not in text
    assert "/usr/bin/docker" not in text
    assert "/bin/sh" not in text


def test_dockerignore_excludes_server_assets() -> None:
    patterns = {
        line.strip()
        for line in _DOCKERIGNORE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    assert "deploy/production/server/" in patterns


def test_g4_contract_in_ci_and_publish_verify() -> None:
    ci = _CI_WORKFLOW.read_text(encoding="utf-8")
    publish = _PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    assert "tests/test_g4_manual_deploy_contract.py" in ci
    verify = publish.split("verify:", 1)[1].split("secret-scan:", 1)[0]
    assert "tests/test_g4_manual_deploy_contract.py" in verify


@pytest.mark.parametrize(
    "sha",
    [
        "abc",
        "ABCDEF0123456789ABCDEF0123456789ABCDEF01",
        "0123456789abcdef0123456789abcdef01234567g",
        "0123456789abcdef0123456789abcdef0123456;rm",
        "origin/main",
        "0123456789abcdef0123456789abcdef01234567\n",
    ],
)
def test_reject_invalid_source_sha(sha: str) -> None:
    with pytest.raises(ValueError):
        validate_source_sha(sha)


@pytest.mark.parametrize(
    "digest",
    [
        "sha256:abc",
        "SHA256:" + "a" * 64,
        "sha256:" + "g" * 64,
        "sha256:" + "a" * 64 + " extra",
        "latest",
        "main",
    ],
)
def test_reject_invalid_digest(digest: str) -> None:
    with pytest.raises(ValueError):
        validate_registry_digest(digest)


def test_reject_extra_receiver_tokens() -> None:
    sha = "a" * 40
    digest = "sha256:" + "b" * 64
    with pytest.raises(ValueError):
        tokenize_forced_command(f"deploy-production {sha} {digest} evil")
    with pytest.raises(ValueError):
        tokenize_forced_command(f"evil {sha} {digest}")
    with pytest.raises(ValueError):
        tokenize_forced_command(f"deploy-production  {sha} {digest}")
    with pytest.raises(ValueError):
        tokenize_forced_command(f"deploy-production {sha} {digest}\n")


def test_reject_root_deploy_extra_argument_pattern() -> None:
    text = _root_deploy_text()
    assert re.search(r'\[ "\$#" -ne 2 \]', text)


def test_reject_arbitrary_repository_in_immutable_reference() -> None:
    digest = "sha256:" + "c" * 64
    with pytest.raises(ValueError):
        validate_immutable_reference(digest, repository="docker.io/evil/app")


def test_reject_malformed_remote_command_line() -> None:
    with pytest.raises(ValueError):
        validate_remote_command_line("deploy-production short sha256:" + "d" * 64)
    with pytest.raises(ValueError):
        validate_remote_command_line("curl https://evil.example")


def test_accept_valid_remote_command_line() -> None:
    sha = "e" * 40
    digest = "sha256:" + "f" * 64
    validate_remote_command_line(f"deploy-production {sha} {digest}")


@pytest.mark.parametrize(
    "host",
    [
        "",
        "host;rm",
        "host$(id)",
        "host name",
        "host@evil",
    ],
)
def test_reject_ssh_host_injection(host: str) -> None:
    with pytest.raises(ValueError):
        validate_ssh_host(host)


@pytest.mark.parametrize(
    "user",
    ["", "root", "1bad", "deploy;id", "UPPER"],
)
def test_reject_ssh_user_contract(user: str) -> None:
    with pytest.raises(ValueError):
        validate_ssh_user(user)


@pytest.mark.parametrize("port", ["", "0", "70000", "22;id", "-1"])
def test_reject_ssh_port_contract(port: str) -> None:
    with pytest.raises(ValueError):
        validate_ssh_port(port)


def test_missing_backup_utility_contract_in_root_script() -> None:
    text = _root_deploy_text()
    assert "backup-postgres" in text
    assert "G7" in _REPO_ROOT.joinpath("deploy/production/server/README.md").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "path",
    [
        "/var/lib/artgents/backups/receipts/../etc/passwd",
        "/var/lib/artgents/backups/receipts",
        "/tmp/outside/receipt.json",
        "/var/lib/artgents/backups/receipts/evil\n",
    ],
)
def test_reject_backup_receipt_path_strings(path: str) -> None:
    with pytest.raises(ValueError):
        validate_backup_receipt_candidate_string(path)


def test_backup_receipt_file_metadata_negative(tmp_path: Path) -> None:
    root = tmp_path / "receipts"
    root.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        validate_backup_receipt_file_metadata(outside, receipt_root=root)
    missing = root / "missing.json"
    with pytest.raises(ValueError):
        validate_backup_receipt_file_metadata(missing, receipt_root=root)
    dir_path = root / "subdir"
    dir_path.mkdir()
    with pytest.raises(ValueError):
        validate_backup_receipt_file_metadata(dir_path, receipt_root=root)


def test_backup_receipt_world_writable_rejected() -> None:
    text = _root_deploy_text()
    assert "group/world writable" in text
    assert "022" in text


def validate_current_receipt_path_metadata(
    path: Path,
    *,
    state_dir: Path,
    is_symlink: bool = False,
    owner_uid: int = 0,
    mode: int = 0o600,
) -> None:
    if path.is_symlink() or is_symlink:
        raise ValueError("symlink not allowed")
    if not path.is_file():
        raise ValueError("must be regular file")
    if path.parent.resolve() != state_dir.resolve():
        raise ValueError("must live directly in deploy state directory")
    if owner_uid != 0:
        raise ValueError("must be root-owned")
    if mode & 0o022:
        raise ValueError("group/world writable")


def test_current_receipt_dangling_symlink_checked_before_absence() -> None:
    block = _root_deploy_text().split("validate_current_receipt_metadata() {", 1)[1].split("\n}", 1)[0]
    symlink_pos = block.find('[ -L "$CURRENT_RECEIPT" ]')
    absent_pos = block.find('[ ! -e "$CURRENT_RECEIPT" ]')
    assert symlink_pos != -1 and absent_pos != -1 and symlink_pos < absent_pos


def test_paused_removing_container_states_fail_closed() -> None:
    block = _root_deploy_text().split("stop_service_if_present() {", 1)[1].split("\n}", 1)[0]
    assert "exited | created | dead)" in block
    assert "paused | removing)" in block
    assert "unsafe state for maintenance" in block
    assert not re.search(r"exited \| created \| dead \| paused", block)


def test_current_receipt_symlink_rejected(tmp_path: Path) -> None:
    if os.name != "posix" or not hasattr(os, "symlink"):
        pytest.skip("symlink test requires POSIX")
    state = tmp_path / "deploy"
    state.mkdir()
    link = state / "current.json"
    os.symlink("/nonexistent/target-current-receipt.json", link)
    assert link.is_symlink()
    assert not link.exists()
    with pytest.raises(ValueError, match="symlink"):
        validate_current_receipt_path_metadata(link, state_dir=state)


def test_current_receipt_wrong_owner_or_writable_rejected(tmp_path: Path) -> None:
    state = tmp_path / "deploy"
    state.mkdir()
    receipt = state / "current.json"
    receipt.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        validate_current_receipt_path_metadata(receipt, state_dir=state, owner_uid=1000)
    with pytest.raises(ValueError):
        validate_current_receipt_path_metadata(receipt, state_dir=state, mode=0o666)


def test_corrupted_current_receipt_must_not_become_null() -> None:
    text = _root_deploy_text()
    assert "|| echo \"null\"" not in text
    assert "read_previous_digest_or_empty" in text
    assert "invalid current deploy receipt" in text
