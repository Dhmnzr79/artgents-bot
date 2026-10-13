"""The shared release list must execute the same protection suites in PR and publish."""
from pathlib import Path
import re

import pytest

from tests.workflow_test_selection import ROOT, read_selection, selected_tests


def workflows():
    return tuple((ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
                 for name in ("ci.yml", "publish-image.yml"))


def test_pr_and_publish_execute_shared_selections_without_discovery():
    ci, publish = workflows()
    offline = ci.split("  offline-unit-and-contracts:", 1)[1].split("  demo-d1-clinic-policy-regression:", 1)[0]
    policy = ci.split("  demo-d1-clinic-policy-regression:", 1)[1].split("  postgres-qualification:", 1)[0]
    verify = publish.split("  verify:", 1)[1].split("  secret-scan:", 1)[0]
    for block, name in ((offline, "offline"), (policy, "policy")):
        commands = re.findall(r"^\s+python -m pytest ([^\n]+)$", block, re.MULTILINE)
        assert len(commands) == 1
        assert commands[0].endswith(f"@tests/release/{name}.txt")
        assert selected_tests(block) == set(read_selection(ROOT / f"tests/release/{name}.txt"))
    assert 'sort -u tests/release/offline.txt tests/release/policy.txt > "$BASETEMP/release-tests.txt"' in verify
    commands = re.findall(r"^\s+python -m pytest ([^\n]+)$", verify, re.MULTILINE)
    assert len(commands) == 1
    assert commands[0].endswith('"@$BASETEMP/release-tests.txt" tests/test_g3_immutable_image_contract.py')
    assert selected_tests(verify) == selected_tests(offline) | selected_tests(policy) | {"tests/test_g3_immutable_image_contract.py"}
    assert "tests/test_release_test_selection.py" in selected_tests(offline)


@pytest.mark.parametrize("entry", ["", "tests/", "tests/test_missing_release.py", "--ignore=tests/test_d2_demo_limits.py", "-k", "../tests/test_d2_demo_limits.py", "@tests/release/policy.txt"])
def test_selection_rejects_empty_missing_options_and_discovery(tmp_path, entry):
    path = tmp_path / "selection.txt"
    path.write_text(entry + "\n" if entry else "", encoding="utf-8")
    with pytest.raises(AssertionError):
        read_selection(path)


def test_selection_rejects_duplicate_files(tmp_path):
    path = tmp_path / "selection.txt"
    path.write_text("tests/test_d2_demo_limits.py\ntests/test_d2_demo_limits.py\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="Duplicate"):
        read_selection(path)
