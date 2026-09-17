# D2 S1 — исполнимый план замены и проверок

Дата: 2026-09-18. Основание: `cdd35ba` и согласованные D2-решения.
Статус: **подготовлен для Checker; код не менялся и тесты не запускались.**
Этот документ не возвращает отменённые правила старой архитектуры.

## 1. Карта замены

### Одна будущая цепочка

```text
/ask или /ask/stream
  → tenant / request_id / D1R lead-privacy и typed UI protection
  → D1R Composer: один смысловой envelope с частями вопроса
  → response_plan: разрешение данных → frozen plan → renderer → UI
  → typed session store: result/replay + память только финального плана
```

`/ask` и `/ask/stream` используют один turn service. Различается только упаковка
готового результата в JSON или SSE. Model-free допустим только для валидного typed
нажатия, terminal, уже установленного typed state предыдущего D1R turn, либо
локального ввода имени/телефона в уже активном D1R lead-flow (с privacy-нормализацией,
без отправки контакта модели). Свежий свободный текст, включая первичное определение
safety/contacts, понимает модель; локальный код не получает второй смысловой parser.

### Конкретные файлы и ответственность

| Текущий файл / символ | Решение | Новая или сохранённая ответственность | Этап |
|---|---|---|---|
| `app.py::_orchestrate_ask_turn_inner`, `_dispatch_orchestration_json`, `_dispatch_orchestration_sse` | Адаптировать | Сохранить маршруты, бюджет, внешний JSON/SSE и передачу request_id; направить оба endpoint в единый D2 turn service | S3 |
| `orchestration/sales_one_plus_ask_turn.py::orchestrate_sales_one_plus_ask_turn` | Адаптировать | Сохранить tenant, reset, rate/lead gates и current typed UI validation; убрать зависимость обычного free-text от sales-fast runtime | S3 |
| `core/lead_provider_input_privacy.py` и D1R lead/pending flow | Сохранить | Имя/телефон, личная заметка и pending-question остаются вне нового смысла D2; проверка заметки до заявки сохраняется | S3 |
| `core/sales_fast_widget_runtime.py::run_sales_fast_widget_turn` | Вывести из normal free-text пути, затем удалить | Сейчас в одном методе соединены local gate, lexical scope, pre-flash hints, provider, повторная сборка, presentation и session write. Его не расширять D2-условиями | S3/S5 |
| `core/sales_fast_widget_runtime.py::_resolve_sales_context` | Удалить из normal free-text пути | Вызывает четыре параллельных смысловых селектора до модели; в D2 данные выбираются после model envelope | S5 |
| `core/sales_fast_turn_frame.py::project_sales_fast_scope_from_message` | Удалить из normal free-text пути | Regex объёма/челюсти заменяется typed situation в D1R envelope | S2/S5 |
| `core/answer_planner.py::detect_aspects_regex` | Удалить из normal free-text пути | Regex намерения/аспекта заменяется списком частей и aspect IDs модели | S2/S5 |
| `core/sales_fast_service_identity.py::resolve_catalog_service_identity`, `resolve_session_service_for_followup` | Удалить из normal free-text пути | Текстовая услуга/продолжение — model-first reference; session лишь валидирует уже выбранную ссылку и свежесть | S2/S5 |
| `core/target_client_data.py::match_service_from_bundle` | Оставить только как data helper, не вызывать по raw free text | Может валидировать предложенный canonical ID/загружать карточку; не классифицирует сообщение пользователя | S2/S5 |
| `core/exact_sales_resolver.py::resolve_exact_sales_inputs` | Адаптировать как resolver typed refs либо вывести из normal пути | Его допустимая роль — загрузить проверенные tenant data после envelope; он не получает raw message и не выбирает смысл/услугу по словам | S2/S5 |
| `core/clinic_policies_loader.py::match_clinic_policy_key` | Удалить из normal free-text пути | Policy ID выбирает модель из allowlist текущего tenant; код показывает only authored text/UI | S3/S5 |
| `core/resolve_precomposer_selected_offer.py::resolve_precomposer_selected_offer_for_turn` | Удалить из normal free-text пути | Цена выбирается единственным post-composer resolver по scope/ситуации/brand, а не hint до модели | S2/S5 |
| `core/sales_fast_strict_evidence.py::build_pre_flash_prompt_hints` | Удалить из normal free-text пути | Нет pre-model price/scope selection; model получает только допустимый corpus, IDs и свежий контекст | S2/S5 |
| `contracts/request_understanding.py::RequestUnderstandingRequest`, `contracts/one_call_envelope.py`, `core/one_call_envelope_protocol.py::parse_production_envelope_json`, `core/one_call_closed_envelope_validation.py` | Адаптировать | **Единственный canonical semantic contract:** уже упорядоченный `RequestUnderstanding.requests` внутри `OneCallEnvelope`. Дополнить каждую часть typed service/source/situation refs и statement/correction/hypothesis; D1R parser остаётся единственным parser модели | S2 |
| `contracts/response_plan_composer.py`, `core/response_plan_composer_contract.py`, `core/response_plan_composer_executor.py`, `core/response_plan_composer_input.py` | Вывести из normal D2 пути, затем удалить или оставить только migration fixture | Их самостоятельный `parse_response_plan_composer_json` не может стать вторым envelope. Lower plan получает механическую projection уже валидированного D1R `OneCallEnvelope`, без provider call или raw model JSON | S2/S5 |
| `contracts/response_plan_post_composer.py`, `core/response_plan_materialization.py`, `core/response_plan_resolver.py` | Адаптировать и сделать центральными | Per-part data resolution, ownership, cap 3 prices, policy/commercial applicability и frozen plan; это основа нового пути, не отдельный fallback | S2/S3 |
| `core/response_text_renderer.py`, `core/response_ui_projection.py` | Сохранить и адаптировать | Единственный renderer текста и единственная UI projection. After freeze никто не дописывает текст, цены или кнопки | S2 |
| `core/one_call_presentation_pass.py::build_one_call_presentation_result` | Вывести из normal free-text пути, затем удалить | Сейчас содержит post-render sanitizing, auto-marketing/amplifiers, installments и повторные выборы. D2 rules должны жить в resolver/frozen plan, не в последнем pass | S3/S5 |
| `core/one_call_presentation_pass.py::_sanitize_patient_text_for_render` | Удалить из normal free-text пути | Не вырезать предложения regex. T3: при обнаруженном structural violation заменить весь prose-block approved material/failure block | S2/S5 |
| `core/sales_fast_presentation.py::append_automatic_marketing_blocks`, `sales_fast_session_selection` | Вывести из normal free-text пути, затем удалить | D2 promo/CTA/secondary selections идут только из post-composer resolver и frozen plan | S3/S5 |
| `core/one_call_direct_commercial.py::append_direct_commercial_without_duplicates`, `core/one_call_presentation_pass.py::_append_installment_12_if_eligible` | Вывести из normal free-text пути, затем удалить | Цена, рассрочка, гарантия, акции — typed blocks из единственного data owner, без дописывания к готовому тексту | S3/S5 |
| `contracts/response_plan_session.py`, `core/response_plan_session.py`, `core/response_plan_session_store.py` | Адаптировать и подключить | Авторитетная D2 session: tenant+sid, revision, request_id replay, финальный text/UI, focus/situation/UI history. Есть SQLite idempotency store, но он сейчас не HTTP authority | S2/S3 |
| `core/target_runtime_session.py` | Сохранить до доказанной замены, затем вывести из normal D2 пути | Старое in-memory/session поле сейчас пишет после materialization. Нельзя удалить, пока lead/privacy и migration T6 не проверены | S3/S5 |
| `core/target_runtime_widget.py` | Адаптировать | Виджетный payload строится из D2 UI projection; внешний вид и typed refs сохраняются | S3 |
| `core/response_plan_situation_continuity.py` | Адаптировать | Использовать typed situation continuity; заменить текущую freshness в turns на 30-minute inactivity clock; replay не обновляет timestamp | S2/S3 |

### Обязательная C08-проверка старого пути

После S5 тесты real `/ask` и `/ask/stream` подменяют перечисленные legacy symbols
на sentinel, который аварийно завершает тест при вызове:

`project_sales_fast_scope_from_message`, `detect_aspects_regex`,
`resolve_catalog_service_identity`, `resolve_session_service_for_followup`,
`match_service_from_bundle`, `match_clinic_policy_key`,
`resolve_precomposer_selected_offer_for_turn`,
`build_pre_flash_prompt_hints`, `build_one_call_presentation_result`,
`append_automatic_marketing_blocks`, `sales_fast_session_selection`,
`append_direct_commercial_without_duplicates`, `_append_installment_12_if_eligible`
и `_sanitize_patient_text_for_render`.

Это не запрещает технические regex для телефона, имени, PII, request_id или
валидности typed UI. Forbidden — только повторное толкование смысла user free text.
Static import/dependency check добавляется как дополнительное доказательство; один
grep сам по себе не считается доказательством runtime.

### Владельцы памяти и фиксации

| Дельта | Единственный владелец | Когда фиксируется |
|---|---|---|
| active focus / topic / situation | `response_plan_session` | Только commit завершённого D2 plan; correction заменяет факт, hypothesis не меняет |
| shown promo / video / follow-up / CTA refs | `response_plan_session` | Только если ref вошёл в frozen UI/text result |
| prices and conditions used in response | `ResolvedResponsePlan` → `response_plan_session` history | Frozen rows, no catalog reread after renderer |
| `request_id` result and replay | `response_plan_session_store` | Atomic commit result+session delta; same payload replays, altered payload conflicts |
| clarification axis/options and shown typed choices | `response_plan_session` | Commit only from frozen clarify/UI result; click is validated against these exact IDs, never re-understood as free text |
| consecutive garbage count / closed-dialogue state | `response_plan_session` | Commit after each model-classified garbage turn; second consecutive garbage freezes closure until an explicit new-chat/reset action |
| lead/pending/privacy | Existing D1R lead state owner | Separate from normal dialogue; context TTL never erases active lead or contacts |
| external lead effect ID / delivery status | `response_plan_session_store` effect ledger | Persist effect ID/status before carrier call; `core/lead_email.py` carries that effect and never decides blind resend |
| TTL 30 minutes | D2 session read layer with injected clock | `last_user_turn_at` updates only for a newly accepted user turn; replay never changes it |

