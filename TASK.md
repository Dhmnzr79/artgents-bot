# TASK — S22 Unified Offline Response Evidence Package

**Ветка:** `codex/stage-a`

**Baseline:** `b652d00 feat: select target marketing ingredients S21`

**Серия / checkpoint:** `S22` — pure offline-сборщик единого набора материалов одной
уже выбранной услуги: service/price/doctor context S10, marketing selection S21,
разрешённые commercial facts/external refs и optional consultation close S18.

**Режим:** governance + один новый unwired builder + synthetic/real-data unit tests +
architecture status docs. Никаких client-data changes, чтения Markdown, session/runtime,
ответов, routes/UI, live/LLM или product authority.

## Owner direction

21 июля 2026 владелец разрешил следующий отдельный offline checkpoint после S21:
собрать единый проверяемый пакет материалов для будущего ответа. Пакет должен сохранять
общую связку «услуга → её цены → её врачи», добавлять выбранные S21 marketing ingredients
и включать `consultation_value` только по exact документу и только при наличии места в
обоих лимитах.

Demo не имеет live-клиентов. S22 не создаёт compatibility path для current/legacy
архитектуры и ничего не подключает к локальным ответам.

## Минимальная граница S22

Создать `core/target_response_evidence.py` с pure function, принимающей только явно
переданные already-validated target models и snapshots:

- `ResponseSchemaBundle`;
- `TargetDoctorCatalog`;
- `ResponseSchemaExternalIndex`;
- ordered `Sequence[ServiceConsultationValue]`;
- exact уже выбранный `service_id`;
- optional exact `selected_content_ref` выбранного service/option документа;
- exact `semantic_context`, explicit `today`, флаг initial block и requested scenarios;
- read-only shown snapshots S21;
- отдельный флаг automatic consultation close и read-only shown consultation refs.

Builder обязан вызвать S10 и S21 с **одним и тем же exact `service_id`**. Поэтому
marketing result другой услуги невозможно передать как готовый несовместимый объект.

Exact public API:

```python
@dataclass(frozen=True, slots=True)
class TargetResponseEvidencePackage:
    service_context: ServiceDataContext
    selected_content_ref: str | None
    marketing_selection: TargetMarketingSelection
    commercial_facts: tuple[TargetCommercialFact, ...]
    external_source_refs: tuple[str, ...]
    consultation_close: ServiceConsultationValue | None
    marketing_slots_used: int
    amplifier_slots_used: int


def build_target_response_evidence_package(
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    external_index: ResponseSchemaExternalIndex,
    consultation_values: Sequence[ServiceConsultationValue],
    *,
    service_id: str,
    selected_content_ref: str | None,
    semantic_context: str,
    today: date,
    include_initial_block: bool,
    include_consultation_close: bool,
    marketing_scenarios: Sequence[str] = (),
    shown_fact_ids: Sequence[str] = (),
    shown_amplifier_refs: Sequence[str] = (),
    shown_consultation_value_refs: Sequence[str] = (),
) -> TargetResponseEvidencePackage:
    ...
```

Result meaning:

- `service_context` — deep-detached S10 context: exact service, все authored offers этой
  услуги и все связанные doctors в authored catalog order;
- `marketing_selection` — exact S21 result для той же услуги;
- `commercial_facts` — deep copies только выбранных `fact:<id>`, в порядке их появления
  в `marketing_selection.selected_refs`;
- `external_source_refs` — выбранные `kb:`/`doctor:` refs, в том же относительном порядке;
- `consultation_close` — отдельное optional source-owned значение exact выбранного
  документа; оно не маскируется под `SourceRef` и не добавляется в S21 tuples;
- slot counts показывают итоговую занятость после optional consultation close;
- result имеет frozen/slots shell и tuple collections; вложенные Pydantic records
  deep-detached от inputs. Builder не изменяет входные models/sequences.

`service_context.offers` намеренно содержит все authored offers и сохраняет их
`active`/selection flags. S22 **не** утверждает, что каждую позицию можно показывать,
не фильтрует и не ранжирует цены. Future eligibility/strategy projection остаётся
отдельной ответственностью. То же относится к ранжированию врачей: S22 возвращает всех
врачей с exact service link, а не выбирает «лучшего».

## Exact algorithm

### 1. Базовая связка одной услуги

1. Вызвать `build_service_data_context(bundle, doctor_catalog, service_id)`.
2. Ошибки S10 `ServiceDataContextError` распространяются без изменения.
3. Builder не читает service/profile Markdown и не выбирает offer/doctor.

### 2. Marketing selection той же услуги

Вызвать `select_target_marketing(...)` с тем же exact `service_id` и без изменения всех
S21 inputs. Ошибки S21 `TargetMarketingSelectionError` распространяются без изменения.
S22 не повторяет и не ослабляет active/date/service/shown/conflict rules S21.

### 3. Consultation input boundary

После успешных S10 и S21:

