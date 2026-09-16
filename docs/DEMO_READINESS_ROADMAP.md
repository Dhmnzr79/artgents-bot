# Demo readiness roadmap (variant 2)

| Stage | Goal | Status |
|---|---|---|
| D1 Clinic business policies (regex/heuristic path) | Pediatric / OMS / DMS on `/ask` | **Rejected** — approach superseded by D1R; evidence commit `aaf9eaa` |
| **D1R** Model understanding + code-owned rules | `request_understanding` in one-call envelope; pure policy resolver; mixed composition | **Design checkpoint A** on `codex/demo-d1-clinic-policy` — implementation checkpoint B pending architect approval |
| D2 Service and volume authority | Unified service / extent / scope on same understanding | Planned — not started |
| D3 Full mixed answers | Commerce composition, response plan alignment | Planned — not started |
| D4 Offline acceptance | Current CI gate for demo path | Planned |
| D5 Live rehearsal | Model + widget with owner budget | Planned (owner approval) |
| F1–F3 Post-demo | Session memory, unified plan, legacy removal | Planned |

**Note:** A small **model-understanding + composition** slice was moved ahead of D2/D3 because clinic rules must bind to structured facts, not substring classifiers. D2/D3 are not complete until their PRs merge.

Documents: `docs/tasks/DEMO_D1R_MODEL_UNDERSTANDING.md` (integration design). Historical `docs/tasks/DEMO_D1_CLINIC_POLICY.md` remains as D1 attempt record only.