The current response-plan session uses turn-age policy, not clock time. S2 specifies
its data contract and boundary tests; S3 wires `last_user_turn_at` and tenant setting.
No global, implicit 30-minute constant is introduced.

## 2. Матрица проверок

`Existing` below means the named test proves a related current/isolated property,
not that D2 is already covered. `New` is a proposed D2 test file; all scenario
tests use fixture data and fake backend, not live provider.
Every check whose stage contains `S2` is **unit-only** until S3 connects it to
the real HTTP/SSE boundary; it must not be presented as widget evidence.

| ID | Existing evidence / current limit | Add for D2 (fixture and visible assertion) | Stage |
|---|---|---|---|
| A01 | `test_demo_implant_volume_scope_offline.py::test_broad_implantation_overview_and_scope_quick_replies`, correction tests | New `test_d2_http_price_volume.py::test_broad_direction_price_hypothesis_and_correction`; demo fixture, overview ≤3 + four choice buttons, hypothesis no write, correction write | S2/S3 |
| A02 | `test_demo_d1r_composition_offline.py::test_primary_price_composes_every_requested_part` | New `test_d2_http_price_rules.py::test_direct_service_prices_have_units_conditions_and_no_content_secondary`; veneers/whitening fixture and full payload assertions | S2/S3 |
| A03 | `test_request_understanding_schema_offline.py::test_answered_pain_source_projects_its_video_and_followup` | New `test_d2_http_content_ui.py::test_pain_uses_bound_source_and_never_repeats_secondary`; authored pain wording/ref and two turns | S2/S3 |
| A04 | `test_request_understanding_schema_offline.py::test_answered_warranty_source_projects_its_followup` | New `test_d2_http_warranty.py::test_warranty_source_has_no_conflicting_prose`; direct and continued service fixtures | S2/S3 |
| A05 | `test_demo_d1r_composition_offline.py::test_primary_price_composes_every_requested_part` | New `test_d2_multi_request.py::test_price_plus_pain_answers_both_and_suppresses_content_secondary`; two parts, one price channel | S2/S3 |
| A06 | Existing composition test above only current `primary_price`; it is not separate-service coverage | New `test_d2_multi_request.py::test_vinirs_price_and_implant_warranty_keep_distinct_refs`; two service refs, ambiguous follow-up clarify | S2/S3 |
| A07 | `test_demo_implant_volume_scope_offline.py::test_extent_clarification_unknown_button_exits_without_scope` | New `test_d2_http_price_volume.py::test_unknown_scope_returns_general_answer_without_lead`; no pending lead or repeated clarify | S2/S3 |
| A08 | `test_demo_implant_volume_scope_offline.py::test_service_detour_keeps_reported_need_without_pricing_other_service_from_it` | New `test_d2_situation_continuity.py::test_same_missing_tooth_continues_implant_to_prosthetics`; shared situation, service-specific prices | S2/S3 |
| A09 | `test_demo_implant_volume_scope_offline.py::test_all_on_4_both_jaws_quotes_one_jaw_unit_without_total` | Add parameter to D2 price-volume tests for both jaws and few teeth; one-jaw/per-tooth unit, no multiplication | S2/S3 |
| A10 | `test_demo_implant_volume_scope_offline.py::test_followup_a_skolko_after_full_arch_scope_keeps_arch_prices` | New `test_d2_session_context.py::test_price_followup_clear_vs_ambiguous_vs_expired`; empty/clear/multi-focus and injected clock | S2/S3 |
| A11 | `test_response_plan_session_integration.py::test_shown_promo_memory_reaches_next_materialization` | New `test_d2_marketing_rules.py::test_direct_promos_auto_promos_repeat_and_incompatibility`; active promo fixtures and exact displayed IDs | S2/S3 |
| A12 | `test_demo_d1r_http_offline.py::test_d1r_adult_booking_enters_lead_after_one_call`, `test_situation_intake_http_offline.py::test_situation_submit_moves_to_lead_name` | Preserve tests; new adapter integration assertion that D2 turn does not bypass lead privacy/effect ID | S3 |
| B01 | `test_demo_target_service_catalog.py::test_real_target_catalog_is_strict_complete_s1_wire_data` | New `test_d2_availability.py::test_no_public_unknown_and_authored_not_offered_are_distinct`; three catalog/policy fixtures | S2/S3 |
| B02 | Current `test_sales_one_plus_turn.py::test_local_gate_bypasses_backend_only_for_spam` is legacy behavior only | New `test_d2_spam_and_unknown.py::test_second_consecutive_garbage_closes_until_new_chat`; terminal reset UI and normal repeat remains open | S3 |
| B03 | `test_demo_clinic_policy_authority_offline.py::test_hostile_model_cannot_leak_via_sse` | New `test_d2_terminals.py::test_current_pain_overrides_price_and_has_only_authored_contact`; terminal no promo/CTA/UI | S2/S3 |
| B04 | `test_response_plan_materialization_integration.py::test_comparison_without_price_has_no_price_or_options` | New `test_d2_multi_request.py::test_two_information_parts_pick_first_source_ui`; ready comparison/two materials/missing side fixture | S2/S3 |
| B05 | `test_response_plan_materialization_integration.py::test_exact_service_price_not_replaced_by_cheaper_alternative` | New `test_d2_brand.py::test_brand_price_and_comparison_do_not_substitute_other_brand`; only brand-specific offer/source | S2/S3 |
| B06 | `test_response_plan_materialization.py::test_unsupported_price_modes_are_not_materialized` records an old limitation | New `test_d2_price_modes.py::test_fixed_from_range_no_public_and_family_fallback`; cap 3 and ordered IDs | S2/S3 |
| B07 | Existing scope tests include installed implant but no D2 contract | New `test_d2_situation_continuity.py::test_stage_question_only_when_price_changes`; own tooth/implant/other clinic/multiple zones | S2/S3 |
| B08 | `test_response_plan_materialization.py::test_warranty_proposed_by_selector_not_automatically_materialized` | New `test_d2_marketing_rules.py::test_direct_price_has_only_allowed_commercial_blocks`; promos≤2, installment/guarantee, no amplifier/consultation close | S2/S3 |
| B09 | `test_demo_target_service_catalog.py::test_content_refs_and_doctor_service_links_are_complete` | New `test_d2_directory_and_protocols.py`; approved doctor/service links and actual protocols only | S2/S3 |
| B10 | `test_clinic_policy_resolver_offline.py::test_payment_rule_is_not_invented_when_pack_lacks_it` | New `test_d2_policy_id.py::test_model_policy_id_allowlist_and_ambiguous_policy_clarify`; no lexical trigger selector | S2/S3 |
| B11 | `test_response_plan_situation_continuity.py::test_stale_state_not_inherited` uses turn counts | New `test_d2_session_ttl.py::test_30_minute_boundary_and_replay_do_not_refresh`; injected clock + active lead preservation | S2/S3 |
| B12 | `test_request_understanding_schema_offline.py::test_answered_pain_source_projects_its_video_and_followup` | New `test_d2_ui_projection.py::test_cta_and_two_secondary_slots_and_click_history`; source/default/free CTA and typed clicks | S2/S3 |
| C01 | `test_request_understanding_schema_offline.py::test_raw_substantive_envelope_requires_requests`; `test_one_call_stage4_2_closed_envelope_production.py::test_invalid_envelope_does_not_retry` | Extend the **D1R** parser contract for ordered request parts/null refs; fake backend count exactly 1 or 0 on invalid | S2 unit-only / S3 HTTP+SSE |
| C02 | `test_response_plan_materialization.py::test_optional_marketing_failure_preserves_patient_text` | New `test_d2_part_failure.py`; optional promo omission vs direct promo request and independent part survival | S2 unit-only / S3 integrated failure path |
| C03 | `test_demo_d1r_composition_offline.py::test_model_price_prose_is_not_a_price_source` | New `test_d2_prose_violation.py`; detected foreign money/forbidden block replaces complete prose block with approved/failure block. Live evaluates uncaught semantics later | S2/S3 |
| C04 | `test_response_plan_materialization.py::test_materialization_foreign_client_rejected` | Extend ownership tests for per-part source/policy/UI IDs and stale typed click; no effect/no foreign output | S2/S3 |
| C05 | `test_response_plan_session_store.py::test_idempotent_replay`, `test_response_plan_session_integration.py::test_idempotency_abc_then_replay_a` | Extend to exact HTTP request_id, same-payload SSE replay, changed-payload conflict, concurrent revision and no second provider call | S3 |
| C06 | `test_response_plan_session_store.py::test_transaction_rollback_on_failure` | New `test_d2_effect_delivery.py`; failure before/after result commit and external lead unknown state, no blind resend | S3 |
| C07 | Existing lead/privacy suite, notably `test_d1r_old_booking_cannot_restart_after_failed_turn` | New `test_d2_legacy_migration.py`; old normal context cleared, active lead survives, legacy action updates choice, rollback compatibility fixture | S3/S4 |
| C08 | No current test proves active HTTP avoids sales-fast selectors | New `test_d2_no_legacy_path.py`; sentinel list in §1 against real `/ask` and `/ask/stream`, static dependency assertion | S5 |
| C09 | `test_response_plan_materialization.py::test_frozen_trace_immune_to_bundle_swap`; `test_response_plan_materialization_integration.py::test_blocking_and_streaming_share_same_render_path` | Extend to final response/UI/session snapshot consistency across transports and post-freeze bundle change | S2/S3 |
| C10 | `test_tenant_lead_pending_question_offline.py::test_provider_privacy_strips_contacts` | Preserve and add network-block fixture/call counter for D2 offline tests; ensure one call max normal turn | S2/S3 |

