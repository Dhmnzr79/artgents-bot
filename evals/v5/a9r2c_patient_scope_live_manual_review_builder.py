"""Build full manual review artifact from A9R2c live result."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evals.v5.a9r2b_patient_scope_live_manual_review_builder import (
    build_manual_review_from_result as _build_from_result,
)
from evals.v5.a9r2c_patient_scope_live_contract import (
    LIVE_MANUAL_REVIEW_ARTIFACT_PATH,
    LIVE_RESULT_ARTIFACT_PATH,
    MEASUREMENT_ID,
    SUITE_ID,
)


def build_manual_review_from_result(result: dict[str, Any]) -> dict[str, Any]:
    payload = _build_from_result(result)
    payload["measurement_id"] = MEASUREMENT_ID
    payload["suite_id"] = SUITE_ID
    payload["reported_context_ruling"] = "diagnostic_only_not_authority_candidate"
    return payload


def write_manual_review_artifact(
    *,
    result_path: Path = LIVE_RESULT_ARTIFACT_PATH,
    output_path: Path = LIVE_MANUAL_REVIEW_ARTIFACT_PATH,
) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    payload = build_manual_review_from_result(result)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload
