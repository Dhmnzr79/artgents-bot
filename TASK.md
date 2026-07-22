# TASK — S47 Final Correction: Remove Legacy threshold_verdict PASS

**Baseline:** `codex/stage-a` / `365ee90` · clean/synced · NO_LIVE

**Gap:** `evals/v5/fullcontext_response_eval_contract.py` still exports deprecated
`evaluate_threshold_verdict()` — maps `AUTOMATED_PASS` → `PASS` without manual review.
Main harness does not call it; violates S47 rule that full `PASS` requires complete manual review.

**Fix (minimal):**
1. Delete `evaluate_threshold_verdict` from S47 contract entirely.
2. `rg`: no S47 import/call remains.
3. Do **not** touch `medical_boundary_eval_contract.evaluate_threshold_verdict` (S43).
4. Regression test: automated clean → `AUTOMATED_PASS`; final without manual →
   `PENDING_MANUAL_REVIEW`; no S47 public API returns full `PASS` from automated summary alone.

**Forbidden:** matrix/models/thresholds changes; live run; S42–S46 core; S43 contract.

**Allowlist:**
- `TASK.md`
- `evals/v5/fullcontext_response_eval_contract.py`
- `tests/test_fullcontext_response_eval_harness.py`

**Acceptance:** targeted S47 matrix+harness + S46 neighbor green; matrix hash unchanged
`c0b2b4cd364b2013cfbe68651eaf43e8bdb3626c`.

**Gates:** PRE-CODE → governance commit → implement → COMPLETION → push → stop.
