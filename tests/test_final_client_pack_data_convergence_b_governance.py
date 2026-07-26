"""PRE-CODE checker for FINAL_CLIENT_PACK_DATA_CONVERGENCE Checkpoint B governance."""

from __future__ import annotations

import hashlib
import re
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

LEGACY_SHA256 = {
    "service_catalog.json": (
        "2089fde05d832df83cfcb5561165b170152c4cd8d02c775acebd1984b50728de"
    ),
    "marketing.yaml": (
        "e958fcd14be057a3e9867ec133175f4024f90178fbfedec8d3d1421f8e2c1eae"
    ),
    "price_brand_aliases.json": (
        "c6541d0cd2ecd526b25302f55f8fce4451f78a8d4e152ce523efc0d342c9c8f8"
    ),
    "pricebook/facts.json": (
        "fa94c72de8c936fffdc50998c0f761fd75adbafee7569f77dfe30771f55dd612"
    ),
    "pricebook/manifest.json": (
        "1611d97a89d74e101d66b78acb20fc86b166b0eaf508b6b3ab6fc68a3970e555"
    ),
}

DELETE_DATA_COUNT = 27
DELETE_MODULE_COUNT = 21
DELETE_TEST_COUNT = 16
UPDATE_COUNT = 18

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

FORBIDDEN_IMPLEMENTATION_ARTIFACTS = (
    "docs/CLIENT_PACK_AUTHORING.md",
    "scripts/validate_client_pack.py",
    "tests/test_validate_client_pack.py",
    "tests/test_client_pack_template_scaffold.py",
    "clients/_template/target_response/service_catalog.json",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_b_seam_audit_exists_and_covers_post_a_inventory() -> None:
    assert _B_AUDIT.is_file()
    text = _B_AUDIT.read_text(encoding="utf-8")
    assert GOVERNANCE_BASELINE_HEAD in text
    assert "Post-A inventory" in text or "post-A inventory" in text.lower()
    assert "HISTORICAL COMPATIBILITY KEEP" in text
    assert "DELETE NOW" in text
    assert str(DELETE_DATA_COUNT) in text
    assert str(DELETE_MODULE_COUNT) in text
    assert "target_response/**" in text
    assert "price_ref_routing" in text
    assert "24 ungrounded" in text or "24" in text


def test_task_checkpoint_b_has_exact_lists_not_candidates() -> None:
    task = _TASK.read_text(encoding="utf-8")
    assert GOVERNANCE_BASELINE_HEAD in task
    assert "FINAL_CLIENT_PACK_DATA_CONVERGENCE_B_SEAM_AUDIT.md" in task
    assert "test_final_client_pack_data_convergence_b_governance.py" in task
    assert "### DELETE list — legacy data (27 files)" in task
    assert "### DELETE list — legacy modules / scripts / contracts (21 files)" in task
    assert "### DELETE list — legacy-only tests (16 files)" in task
    assert "### UPDATE list (18 files)" in task
    assert "### KEEP list" in task
    assert "HISTORICAL COMPATIBILITY KEEP" in task
    assert "Future checkpoint" in task or "future checkpoint" in task
    b_section = task.split("## Checkpoint B — governance (PRE-CODE only)", 1)[1]
    assert "candidate" not in b_section.lower()
    assert "optional" not in b_section.lower()
    for rel in DELETE_DATA_PATHS:
        assert rel in task
    for rel in DELETE_MODULE_PATHS:
        assert rel in task


def test_implementation_not_started_legacy_still_present() -> None:
    for rel in DELETE_DATA_PATHS:
        path = _REPO_ROOT / rel
        assert path.is_file(), f"legacy data must remain until implementation: {rel}"
    for rel in DELETE_MODULE_PATHS:
        path = _REPO_ROOT / rel
        assert path.is_file(), f"legacy module must remain until implementation: {rel}"
    for rel in FORBIDDEN_IMPLEMENTATION_ARTIFACTS:
        assert not (_REPO_ROOT / rel).exists(), f"implementation artifact must not exist yet: {rel}"


def test_legacy_sources_remain_byte_identical_to_governance_pins() -> None:
    for relative, expected in LEGACY_SHA256.items():
        path = _DEMO / relative
        assert path.is_file()
        assert _sha256(path) == expected
    assert len(list((_DEMO / "pricebook/services").glob("*.json"))) == 21


def test_target_bundle_strict_loadable_and_checkpoint_a_loader_present() -> None:
    from contracts.response_schema import ResponseSchemaBundle
    from core.response_schema_loader import load_response_schema_bundle

    bundle = load_response_schema_bundle(_DEMO / "target_response")
    assert isinstance(bundle, ResponseSchemaBundle)
    assert len(bundle.services) == 21
    assert len(bundle.offers) == 31
    assert len(bundle.facts) == 6
    assert (_REPO_ROOT / "core/target_client_data.py").is_file()
    assert (_REPO_ROOT / "core/target_query_cues.py").is_file()


def test_frozen_artifact_guards_unchanged() -> None:
    test_frozen_retry4_artifacts_unchanged_after_closeout()
    test_w1b_snapshot_checksums_unchanged()
    test_pscn_frozen_pins_unchanged()
    turns_path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    assert sha256_file_hex(turns_path) == FROZEN_TURNS_HASH
    assert_frozen_retry4_live_artifacts_unchanged()


def test_governance_allowlist_paths_exist() -> None:
    for rel in (
        "TASK.md",
        "docs/evidence/client_pack/FINAL_CLIENT_PACK_DATA_CONVERGENCE_B_SEAM_AUDIT.md",
        "docs/FLAGS_AND_STATUS.md",
        "tests/test_final_client_pack_data_convergence_b_governance.py",
    ):
        assert (_REPO_ROOT / rel).is_file()


def test_task_lists_match_governance_test_constants() -> None:
    assert len(DELETE_DATA_PATHS) == DELETE_DATA_COUNT
    assert len(DELETE_MODULE_PATHS) == DELETE_MODULE_COUNT
    task = _TASK.read_text(encoding="utf-8")
    acceptance_rows = len(re.findall(r"^\| \d+ \|", task, flags=re.MULTILINE))
    assert acceptance_rows >= 16