1. `consultation_values` обязан быть non-string ordered `Sequence`; каждый элемент —
   exact `ServiceConsultationValue` instance.
2. Duplicate `content_ref` запрещён.
3. На скопированном tuple обязательно вызывается S18
   `validate_service_consultation_refs(records, bundle.services)`; orphan refs fail closed
   через существующий `ServiceConsultationRefError` без переупаковки.
4. `selected_content_ref` — `None` либо exact valid S18 content ref. При непустом
   значении ref обязан принадлежать exact выбранной услуге: её `service.content_ref` или
   одному из её `option.content_ref`.
5. `include_consultation_close` обязан быть exact `bool`.
6. `shown_consultation_value_refs` — non-string ordered Sequence valid S18 content refs
   без duplicate. Snapshot может содержать ref, которого уже нет в текущем списке
   values; это допустимо и не требует скрытой очистки session.

S22 не normalizes/strip/case-fold IDs или refs.

### 4. Exact consultation close rule

`consultation_close` включается только когда одновременно истинны все условия:

1. `include_consultation_close is True`;
2. `selected_content_ref is not None`;
3. в `consultation_values` есть record с exact тем же `content_ref`;
4. exact ref отсутствует в `shown_consultation_value_refs`;
5. после S21 `len(selected_refs) < max_marketing_facts_per_turn`;
6. после S21 `len(amplifier_refs) < max_amplifiers_per_turn`.

При включении consultation close занимает ровно **один marketing slot и один amplifier
slot**. При отсутствии любого условия результат `None`, оба итоговых counts остаются
равны S21 counts, а другой consultation ref не подставляется.

Сборщик не изменяет shown snapshot и не помечает ref показанным. Future session может
сделать это только после фактического включения в ответ. Direct question о пользе
консультации остаётся основным content answer и не моделируется automatic close S22.

### 5. Materialization selected refs

Для каждого ref в `marketing_selection.selected_refs`, сохраняя exact порядок:

- `fact:<id>` превращается в deep copy `bundle.facts[id]` и добавляется в
  `commercial_facts`;
- `kb:` и `doctor:` остаются exact strings в `external_source_refs`;
- неизвестного типа быть не может после validated S1/S20/S21 boundary.

Builder не загружает тела KB/doctor Markdown. Exact ref остаётся указателем на
source-owned материал, а doctor basics уже присутствуют в `service_context.doctors`.

## Stable own errors

`TargetResponseEvidencePackageError(ValueError)` хранит public fields `code` и `value`;
message: `f"{code}: {value!r}"`.

| Условие | `code` | `value` |
|---|---|---|
| consultation values не non-string `Sequence` или первый элемент не `ServiceConsultationValue` | `evidence_consultation_values_invalid` | container или первый offending element |
| duplicate consultation `content_ref` | `evidence_consultation_content_ref_duplicate` | скопированный tuple refs |
| selected ref не `None` и не valid exact S18 content ref | `evidence_selected_content_ref_invalid` | исходное значение |
| valid selected ref не принадлежит exact service/option | `evidence_selected_content_ref_not_owned` | exact ref |
| consultation flag не exact `bool` | `evidence_include_consultation_close_invalid` | исходное значение |
| shown refs не non-string `Sequence` или первый элемент не valid exact S18 content ref | `evidence_shown_consultation_ref_invalid` | container или offending element |
| duplicate shown refs | `evidence_shown_consultation_ref_duplicate` | скопированный tuple |

Validation precedence:

1. S10 service boundary;
2. S21 inputs в его зафиксированном порядке;
3. consultation values container/items/duplicates, затем S18 cross-ref;
4. selected content ref grammar, затем ownership;
5. consultation flag;
6. shown consultation refs container/items/duplicates.

`Sequence` означает tuple/list и другие ordered non-string sequences; `str`, `bytes`,
mapping и set отклоняются. Existing typed bundle/catalog/index и их cross-ref acceptance
не дублируются собственной error table S22.

## Что S22 сознательно не делает

- не определяет service, patient scope, semantic context или marketing scenarios из текста;
- не выбирает применимые/приоритетные offers и не вычисляет цены;
- не ранжирует и не рекомендует врача как «лучшего»;
- не читает client files/Markdown и не формирует fullcontext/prompt/reply;
- не копирует wording incompatibility или placement instructions в generated text;
- не применяет manual-contact, lead/refusal, safety или UI gates;
- не создаёт/не читает/не меняет session state;
- не подключается к ResponseSpec/composer/routes/API/app/UI/config;
- не меняет current/target client data, frozen contracts или S10/S18/S21;
- не меняет A9, product authority и не запускает live/LLM.

## Затрагиваемые файлы

- `TASK.md`;
- `core/target_response_evidence.py` — new pure offline builder;
- `tests/test_target_response_evidence.py` — new synthetic unit contract;
- `tests/test_demo_target_response_evidence.py` — new read-only real-data acceptance;
- `docs/PRICE_SERVICE_ARCHITECTURE.md` — S22 package/status boundary;
- `docs/MARKETING_SCENARIO_ARCHITECTURE.md` — consultation slot/package status;
- `docs/STRANGLER_ROADMAP.md` — pending `[ ]`, затем `[x]` только после completion
  checker `✅`.

