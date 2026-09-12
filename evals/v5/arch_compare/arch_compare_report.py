"""Report builders for architecture comparison offline dry-run."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evals.v5.arch_compare.arch_compare_contract import BLIND_VARIANTS, DRY_RUN_DISCLAIMER

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ARTIFACTS_ROOT = _REPO_ROOT / "evals" / "v5" / "artifacts" / "arch_compare"


def artifact_dir_for_attempt(attempt_id: str) -> Path:
    return _ARTIFACTS_ROOT / attempt_id


def build_blind_review_markdown(
    *,
    attempt_id: str,
    dry_run: dict[str, Any],
) -> str:
  """Reviewer-facing markdown without config/model/context leakage."""

  mapping = dry_run.get("blind_variant_mapping") or {}
  lines = [
      f"# Architecture compare blind review — `{attempt_id}`",
      "",
      f"> {DRY_RUN_DISCLAIMER}",
      "",
      "Оцените только **основной patient_text** (варианты A–D). "
      "Точные цены, промо, усилители и CTA показаны отдельно как `unavailable` в offline dry-run.",
      "",
  ]
  scenarios = dry_run.get("scenarios") or []
  for scenario in scenarios:
      scenario_id = str(scenario["scenario_id"])
      lines.append(f"## Сценарий `{scenario_id}`")
      lines.append("")
      variant_to_config = mapping.get(scenario_id) or {}
      turns_by_id: dict[str, list[dict[str, Any]]] = {}
      for row in scenario.get("turns") or []:
          turns_by_id.setdefault(str(row["turn_id"]), []).append(row)
      for turn_id, rows in turns_by_id.items():
          lines.append(f"### Ход `{turn_id}`")
          lines.append("")
          for variant in BLIND_VARIANTS:
              config_id = variant_to_config.get(variant)
              match = next((r for r in rows if r.get("config_id") == config_id), None)
              patient_text = (match or {}).get("patient_text") or "unavailable"
              lines.append(f"- **Вариант {variant}** — patient_text: `{patient_text}`")
          lines.append("")
          lines.append("Точная цена/offer (код): `unavailable`")
          lines.append("Промо (код): `unavailable`")
          lines.append("Усилители (код): `unavailable`")
          lines.append("CTA/UI: `unavailable`")
          lines.append("Полный visible answer: `unavailable`")
          lines.append("")
  return "\n".join(lines)


def persist_dry_run_artifacts(
    *,
    attempt_id: str,
    dry_run: dict[str, Any],
) -> dict[str, Path]:
    out_dir = artifact_dir_for_attempt(attempt_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    result_path = out_dir / "result.json"
    mapping_path = out_dir / "blind_variant_mapping.json"
    review_path = out_dir / "blind_review.md"
    result_path.write_text(
        json.dumps(dry_run, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    mapping_path.write_text(
        json.dumps(
            {
                "attempt_id": attempt_id,
                "mapping": dry_run.get("blind_variant_mapping"),
                "note": "closed mapping — not for reviewer markdown",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    review_path.write_text(
        build_blind_review_markdown(attempt_id=attempt_id, dry_run=dry_run),
        encoding="utf-8",
    )
    return {
        "dir": out_dir,
        "result_json": result_path,
        "blind_variant_mapping_json": mapping_path,
        "blind_review_md": review_path,
    }