Future test commands are intentionally named only after files exist. The first S2
checkpoint command set is fixed in the next section. No pytest command was run for S1.

## 3. Первый ограниченный checkpoint S2

### Goal

Turn the isolated `response_plan_*` lower path into the first D2 central plan
contract. Its *only semantic input* is a fixture parsed through existing D1R
`OneCallEnvelope.request_understanding.requests`; it never reads a second model
JSON shape. It must resolve two ordered parts of one ordinary message —
**direction price + one information part** — from fixture data:

`«Сколько стоит имплантация и больно ли это?»` → up to three frozen approved price
rows plus approved pain text/source, **no ordinary content video/follow-up** because
price owns the navigation channel. The first proof is pure/isolated with fake model
output. It is deliberately not yet a widget, HTTP, lead, TTL, replay, or live proof.

This is a direction-level capability; no special branch for the literal word
«имплантация» is permitted. The same fixture shape must work for another direction.

### Exact write allowlist

Only these paths may change in S2-C1 without a new preflight and explanation:

```text
contracts/request_understanding.py
contracts/one_call_envelope.py
core/one_call_envelope_protocol.py
core/one_call_closed_envelope_validation.py
contracts/response_plan.py
contracts/response_plan_post_composer.py
contracts/response_plan_materialization.py
core/response_plan_materialization.py
core/response_plan_resolver.py
core/response_text_renderer.py
core/response_ui_projection.py
tests/test_request_understanding_schema_offline.py
tests/test_one_call_stage4_2_closed_envelope_production.py
tests/test_response_plan_materialization.py
tests/test_response_plan_materialization_integration.py
tests/test_d2_multi_request.py                 (new)
tests/test_d2_price_modes.py                   (new, only fixed/from/range/no_public contract fixtures)
```

