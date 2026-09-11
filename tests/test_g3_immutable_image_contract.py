"""G3 immutable GHCR image workflow contract — static, fully offline."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PUBLISH_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "publish-image.yml"
_CI_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
_DOCKERFILE = _REPO_ROOT / "Dockerfile"
_DOCKERIGNORE = _REPO_ROOT / ".dockerignore"
_PROD_INPUT = _REPO_ROOT / "requirements.txt"
_PROD_LOCK = _REPO_ROOT / "requirements.lock"
_CI_INPUT = _REPO_ROOT / "requirements-ci.in"
_CI_LOCK = _REPO_ROOT / "requirements-ci.lock"
_CONTRACT_PATH = Path(__file__).resolve()

_IMAGE_REPO = "ghcr.io/dhmnzr79/artgents-bot"
_CHECKOUT_SHA = "d23441a48e516b6c34aea4fa41551a30e30af803"
_SETUP_PYTHON_SHA = "ece7cb06caefa5fff74198d8649806c4678c61a1"
_GITLEAKS_SHA = "e0c47f4f8be36e29cdc102c57e68cb5cbf0e8d1e"
_BUILDX_SHA = "e468171a9de216ec08956ac3ada2f0791b6bd435"
_BUILD_PUSH_SHA = "263435318d21b8e681c14492fe198d362a7d2c83"
_LOGIN_SHA = "74a5d142397b4f367a81961eba4e8cd7edddf772"
_UPLOAD_ARTIFACT_SHA = "ea165f8d65b6e75b540449e92b4886f43607fa02"

_PROD_TEST_ONLY_PACKAGES = frozenset({"pytest", "pluggy", "iniconfig", "pygments"})

_LOCK_PIN_RE = re.compile(r"^([a-zA-Z0-9][a-zA-Z0-9._-]*)==([^\s\\]+)")
_LOCK_PIN_LINE_RE = re.compile(r"^([a-zA-Z0-9][a-zA-Z0-9._-]*)==([^\s\\]+)\s*\\?\s*$")
_LOCK_HASH_LINE_RE = re.compile(r"^\s*--hash=sha256:[0-9a-f]{64}\s*\\?\s*$")
_LOCK_VIA_COMMENT_RE = re.compile(r"^\s+#")
_FLOATING_MARKERS = (">=", "~=", "git+", "file:", "http://", "https://")

_SHA_USES_RE = re.compile(
    r"^\s*(?:-\s*)?uses:\s*([^\s@]+)@([0-9a-f]{40})\b",
    re.IGNORECASE | re.MULTILINE,
)

_FORBIDDEN_TRIGGERS = (
    r"pull_request:",
    r"pull_request_target:",
    r"workflow_dispatch:",
)

_FORBIDDEN_TAG_PATTERNS = (
    r":latest\b",
    r":main\b",
    r":prod\b",
    r":stable\b",
    r'tags:\s*["\']?latest',
)

_FORBIDDEN_SECRET_PATTERNS = (
    r"\$\{\{\s*secrets\.(?!GITHUB_TOKEN\b)",
    r"^\s*DASHSCOPE_API_KEY:",
    r"^\s*SMTP_PASSWORD:",
    r"^\s*SMTP_USER:",
    r"^\s*BOT_PG_DSN:",
    r"^\s*BOT_MIGRATOR_PG_DSN:",
    r"^\s*BOT_TEST_PG_DSN:",
    r"^\s*ADMIN_DASHBOARD_TOKEN:",
    r"SSH_PRIVATE_KEY",
    r"continue-on-error:\s*true",
)

_FORBIDDEN_EXTRA_PERMISSIONS = (
    r"^\s*actions:\s*write",
    r"^\s*id-token:\s*write",
    r"^\s*issues:\s*write",
    r"^\s*pull-requests:\s*write",
)

_G4_DEPLOY_MARKERS = (
    r"workflow_call:",
    r"\benvironment:\s*production\b",
    r"ssh-action",
    r"appleboy/",
)


def _publish_text() -> str:
    assert _PUBLISH_WORKFLOW.is_file(), f"missing {_PUBLISH_WORKFLOW}"
    return _PUBLISH_WORKFLOW.read_text(encoding="utf-8")


def _ci_text() -> str:
    return _CI_WORKFLOW.read_text(encoding="utf-8")


def _parse_lock_pins(path: Path) -> dict[str, str]:
    pins: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _LOCK_PIN_RE.match(line.strip())
        if match:
            pins[match.group(1).lower()] = match.group(2)
    return pins


def validate_lock_file_content(text: str, *, label: str = "lock") -> None:
    """Fail-closed pip-compile lock validation (offline, no I/O)."""
    lines = text.splitlines()
    in_entry = False
    hash_count = 0
    saw_pin = False

    def _finalize_entry() -> None:
        nonlocal in_entry, hash_count
        if in_entry and hash_count < 1:
            raise AssertionError(f"{label}: package pin without sha256 hash")
        in_entry = False
        hash_count = 0

    for lineno, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        if line.startswith("#"):
            continue
        for marker in _FLOATING_MARKERS:
            if marker in line:
                raise AssertionError(f"{label} line {lineno}: forbidden marker {marker!r}")
        if "\\" in line and not line.rstrip().endswith("\\") and _LOCK_PIN_LINE_RE.match(line):
            raise AssertionError(f"{label} line {lineno}: malformed continuation")
        if _LOCK_PIN_LINE_RE.match(line):
            _finalize_entry()
            for marker in _FLOATING_MARKERS:
                assert marker not in line, f"{label} line {lineno}"
            in_entry = True
            hash_count = 0
            saw_pin = True
            continue
        if _LOCK_HASH_LINE_RE.match(line):
            if not in_entry:
                raise AssertionError(f"{label} line {lineno}: hash without package pin")
            hash_count += 1
            continue
        if _LOCK_VIA_COMMENT_RE.match(line):
            if not in_entry or hash_count < 1:
                raise AssertionError(f"{label} line {lineno}: unexpected via comment")
            continue
        if re.match(r"^[A-Za-z]:\\", line) or line.startswith("./") or line.startswith(".\\"):
            raise AssertionError(f"{label} line {lineno}: local path dependency")
        raise AssertionError(f"{label} line {lineno}: unrecognized content: {line!r}")

    _finalize_entry()
    if not saw_pin:
        raise AssertionError(f"{label}: no pinned packages")


def _assert_lock_file_integrity(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    validate_lock_file_content(text, label=path.name)
    pins = _parse_lock_pins(path)
    assert pins, f"no pinned packages in {path.name}"
    assert "--hash=sha256:" in text


def _dockerignore_patterns() -> set[str]:
    patterns: set[str] = set()
    for raw in _DOCKERIGNORE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        patterns.add(line)
    return patterns


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


def test_workflow_and_job_names() -> None:
    text = _publish_text()
    assert re.search(r"^name:\s*Publish production image\s*$", text, re.MULTILINE)
    assert re.search(r"^\s*name:\s*Build, test and publish\s*$", text, re.MULTILINE)


def test_trigger_push_main_only() -> None:
    text = _publish_text()
    for pattern in _FORBIDDEN_TRIGGERS:
        assert not re.search(pattern, text), pattern
    push_block = re.search(r"^on:\s*\n\s*push:\s*\n\s*branches:\s*\n((?:\s*-\s*.+\n)+)", text, re.MULTILINE)
    assert push_block, "on.push.branches missing"
    branches = re.findall(r"-\s*(\S+)", push_block.group(1))
    assert branches == ["main"]


def test_fail_closed_jobs_needs_and_permissions() -> None:
    text = _publish_text()
    assert re.search(
        r"^permissions:\s*\n\s*contents:\s*read\s*$",
        text,
        re.MULTILINE,
    )
    assert "verify:" in text
    assert "secret-scan:" in text
    assert "build-test-and-publish:" in text
    build_job = text.split("build-test-and-publish:", 1)[-1]
    assert re.search(r"needs:\s*\n\s*-\s*verify\s*\n\s*-\s*secret-scan", build_job)
    assert re.search(
        r"build-test-and-publish:[\s\S]*?permissions:\s*\n\s*contents:\s*read\s*\n\s*packages:\s*write",
        text,
    )
    verify_block = text.split("verify:", 1)[1].split("secret-scan:", 1)[0]
    secret_block = text.split("secret-scan:", 1)[1].split("build-test-and-publish:", 1)[0]
    assert "packages: write" not in verify_block
    assert "packages: write" not in secret_block
    for pattern in _FORBIDDEN_EXTRA_PERMISSIONS:
        assert not re.search(pattern, text, re.MULTILINE), pattern


def test_image_name_tag_and_no_mutable_tags() -> None:
    text = _publish_text()
    assert _IMAGE_REPO in text
    assert _IMAGE_REPO.islower()
    assert "IMAGE_TAG: ${{ github.sha }}" in text
    assert re.search(rf"tags:\s*\$\{{\{{\s*env\.IMAGE\s*\}}\}}:\$\{{\{{\s*env\.IMAGE_TAG\s*\}}\}}", text)
    for pattern in _FORBIDDEN_TAG_PATTERNS:
        assert not re.search(pattern, text, re.IGNORECASE), pattern


def test_no_production_or_vps_secrets() -> None:
    text = _publish_text()
    for pattern in _FORBIDDEN_SECRET_PATTERNS:
        assert not re.search(pattern, text, re.IGNORECASE | re.MULTILINE), pattern
    assert "secrets.GITHUB_TOKEN" in text
    assert "unset DASHSCOPE_API_KEY" in text


def test_all_action_uses_pinned_full_sha() -> None:
    text = _publish_text()
    uses_entries = _SHA_USES_RE.findall(text)
    assert len(uses_entries) == 9
    for action, sha in uses_entries:
        assert len(sha) == 40, action
    for floating in (
        "actions/checkout@v",
        "actions/setup-python@v",
        "gitleaks/gitleaks-action@v",
        "docker/setup-buildx-action@v",
        "docker/build-push-action@v",
        "docker/login-action@v",
        "actions/upload-artifact@v",
    ):
        assert floating not in text


def test_secret_scan_job_matches_g2_safeguards() -> None:
    text = _publish_text()
    secret_job = text.split("secret-scan:", 1)[-1].split("build-test-and-publish:", 1)[0]
    assert "fetch-depth: 0" in secret_job
    assert f"gitleaks/gitleaks-action@{_GITLEAKS_SHA}" in secret_job
    assert 'GITLEAKS_ENABLE_COMMENTS: "false"' in secret_job
    assert 'GITLEAKS_ENABLE_UPLOAD_ARTIFACT: "false"' in secret_job
    assert 'GITLEAKS_ENABLE_SUMMARY: "false"' in secret_job
    assert 'GITLEAKS_VERSION: "8.24.3"' in secret_job


def test_single_docker_build_load_no_push_in_build_step() -> None:
    text = _publish_text()
    build_job = text.split("build-test-and-publish:", 1)[-1]
    build_uses = re.findall(r"docker/build-push-action@[0-9a-f]{40}", build_job)
    assert len(build_uses) == 1
    build_block = build_job.split("docker/build-push-action@", 1)[-1]
    build_block = build_block.split("docker/login-action", 1)[0]
    assert re.search(r"\bload:\s*true\b", build_block)
    assert re.search(r"\bpush:\s*false\b", build_block)
    assert not re.search(r"\bpush:\s*true\b", build_job)


def test_smoke_before_login_and_push_after_smoke() -> None:
    text = _publish_text()
    build_job = text.split("build-test-and-publish:", 1)[-1]
    assert build_job.index("docker/build-push-action@") < build_job.index("Smoke test exact local image")
    assert build_job.index("Smoke test exact local image") < build_job.index("docker/login-action@")
    assert build_job.index("docker/login-action@") < build_job.index("Push verified local image")
    assert build_job.index("Record local image ID") < build_job.index("Smoke test exact local image")


def test_registry_digest_hardening_and_receipt() -> None:
    text = _publish_text()
    push_step = text.split("Push verified local image", 1)[-1].split("Write publish receipt", 1)[0]
    assert "re.findall(r\"digest:\\s*(sha256:[0-9a-f]{64})\"" in push_step
    assert "len(unique) != 1" in push_step
    assert "publish-receipt.json" in text
    assert "immutable_reference" in text
    assert f"actions/upload-artifact@{_UPLOAD_ARTIFACT_SHA}" in text
    assert "GITHUB_STEP_SUMMARY" in text


def test_verify_job_preflight_and_ci_lock() -> None:
    text = _publish_text()
    verify = text.split("verify:", 1)[1].split("secret-scan:", 1)[0]
    assert "requirements-ci.lock" in verify
    assert "requirements.lock" not in verify.replace("requirements-ci.lock", "")
    assert "Compile production Python sources" in verify
    assert "pip install --upgrade pip" not in verify
    pytest_block = verify.split("Offline unit, G2/G3 contracts", 1)[-1]
    assert "tests/test_g2_pr_ci_contract.py" in pytest_block
    assert "tests/test_g3_immutable_image_contract.py" in pytest_block
    assert "tests/test_g4_manual_deploy_contract.py" in pytest_block


def test_production_input_has_no_pytest() -> None:
    prod_input = _PROD_INPUT.read_text(encoding="utf-8")
    lines = [ln.strip() for ln in prod_input.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    assert "pytest" not in lines
    assert prod_input.endswith("\n")


def test_production_lock_no_test_only_packages() -> None:
    _assert_lock_file_integrity(_PROD_LOCK)
    prod_pins = _parse_lock_pins(_PROD_LOCK)
    for pkg in _PROD_TEST_ONLY_PACKAGES:
        assert pkg not in prod_pins, pkg


def test_ci_lock_includes_pytest_and_matches_production_runtime() -> None:
    _assert_lock_file_integrity(_CI_LOCK)
    prod_pins = _parse_lock_pins(_PROD_LOCK)
    ci_pins = _parse_lock_pins(_CI_LOCK)
    assert "pytest" in ci_pins
    for name, version in prod_pins.items():
        assert name in ci_pins, f"runtime package {name} missing from CI lock"
        assert ci_pins[name] == version, f"version drift for {name}"


def test_ci_input_references_production_requirements() -> None:
    ci_input = _CI_INPUT.read_text(encoding="utf-8")
    assert "-r requirements.txt" in ci_input
    assert "pytest" in ci_input


def test_dockerignore_excludes_ci_and_input_keeps_production_lock() -> None:
    patterns = _dockerignore_patterns()
    assert "requirements.txt" in patterns
    assert "requirements-ci.in" in patterns
    assert "requirements-ci.lock" in patterns
    assert "requirements.lock" not in patterns


def test_dockerfile_production_lock_only_no_pip_upgrade() -> None:
    docker = _DOCKERFILE.read_text(encoding="utf-8")
    assert re.search(
        r"^FROM python:3\.11-slim@sha256:[0-9a-f]{64}\s*$",
        docker,
        re.MULTILINE,
    )
    assert re.search(r"^COPY requirements\.lock \./\s*$", docker, re.MULTILINE)
    assert "requirements.txt" not in docker
    assert "requirements-ci.in" not in docker
    assert "requirements-ci.lock" not in docker
    assert "--require-hashes" in docker
    assert "pip install --upgrade pip" not in docker
    assert re.search(r"^USER\s+10001:10001\s*$", docker, re.MULTILINE)


def test_ci_workflow_uses_ci_lock_without_pip_upgrade() -> None:
    ci = _ci_text()
    assert ci.count("pip install --require-hashes -r requirements-ci.lock") >= 2
    assert "pip install --upgrade pip" not in ci
    assert "requirements.lock" not in ci.replace("requirements-ci.lock", "")


def test_no_g4_deploy_wiring_started() -> None:
    text = _publish_text()
    for pattern in _G4_DEPLOY_MARKERS:
        assert not re.search(pattern, text, re.IGNORECASE), pattern


def test_ci_workflow_pip_cache_uses_ci_lock() -> None:
    ci = _ci_text()
    assert ci.count("cache-dependency-path: requirements-ci.lock") == 2


def test_publish_verify_pip_cache_uses_ci_lock() -> None:
    verify = _publish_text().split("verify:", 1)[1].split("secret-scan:", 1)[0]
    assert "cache-dependency-path: requirements-ci.lock" in verify


_VALID_MINIMAL_LOCK = """\
samplepkg==1.0.0 \\
    --hash=sha256:0000000000000000000000000000000000000000000000000000000000000001
    # via root
"""


def test_lock_validator_accepts_valid_exact_pin_with_hash(tmp_path: Path) -> None:
    path = tmp_path / "ok.lock"
    path.write_text(_VALID_MINIMAL_LOCK, encoding="utf-8")
    validate_lock_file_content(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "body",
    [
        "package>=1\n",
        "package~=1.2\n",
        "git+https://example.com/pkg.git@abc#egg=pkg\n",
        "https://example.com/pkg-1.0.tar.gz\n",
        "file:../local/pkg\n",
        ".\\local\\pkg\n",
        "totally-unknown-garbage-line\n",
        "samplepkg==1.0.0\n",
        "samplepkg==1.0.0 \\\n    totally-unknown-garbage-line\n",
    ],
)
def test_lock_validator_rejects_invalid_lines(body: str) -> None:
    with pytest.raises(AssertionError):
        validate_lock_file_content(body, label="tmp.lock")


def test_lock_validator_rejects_pin_without_hash() -> None:
    with pytest.raises(AssertionError):
        validate_lock_file_content("samplepkg==1.0.0 \\\n", label="tmp.lock")
