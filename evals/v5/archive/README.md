# Archived eval sets (v4 era)

Не запускаются в CI. Оставлены для истории и diff при переносе кейсов.

| File | Замена |
|------|--------|
| `e2e_smoke.v4.json` | `demo/smoke.json` (24 кейса, drafts/test.md §1) + `demo/risk.json` |
| `implant_golden.v4.json` | Инкрементально → `demo/risk.json` и будущий `demo/golden.json` (§2 drafts/test.md) |

Актуальный runner: `python evals/v5/run_demo_eval.py --client demo`