No write to `app.py`, `orchestration/`, `sales_fast_*`, session stores, policies,
clinic data, widget, lead/privacy or existing full HTTP tests. These belong to S3
or a later S2 checkpoint. If a required behavior cannot be proved without one of
them, stop and report the exact dependency rather than expanding the allowlist.

### Work in dependency order

1. Extend `RequestUnderstandingRequest` in the existing `OneCallEnvelope`, retaining
   D1R terminal normalization and its single `parse_production_envelope_json` path.
   `RequestUnderstanding.requests` is the ordered parts list; each part carries
   only model-owned semantic refs/unknown and prose-source ref. A single-part input
   remains a real one-item list, not a legacy alternate shape. Build a mechanical
   lower-plan projection from that parsed object; do not parse/validate a separate
   `ComposerDecision` or call a second model.
2. Extend response-plan materialization input to preserve part
   boundaries, validate same-tenant source refs, and choose one primary navigation
   channel. Add D2 price modes `fixed`, `from`, `range`, `no_public_price` and
   direction fallback as typed plans; do not use the old fixed-only failure path.
3. Resolve exact price/unit/conditions in frozen blocks. Do not select a protocol,
   multiply prices, import unrelated offer, or append words after render. Mark a
   direct price commercial addition optional only when the user did not ask for it.
