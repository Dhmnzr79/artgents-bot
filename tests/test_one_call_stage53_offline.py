"""Integration tests for Stage 5.3 offline multiclient harness."""

from __future__ import annotations

import pytest

from evals.v5.stage53.one_call_stage53_contract import (
    FROZEN_MATRIX_SHA256,
    LIVE_AUTHORIZED_ATTEMPT_ID,
)
from evals.v5.stage53.one_call_stage53_harness import run_offline_matrix
from evals.v5.stage53.one_call_stage53_matrix import assert_frozen_matrix_unchanged


def test_live_gate_closed() -> None:
    assert LIVE_AUTHORIZED_ATTEMPT_ID is None


def test_offline_matrix_harness_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    assert FROZEN_MATRIX_SHA256
    assert_frozen_matrix_unchanged()
    result = run_offline_matrix(monkeypatch)
    assert result["pass"] is True
    assert result["case_count"] == 46
    assert result["provider_call_total"] == 39
