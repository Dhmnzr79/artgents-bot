"""POST-implementation checker for FINAL_CLIENT_PACK_DATA_CONVERGENCE Checkpoint B."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from evals.v5.final_scope_widget_e2e_live_contract import FROZEN_TURNS_HASH, sha256_file_hex
from evals.v5.final_scope_widget_e2e_retry4_live_contract import (
    assert_frozen_retry4_live_artifacts_unchanged,
)
from tests.test_ac3_scope_price_flow_offline import test_w1b_snapshot_checksums_unchanged
from tests.test_final_price_scope_coverage_nav_implementation import (
    test_frozen_pins_unchanged as test_pscn_frozen_pins_unchanged,
)
from tests.test_final_scope_widget_e2e_closeout_implementation import (
    test_frozen_retry4_artifacts_unchanged_after_closeout,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEMO = _REPO_ROOT / "clients" / "demo"
_TASK = _REPO_ROOT / "TASK.md"
_B_AUDIT = (
    _REPO_ROOT
    / "docs"
    / "evidence"
    / "client_pack"
    / "FINAL_CLIENT_PACK_DATA_CONVERGENCE_B_SEAM_AUDIT.md"
)

GOVERNANCE_BASELINE_HEAD = "e3730ea"
IMPLEMENTATION_BASELINE_HEAD = "1fdc26d"

DELETE_DATA_COUNT = 27
DELETE_MODULE_COUNT = 21

DELETE_DATA_PATHS = (
    "clients/demo/service_catalog.json",
    "clients/demo/marketing.yaml",
    "clients/demo/price_brand_aliases.json",
    "clients/demo/pricebook/facts.json",
    "clients/demo/pricebook/manifest.json",
    "clients/demo/pricebook/README.md",
    "clients/demo/pricebook/services/all_on_4.json",
    "clients/demo/pricebook/services/all_on_6.json",
    "clients/demo/pricebook/services/aligners.json",
    "clients/demo/pricebook/services/caries.json",
    "clients/demo/pricebook/services/clasp_dentures.json",
    "clients/demo/pricebook/services/classic.json",
    "clients/demo/pricebook/services/implant_supported_prosthetics.json",
    "clients/demo/pricebook/services/one_stage.json",
    "clients/demo/pricebook/services/periodontitis.json",
    "clients/demo/pricebook/services/professional_whitening.json",
    "clients/demo/pricebook/services/pterygoid_implants.json",
    "clients/demo/pricebook/services/pulpitis.json",
    "clients/demo/pricebook/services/removable_dentures.json",
    "clients/demo/pricebook/services/sinus_lift.json",
    "clients/demo/pricebook/services/teeth_treatment.json",
    "clients/demo/pricebook/services/temporary_teeth.json",
    "clients/demo/pricebook/services/tomography.json",
    "clients/demo/pricebook/services/tooth_extraction.json",
    "clients/demo/pricebook/services/veneers.json",
    "clients/demo/pricebook/services/zygomatic_implants.json",
    "clients/demo/pricebook/services/zirconia_crowns.json",
)

DELETE_MODULE_PATHS = (
    "query_selector.py",
    "core/pricebook_loader.py",
    "core/price_offers.py",
    "core/price_scope.py",
    "core/price_followup.py",
    "core/price_answer_assembler.py",
    "core/marketing_loader.py",
    "core/marketing_policy.py",
    "core/promo_overview.py",
    "core/service_selector_llm.py",
    "core/explicit_service.py",
    "core/clarify_state.py",
    "core/patient_situation.py",
    "core/patient_situation_llm.py",
    "core/patient_situation_routing.py",
    "core/patient_situation_session.py",
    "core/patient_scope_cues.py",
    "contracts/price_brand_aliases.py",
    "contracts/service_selection.py",
    "contracts/pricebook.py",
    "scripts/migrate_pricebook_services.py",
)

REQUIRED_IMPLEMENTATION_ARTIFACTS = (
    "docs/CLIENT_PACK_AUTHORING.md",
    "scripts/validate_client_pack.py",
    "tests/test_validate_client_pack.py",
    "tests/test_client_pack_template_scaffold.py",
    "clients/_template/target_response/service_catalog.json",
)


def test_b_seam_audit_exists_and_covers_post_a_inventory() -> None:
    assert _B_AUDIT.is_file()
    text = _B_AUDIT.read_text(encoding="utf-8")
    assert GOVERNANCE_BASELINE_HEAD in text
    assert IMPLEMENTATION_BASELINE_HEAD in text or "e3730ea" in text
    assert "HISTORICAL COMPATIBILITY KEEP" in text
    assert str(DELETE_DATA_COUNT) in text


def test_task_checkpoint_b_has_exact_lists_not_candidates() -> None:
    task = _TASK.read_text(encoding="utf-8")
    assert "### DELETE list — legacy data (27 files)" in task
    assert "### DELETE list — legacy modules / scripts / contracts (21 files)" in task
    b_section = task.split("## Checkpoint B — governance (PRE-CODE only)", 1)[1]
    assert "candidate" not in b_section.lower()


def test_legacy_data_and_modules_deleted() -> None:
    for rel in DELETE_DATA_PATHS:
        assert not (_REPO_ROOT / rel).exists(), rel
    for rel in DELETE_MODULE_PATHS:
        assert not (_REPO_ROOT / rel).exists(), rel


def test_implementation_artifacts_present() -> None:
    for rel in REQUIRED_IMPLEMENTATION_ARTIFACTS:
        assert (_REPO_ROOT / rel).is_file(), rel


def test_target_bundle_strict_loadable_and_checkpoint_a_loader_present() -> None:
    from contracts.response_schema import ResponseSchemaBundle
    from core.response_schema_loader import load_response_schema_bundle

    bundle = load_response_schema_bundle(_DEMO / "target_response")
    assert isinstance(bundle, ResponseSchemaBundle)
    assert len(bundle.services) == 22
    assert len(bundle.offers) == 32
    assert (_REPO_ROOT / "core/target_client_data.py").is_file()


def test_validator_cli_passes_on_demo() -> None:
    proc = subprocess.run(
        [sys.executable, str(_REPO_ROOT / "scripts" / "validate_client_pack.py"), "--client-id", "demo"],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr


def test_import_app_smoke() -> None:
    proc = subprocess.run(
        [sys.executable, "-c", "import app"],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_frozen_artifact_guards_unchanged() -> None:
    test_frozen_retry4_artifacts_unchanged_after_closeout()
    test_w1b_snapshot_checksums_unchanged()
    test_pscn_frozen_pins_unchanged()
    turns_path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    assert sha256_file_hex(turns_path) == FROZEN_TURNS_HASH
    assert_frozen_retry4_live_artifacts_unchanged()


def test_task_lists_match_governance_test_constants() -> None:
    assert len(DELETE_DATA_PATHS) == DELETE_DATA_COUNT
    assert len(DELETE_MODULE_PATHS) == DELETE_MODULE_COUNT
    task = _TASK.read_text(encoding="utf-8")
    acceptance_rows = len(re.findall(r"^\| \d+ \|", task, flags=re.MULTILINE))
    assert acceptance_rows >= 16
