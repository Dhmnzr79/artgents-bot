"""Inner live runner for A9R2d (env must be set before interpreter imports repo modules)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from evals.v5 import a9r2d_patient_scope_live_contract as contract  # noqa: E402
from evals.v5.a9r2_patient_scope_live_harness import run_planner_harness  # noqa: E402
from evals.v5.fullcontext_response_eval_contract import (  # noqa: E402
    AttemptMarkerExistsError,
    HarnessConfigError,
    LiveArtifactExistsError,
)
from evals.v5.patient_scope_live_model_pin import assert_planner_model_pin_before_marker  # noqa: E402


def main() -> int:
    try:
        contract.assert_matrix_v1_frozen()
        contract.assert_matrix_v2_frozen()
        contract.assert_matrix_v3_frozen()
        contract.assert_attempt_marker_absent(contract.LIVE_ATTEMPT_MARKER_PATH)
        contract.assert_live_artifacts_absent()
        assert_planner_model_pin_before_marker(contract.OWNER_APPROVED_PLANNER_MODEL)
    except (AttemptMarkerExistsError, LiveArtifactExistsError) as error:
        print(f"PREFLIGHT_BLOCKED: {error}", file=sys.stderr)
        return 4
    except HarnessConfigError as error:
        print(f"CONFIG_ERROR: {error}", file=sys.stderr)
        return 2

    from core.turn_planner_llm import plan_turn_attempt  # noqa: WPS433

    try:
        payload = run_planner_harness(
            planner_fn=plan_turn_attempt,
            contract=contract,
            record_dialog_history=True,
        )
    except HarnessConfigError as error:
        print(f"LIVE_ABORTED: {error}", file=sys.stderr)
        return 5

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["automated_verdict"] == "AUTOMATED_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