4. Render the frozen blocks once; test price suppresses normal content secondary
   UI but preserves allowed single CTA only when a fixture explicitly selects it.
5. Add the listed isolated tests. Existing regression expectations that encode
   fixed-only price limitation must be intentionally replaced by D2 assertions,
   not silently deleted.

### Minimal offline verification after code exists

```text
pytest -q -p no:cacheprovider tests/test_request_understanding_schema_offline.py tests/test_one_call_stage4_2_closed_envelope_production.py tests/test_response_plan_materialization.py tests/test_response_plan_materialization_integration.py tests/test_d2_multi_request.py tests/test_d2_price_modes.py
```

Use the repository's isolated temporary test setup if the named suite requires it.
Network and real provider remain blocked; fake backend asserts one call. No full CI,
browser, or live latency run at this checkpoint.

### S2-C1 exit evidence

- One parser/envelope accepts/rejects ordered D2 parts with strict shape and no
  legacy free-text selector in the new isolated path.
- A01/A05 core mechanics and B06/C01/C02/C03/C04/C09/C10 relevant slices pass in
  fixtures, including frozen price unit/conditions and source-owned pain text.
- The tests prove plan→renderer→UI projection; they explicitly say HTTP, SSE,
  persistence/replay, lead/privacy and browser are **not yet integrated**.
