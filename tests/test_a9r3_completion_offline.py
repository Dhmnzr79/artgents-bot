"""A9R3 implementation COMPLETION checker (offline, no LLM)."""

from __future__ import annotations

import importlib
import os

import config
from evals.v5.a9r2_patient_scope_live_contract import assert_frozen_a9r2_live_artifacts_unchanged
from evals.v5 import a9r2b_patient_scope_live_contract as a9r2b_contract
from evals.v5 import a9r2c_patient_scope_live_contract as a9r2c_contract
from tests.test_a9r1_offline_harness import (
    test_a9_v1_v2_matrix_blobs_unchanged as _a9_shadow_blobs_unchanged,
)
from tests.test_ac3_scope_price_flow_offline import test_w1b_snapshot_checksums_unchanged
from tests.test_patient_scope_a9r_matrix_v3_contract import test_a9r_v3_matrix_blob_frozen


def test_runtime_planner_uses_single_default_model() -> None:
    prior = os.environ.get("DEFAULT_LLM_MODEL")
    try:
        os.environ["DEFAULT_LLM_MODEL"] = "qwen3.8-flash"
        importlib.reload(config)
        assert config.TURN_PLANNER_LLM_MODEL == config.DEFAULT_LLM_MODEL == "qwen3.8-flash"
    finally:
        if prior is None:
            os.environ.pop("DEFAULT_LLM_MODEL", None)
        else:
            os.environ["DEFAULT_LLM_MODEL"] = prior
        importlib.reload(config)


def test_frozen_neighbor_artifacts_unchanged() -> None:
    test_a9r_v3_matrix_blob_frozen()
    _a9_shadow_blobs_unchanged()
    test_w1b_snapshot_checksums_unchanged()
    assert_frozen_a9r2_live_artifacts_unchanged()
    a9r2b_contract.assert_frozen_a9r2b_live_artifacts_unchanged()
    a9r2c_contract.assert_frozen_a9r2c_live_artifacts_unchanged()
