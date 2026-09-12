# A9R2c model-pin incident capture

**Date:** 2026-07-25  
**Baseline:** `c519dd4` (A9R2c live complete)  
**Scope:** incident documentation only · **NO LIVE / NO LLM**

## Official status

| Field | Value |
|-------|-------|
| Status | **`A9R2C_NOT_VALID_FOR_PLUS`** |
| Plus validation | **false** |
| Rerun A9R2c | **blocked** |
| Frozen artifacts | **byte-identical** (immutable) |
| Official `AUTOMATED_FAIL` / `FAIL` | unchanged |

## Incident facts

| Field | Declared / configured | Observed |
|-------|----------------------|----------|
| Owner-requested model | `qwen3.7-plus` | — |
| Manifest/attempt label | `qwen3.7-plus` | — |
| `config.TURN_PLANNER_LLM_MODEL` at call time | `qwen3.6-flash` | — |
| Provider `llm_usage` model | — | **`qwen3.6-flash` (17/17 calls)** |

**Incident cost:** 17 Flash provider calls consumed under A9R2c namespace. Attempt does **not** validate Plus semantic adherence.

## Root cause

`config.TURN_PLANNER_LLM_MODEL` binds at first `config` import. `configure_live_env()` set `os.environ` after harness/session imports had already loaded `config` with Flash default.

## Frozen artifacts (unchanged)

SHA256 pins in `evals/v5/a9r2c_patient_scope_live_contract.py`. No retroactive rewrite.

## Checkpoint B — A9R2d wiring correction (offline)

New isolated namespace `a9r2d_*` with:

- env/bootstrap before first `config` import (subprocess inner runner)
- pre-marker assert `config.TURN_PLANNER_LLM_MODEL == owner_requested`
- separate `owner_requested_model` / `configured_model` / `provider_observed_models`
- abort on first observed provider model mismatch (`MODEL_MISMATCH`)
- manifest uses `model_provenance`, not owner config alone

**STOP before A9R2d live.**
