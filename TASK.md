# TASK — S50 Offline Harness Correction (Checkpoint B)

**Baseline:** `codex/stage-a` / `f919d05` · **NO LIVE** · **NO LLM**

**Goal:** Fix two confirmed S50 live harness defects offline: narrow audit-proxy
`captures` delegation and post-marker artifact preflight (no `artifact_paths=None`).
Harness reliability only — Verifier false negatives remain open.

**Reference:** `evals/v5/artifacts/s50_live_harness_dirty_audit.patch` (diagnostic only;
do not apply blindly — no broad `__getattr__`, no `artifact_paths=None`).

## Owner decisions (binding)

1. S50 live artifacts, incident manifest/doc/patch — **frozen**, byte-identical.
2. **NO LIVE** / **NO LLM** / **NO rerun** proposal.
3. Product Composer/Verifier/runtime/UI/A9/authority — **untouched**.
4. `fc_missing_01` / `fc_medical_03` Verifier FN — **not fixed** in this checkpoint.

## Defect 1 — Proxy `captures`

Audit proxies must expose `captures` via **narrow explicit delegation**, not broad
`__getattr__`. `call_count` stays proxy-controlled and synced from backend after calls.

## Defect 2 — Artifact preflight after marker

Sequence for v2 live path:

1. Before marker: assert all future output artifacts **and** marker absent.
2. Exclusive-create marker.
3. After marker: re-check **output paths only**, excluding the created attempt marker.
4. Backend factory runs only after these checks.
5. Final writes remain exclusive-create.

**Forbidden:** `artifact_paths=None` as permanent bypass.

## Allowlist

- `TASK.md`
- `evals/v5/run_fullcontext_response_eval.py`
- `tests/test_fullcontext_response_eval_harness.py`
- `docs/STRANGLER_ROADMAP.md` (completion status only)

Contract changes only if PRE-CODE checker proves necessity (prefer harness-only).

## Protected (must not change bytes/content)

- S47/S50 matrices
- All live raw/result/manifest/marker/log artifacts
- Incident manifest, audit doc, dirty patch
- Composer/Verifier product code
- runtime/UI/A9/authority

## Frozen SHA-256 pins (must stay byte-identical)

| Object | SHA-256 |
|--------|---------|
| v2 live raw | `c78403a8a1a82f472d3665f4893db3fb3fa794a9db254e91611448081be7536c` |
| v2 live result | `273fb2dd7228bd31bb6f981399a77fcdb59336e07e99ba1ccd14005096bc39aa` |
| v2 manifest | `8f61aa9097859337f31fbacf1ebf5d45ce3bee68d3f57955a99aa7a128567b8e` |
| v2 attempt marker | `2d02c1c971e617f4583c86d27360b380d98736c6bbe00b268c8e68a2ace8c64c` |
| s50 log | `76be057b272deffff3275ccd38a33c6e492f86d5b34c369d9e86626e3011cab2` |
| incident manifest | per `f919d05` tree |
| dirty patch | `2322e3fa2b7dac988f200c93406efa13ee1e3be482a1179d77f7a84fac1ee397` |

## Required tests (offline only)

### Proxy captures

- Composer proxy exposes `captures`
- Semantic proxy exposes `captures`
- First full fake case via wrapped factory — no `AttributeError`
- `call_count` and `captures` belong to wrapped backend
- No provider/live calls

### Artifact preflight

- Existing marker blocks before backend (existing test retained)
- Existing raw/result/manifest blocks before backend
- Freshly created marker does not cause false `CONFIG_ERROR`
- Post-marker output preflight remains active
- Factory/captures fake run passes end-to-end
- Owner override alone does not overwrite existing marker or allow provider path

## Test execution

```powershell
$bt = Join-Path $env:TEMP ("pytest-fc-harness-" + [guid]::NewGuid().ToString("n"))
python -m pytest tests/test_fullcontext_response_eval_harness.py -p no:cacheprovider --basetemp=$bt -q
```

- Unique external `--basetemp`
- `-p no:cacheprovider`
- No default v2 artifact paths in tests (use `tmp_path` only)

## Process

1. Governance TASK commit → PRE-CODE checker ✅
2. Implementation
3. Offline pytest
4. COMPLETION checker ✅
5. Completion commit + push `codex/stage-a` → stop

## Acceptance

1. Both harness defects fixed per spec (narrow `captures`; post-marker preflight).
2. No `artifact_paths=None`; no broad `__getattr__`.
3. All new tests pass; frozen artifact SHA pins unchanged.
4. Harness-only scope; Verifier FN explicitly still open.
5. Checkpoint B complete; no live rerun; no product semantic milestone.
