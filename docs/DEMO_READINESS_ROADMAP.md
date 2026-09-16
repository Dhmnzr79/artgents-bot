# Demo readiness roadmap (variant 2)

| Stage | Goal | Status |
|---|---|---|
| D1 Clinic business policies (regex/heuristic path) | Pediatric / OMS / DMS on `/ask` | **Rejected** — superseded by D1R; evidence `aaf9eaa` |
| **D1R** Model understanding + code-owned rules | `request_understanding`, resolver, composition | **Complete** — merged via PR #18 (`141ce91`) |
| D2 Service and volume authority | Service/family/scope on same understanding | Rules agreed; implementation started on `codex/demo-d2-service-volume` |
| D3 Full mixed answers | Commerce + response plan alignment | Planned — not started |
| D4 Offline acceptance | CI gate for demo path | Planned |
| D5 Live rehearsal | Model + widget (owner budget) | Planned |
| F1–F3 Post-demo | Session memory, unified plan, legacy removal | Planned |

**Sequence note:** D1R is complete; D2 builds on its single model understanding and code-owned authority. D3 remains planned.

**Documents:** `docs/tasks/DEMO_D1R_MODEL_UNDERSTANDING.md` (integration design, checkpoint A → **A1** corrections). `docs/tasks/DEMO_D1_CLINIC_POLICY.md` is historical D1 attempt only.

**Lead/privacy:** D1R design **preserves** existing local name/phone → pending choice → `prepare_lead_pending_provider_question` chain; no new repeat-question UX.

**Next gate:** D2 service/scope implementation and focused offline verification; see `docs/tasks/DEMO_D2_SERVICE_VOLUME.md`.
