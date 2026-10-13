# Historical references — не требования к нынешнему D2

Срез2026-10-13 по текущей ветке docs/tests cleanup.

Некоторые старые документы пока сохраняют прежний путь, чтобы не ломать
historical test/eval references. Они помечены историческими; исходный текст
и согласованная тогда терминология сохранены только для provenance.
Число references ниже — файлы с упоминанием basename, не доказательство
runtime-достижимости и не число failing tests. Все найденные references этой
группы — tests/evals; core/scripts/deploy для этих basenames references не имеют.

Не мигрировать отменённые механизмы только ради этих проверок. При дальнейшем
удалении: trace импортов/callers → сохраняемый invariant/equivalent current guard
→ удалить obsolete-only assertions или перенести полезную проверку.
Их результаты не сертифицируют нынешний ответ/релиз.

## ARCH_TARGET_DESIGN.md

[Исходник](ARCH_TARGET_DESIGN.md) — 7 reference files.

- `tests/test_final_contact_value_verification_and_marketing_scenario_activation_governance.py`
- `tests/test_final_generic_fullcontext_content_authority_governance.py`
- `tests/test_final_price_only_source_sufficiency_convergence_governance.py`
- `tests/test_final_service_availability_and_clinic_capability_routing_governance.py`
- `tests/test_final_tomography_existing_scan_content_routing_governance.py`
- `tests/test_fullcontext_dialogue_presentation_convergence_governance.py`
- `tests/test_fullcontext_presentation_parity_governance.py`

## ONE_CALL_CACHED_FULLCONTEXT_ARCHITECTURE_LOCK.md

[Исходник](ONE_CALL_CACHED_FULLCONTEXT_ARCHITECTURE_LOCK.md) — 3 reference files.

- `tests/one_call_stage2_fixture.py`
- `tests/test_sales_one_plus_governance.py`
- `tests/fixtures/one_call_stage2_cases.json`

## PATIENT_SCOPE_DESIGN_A9.md

[Исходник](PATIENT_SCOPE_DESIGN_A9.md) — 2 reference files.

- `evals/v5/demo/patient_scope_shadow_matrix.json`
- `evals/v5/demo/patient_scope_shadow_matrix_v2.json`

## MARKETING_TARGET_MIGRATION_AUDIT.md

[Исходник](MARKETING_TARGET_MIGRATION_AUDIT.md) — 1 reference files.

- `tests/test_demo_target_marketing_migration_audit.py`

## ARCHITECTURE_CONVERGENCE.md

[Исходник](ARCHITECTURE_CONVERGENCE.md) — 7 reference files.

- `tests/test_final_contact_value_verification_and_marketing_scenario_activation_governance.py`
- `tests/test_final_generic_fullcontext_content_authority_governance.py`
- `tests/test_final_price_only_source_sufficiency_convergence_governance.py`
- `tests/test_final_service_availability_and_clinic_capability_routing_governance.py`
- `tests/test_final_tomography_existing_scan_content_routing_governance.py`
- `tests/test_fullcontext_dialogue_presentation_convergence_governance.py`
- `tests/test_fullcontext_presentation_parity_governance.py`

## STRANGLER_ROADMAP.md

[Исходник](STRANGLER_ROADMAP.md) — 12 reference files.

- `tests/test_final_adaptive_response_length_budgets_governance.py`
- `tests/test_final_client_pack_content_dedup_and_token_audit_governance.py`
- `tests/test_final_contact_value_verification_and_marketing_scenario_activation_governance.py`
- `tests/test_final_generic_fullcontext_content_authority_governance.py`
- `tests/test_final_local_evidence_package_builder_foundation_governance.py`
- `tests/test_final_multi_level_scoped_context_shadow_governance.py`
- `tests/test_final_price_only_source_sufficiency_convergence_governance.py`
- `tests/test_final_provider_prompt_cache_prewarm_governance.py`
- `tests/test_final_service_availability_and_clinic_capability_routing_governance.py`
- `tests/test_final_tomography_existing_scan_content_routing_governance.py`
- `tests/test_fullcontext_dialogue_presentation_convergence_governance.py`
- `tests/test_fullcontext_presentation_parity_governance.py`

Current release tests: [shared selections](../tests/release/README.md).
Current behavior: [BOT_BEHAVIOR](BOT_BEHAVIOR.md).
Архивирование остальных docs/evidence и useful-test inventory ещё не завершены.
Клиентская база знаний и реальные runtime пути этим индексом не меняются.