- `git diff --check` and an independent Checker pass. Then exact files only are
  committed and pushed. A PASS does not allow S3 automatically.

## 4. Risks and real blockers

### R1 — D1R holds the parts, lower plan is currently singleton-oriented

Evidence: D1R already parses the ordered `RequestUnderstanding.requests` inside
`OneCallEnvelope`, while separate `contracts/response_plan_composer.py::ComposerDecision`
also holds one service/topic/aspect and has its own parser. It cannot safely represent
A06 and must not become a second meaning contract.

Resolution: S2-C1 extends the existing D1R request type and mechanically projects
that parsed envelope into lower plan data. The separate Composer parser is not in
the C1 write allowlist and is not invoked. This removes the blocker.

### R2 — target lower path has valuable mechanics but old commercial defaults

Evidence: `contracts/response_plan.py::ResponseCaps` and
`core/response_plan_materialization.py` support frozen rows and materialization,
but currently name `automatic_amplifiers`; current sales-fast presentation also
adds amps/installments after it renders. That conflicts with D2-017/018/044/047.

Resolution: S2-C1 introduces D2 typed commercial roles in the central plan and
does not reuse amplifier/service-value behavior for normal D2 responses. Existing
legacy selectors remain untouched until S3/S5, not accidentally called by C1.

### R3 — 30-minute TTL needs a wall clock and response result boundary

Evidence: `contracts/response_plan_session.py::SessionContinuityPolicy` and
`core/response_plan_session.py` measure freshness in turns (`set_at_turn`), while
D2 requires inactivity time. The store already has revision/request id mechanics
but has not been wired to HTTP.

Resolution: C1 documents a typed timestamp field and injected clock tests, but
does not mutate persistence. S3 adds migration/replay integration. No blocker to
central plan C1.

### R4 — T3 cannot promise automatic detection of arbitrary bad Russian prose

Evidence: current `one_call_presentation_pass.py` only detects some monetary
patterns and then sanitizes/replaces text. Structural checks can detect malformed
envelope, forbidden code-owned block/known amount and foreign/missing refs. They
cannot prove every paraphrased false guarantee or medical claim.

Resolution: S2-C1 tests only detected structural violations; it replaces the
whole affected prose block with approved source/failure block. A later approved
live set evaluates semantic quality. No regex sentence deletion.

### R5 — policy source selection has two legacy forms

Evidence: `core/clinic_policies_loader.py::match_clinic_policy_key` reads raw
text, while catalog status/policy material can both describe availability.

Resolution: S3 supplies model-selected policy IDs plus loader validation and T1
ownership checks. This is outside C1's price+pain scope. No blocker to C1.

### Escalation condition for Astra

Ask Astra only if extending `RequestUnderstandingRequest` inside the existing
`OneCallEnvelope` cannot represent ordered parts while retaining the terminal/lead
route contract, or if the lower
response-plan renderer cannot render an approved source block without reopening
post-render mutation. Present the exact conflicting type/route and two options:

1. extend the existing D1R request type with versioned per-part refs; or
2. make a short-lived adapter at the D1R boundary.

Recommendation: option 1. A separate parser or shadow runtime is not allowed.
