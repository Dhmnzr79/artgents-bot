# Demo readiness roadmap (variant 2)

| Stage | Goal | Status |
|---|---|---|
| D1 Clinic business policies (regex/heuristic path) | Pediatric / OMS / DMS on `/ask` | **Rejected** — superseded by D1R; evidence `aaf9eaa` |
| **D1R** Model understanding + code-owned rules | `request_understanding`, resolver, composition | **B implemented** on `codex/demo-d1-clinic-policy` (pending architect sign-off) |
| D2 Service and volume authority | Service/family/scope on same understanding | Planned — not started |
| D3 Full mixed answers | Commerce + response plan alignment | Planned — not started |
| D4 Offline acceptance | CI gate for demo path | Planned |
| D5 Live rehearsal | Model + widget (owner budget) | Planned |
| F1–F3 Post-demo | Session memory, unified plan, legacy removal | Planned |

**Sequence note:** Model-understanding + composition for clinic rules is ahead of D2/D3 completion; those stages stay **planned** until their PRs merge.

**Documents:** `docs/tasks/DEMO_D1R_MODEL_UNDERSTANDING.md` (integration design, checkpoint A → **A1** corrections). `docs/tasks/DEMO_D1_CLINIC_POLICY.md` is historical D1 attempt only.

**Lead/privacy:** D1R design **preserves** existing local name/phone → pending choice → `prepare_lead_pending_provider_question` chain; no new repeat-question UX.

**Next gate:** architect review of checkpoint **B** on `codex/demo-d1-clinic-policy`; D2 not started.