Любой другой файл требует остановки и отдельного решения владельца/Архитектора.

## Protected / вне scope

- весь `clients/**`, включая current/target JSON/YAML/MD, doctors, pricebook, marketing;
- весь `contracts/**`, включая frozen S1/S3/S5/S18/S20 contracts/validators;
- existing `core/service_data_context.py`, `target_marketing_selector.py`, loaders,
  strategy/current runtime paths;
- изменение S10 authored-order/all-record law, S18 cadence/value data или S21 selection;
- offer eligibility/strategy selection, dialog focus и patient-scope extraction;
- session persistence/TTL/client resolver/cache/shown-state mutation;
- ResponseSpec/evidence composer/prompt/FullContext/routes/API/app/UI/config;
- protected golden/eval fixtures;
- A9 design/raw/frozen/harness/evidence и live re-audit;
- live/LLM, merge, `main`, другие ветки и product authority.

## Acceptance tests

### Synthetic builder contract

`tests/test_target_response_evidence.py` обязан доказать:

1. exact API/result fields, frozen+slots dataclass, tuple collections и честная
   deep-detachment boundary без заявления о frozen nested Pydantic records;
2. один exact service управляет одновременно S10 context и S21 selection;
3. service/offers/doctors сохраняют S10 authored order/flags и deep-detached от inputs;
4. selected refs детерминированно разделяются на copied commercial facts и external refs
   без изменения exact order S21 result;
5. service-level и option-level selected content refs принимаются, `None` разрешён;
6. invalid/unowned/cross-service selected refs fail closed stable errors;
7. consultation close при свободных slots занимает exact 1 marketing + 1 amplifier;
8. отсутствие value, shown ref, false flag и `None` selected ref независимо suppress close;
9. полный marketing slot и полный amplifier slot независимо suppress close;
10. invalid/duplicate values и shown snapshots дают exact stable error/code/value;
11. orphan consultation record отклоняется существующим S18 cross-ref validator;
12. S10/S21 typed errors распространяются без изменения и соблюдается precedence;
13. repeated calls stateless, input models/sequences/snapshots не меняются;
14. imports только stdlib/Pydantic target contracts и pure S10/S21; нет IO, client,
    session, runtime, LLM или product imports.

### Real demo acceptance

`tests/test_demo_target_response_evidence.py` обязан read-only доказать:

1. real S2/S4/S5/S6/S18/S20 boundaries строят explicit validated inputs;
2. exact `all_on_4` package содержит одну service, все её authored offers и только
   doctors с exact service link;
3. neutral `service` call без initial/scenarios включает real All-on-4 consultation
   value и считает 1/1 slots;
4. exact shown consultation ref suppresses close без замены;
5. `cost + price + all_on_4` даёт S21 2 marketing / 2 amplifiers и поэтому **не**
   включает consultation close, хотя один общий marketing slot ещё свободен;
6. selected fact records/external refs точно соответствуют S21 selection;
7. source/current/target files не меняются;
8. no product imports/writes/skip/xfail/live/LLM.

## Verification

До implementation:

1. этот TASK + roadmap pending коммитятся отдельно и push только в `codex/stage-a`;
2. independent read-only checker читает TASK, S10/S18–S21 contracts/data/tests,
   architecture, checklist/guardrails;
3. checker подтверждает ownership, slot math, validation precedence, no-selection и
   no-runtime/no-authority boundary;
4. при `❌`/`❓` governance исправляется и проверяется повторно до code.

После implementation:

1. `.venv/codex312/Scripts/python.exe -m pytest tests/test_target_response_evidence.py tests/test_demo_target_response_evidence.py -q --basetemp=<temp>/s22-target`;
2. `.venv/codex312/Scripts/python.exe -m pytest tests/test_service_data_context.py tests/test_service_consultation_source.py tests/test_target_marketing_selector.py tests/test_demo_target_marketing_selection.py -q --basetemp=<temp>/s22-neighbors`;
3. `git diff --check`, exact allowlist, no skip/xfail, no full pytest;
4. independent completion checker повторяет review/tests;
5. roadmap `[x]`, completion commit/push only `codex/stage-a`, tree clean/synced.

## Definition of Done

- pure builder детерминированно собирает one-service evidence package из S10/S18/S21;
- service/price/doctor link и exact marketing materialization проверены independently;
- consultation close соблюдает exact document/session cadence snapshot и оба 3/2 slots;
- никакого offer/doctor selection, IO, text generation, session/runtime/product wiring;
- current/target client data, frozen contracts, A9 и authority не меняются;
- independent governance и completion reviews `✅`;
- commits/push только `codex/stage-a`, working tree clean и HEAD synced with origin.
