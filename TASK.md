# TASK — S21 Deterministic Offline Marketing Selection

**Ветка:** `codex/stage-a`

**Baseline:** `91084b2 feat: materialize demo target marketing S20`

**Серия / checkpoint:** `S21` — pure offline-механизм выбора автоматических
source-backed marketing ingredients из уже validated target bundle.

**Режим:** governance + один новый unwired selector + synthetic/real-data unit tests +
architecture status docs. Никаких client-data changes, session storage, ответов,
routes/UI, live/LLM или product authority.

## Owner direction

21 июля 2026 владелец разрешил следующий checkpoint после S20 и подтвердил понятную
роль механизма: он должен брать правила клиники, выбранную услугу и ситуацию пациента,
отбрасывать неприменимые материалы и соблюдать лимиты. Владелец ожидает:

- одинаковые входы всегда дают одинаковый выбор;
- факты другой услуги, неактивные/просроченные предложения и неподходящие врачи не
  попадают в результат;
- механизм не заполняет свободные места нерелевантными фактами;
- результат остаётся набором проверенных материалов, а не готовой репликой;
- до отдельного решения ничего не подключается к ответам demo.

Demo не имеет live-клиентов. S21 не создаёт compatibility path для current marketing.

## Минимальная граница S21

Создать `core/target_marketing_selector.py` с pure function, которая принимает только
явные already-validated inputs:

- `ResponseSchemaBundle` — S1/S2 bundle с policy и commercial facts;
- `TargetDoctorCatalog` — S5 catalog для service links врачей;
- `ResponseSchemaExternalIndex` — explicit available `kb:`/`doctor:` refs;
- exact `semantic_context`;
- optional exact `service_id`, уже выбранный upstream;
- ordered requested `marketing_scenarios`;
- explicit `include_initial_block`;
- snapshots `shown_fact_ids` и `shown_amplifier_refs`;
- обязательную explicit `today: date`.

Exact public API:

```python
@dataclass(frozen=True, slots=True)
class TargetMarketingSelection:
    applied_scenarios: tuple[str, ...]
    selected_refs: tuple[str, ...]
    amplifier_refs: tuple[str, ...]
    cta_key: str


def select_target_marketing(
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    external_index: ResponseSchemaExternalIndex,
    *,
    semantic_context: str,
    service_id: str | None,
    include_initial_block: bool,
    today: date,
    marketing_scenarios: Sequence[str] = (),
    shown_fact_ids: Sequence[str] = (),
    shown_amplifier_refs: Sequence[str] = (),
) -> TargetMarketingSelection:
    ...
```

`TargetMarketingSelection` возвращает:

- `applied_scenarios` в фактически применённом порядке;
- `selected_refs` — общий ordered список автоматических marketing ingredients;
- `amplifier_refs` — ordered subset усилителей;
- `cta_key` — exact context key либо clinic default.

Result invariants:

- каждый selected ref любого типа занимает ровно один marketing slot;
- каждый ref, пришедший из scenario pool, дополнительно занимает ровно один amplifier
  slot;
- `amplifier_refs` — exact ordered subsequence `selected_refs`;
- `selected_refs` состоит сначала из всех amplifiers в фактическом round-robin order,
  затем из initial fill;
- в обоих tuples нет дублей;
- если initial fact уже выбран как amplifier, он остаётся только на своей первой
  позиции и считается одним marketing + одним amplifier slot.

Selector ничего не читает с диска, не знает `client_id/session_id`, не получает
TurnFrame, не вызывает LLM и не меняет переданные models/collections.

## Почему `today` передаётся явно

Selector не использует `date.today()`, system clock или environment. Активность facts
должна быть воспроизводима в тесте и audit. Future caller отдельно передаст текущую дату.
`active_from` и `active_until` включительны: факт активен в обе граничные даты.

## Exact selection algorithm

### 1. Input boundary

- `semantic_context` — exact nonblank string;
- `service_id` — `None` либо exact nonblank existing key из `bundle.services`;
- `today` принимается только при `type(today) is date`; `datetime`, subclasses и любые
  строки отклоняются;
- scenarios/shown inputs — ordered non-string sequences exact nonblank strings без
  дублей;
- scenario values обязаны входить в frozen `MarketingScenario` literal;
- `include_initial_block` обязан быть exact `bool`;
- invalid input получает typed `TargetMarketingSelectionError` со stable code/value;
- selector не выбирает service и не нормализует ID/case.

### 2. Applicable scenarios

1. Requested scenarios рассматриваются в authored request order.
2. Scenario без rule в policy игнорируется.
3. Context допускается только при exact присутствии в
   `rule.allowed_semantic_contexts`; пустой allowed list означает запрет automatic use.
4. После context filtering берутся первые
   `max_scenarios_per_turn` applicable scenarios.
5. Result сохраняет их exact order в `applied_scenarios`.

`applied_scenarios` означает context-applicable rules после scenario cap, выбранные для
рассмотрения. Scenario остаётся в tuple, даже если его pool не дал eligible ref или
`max_amplifiers_per_turn == 0`. При `max_scenarios_per_turn == 0` tuple пуст. Это
diagnostic selection metadata, а не утверждение, что amplifier был показан.

### 3. Amplifier merge

При двух applicable scenarios pools объединяются round-robin:

1. в каждом круге каждый scenario может дать максимум один следующий eligible ref;
2. первый круг идёт в `applied_scenarios` order;
3. внутри каждого pool сохраняется `ordered_amplifier_refs` order;
4. если один pool исчерпан/неприменим, второй может занять оставшийся amplifier slot;
5. одинаковый ref из двух pools выбирается один раз по первому появлению;
6. merge останавливается при любом достигнутом лимите:
   `max_amplifiers_per_turn` или `max_marketing_facts_per_turn`.

В свой ход pool последовательно пропускает ineligible, already-selected и cross-pool
duplicate refs до первого eligible ref. Такой пропуск не расходует slot и не завершает
ход scenario. После одного выбранного ref ход переходит следующему scenario. Если pool
исчерпан, scenario не даёт ref в этом и следующих кругах. Protected synthetic fixture:
оба pools начинаются с одного shared ref; первый scenario выбирает shared, второй в том
же первом круге пропускает duplicate и выбирает свой следующий eligible ref.

Так составное сомнение вроде «боюсь и дорого» по возможности получает по одному
усилителю каждого сценария, а не два материала только первого scenario.

### 4. Candidate eligibility

Для automatic candidate действуют exact gates:

**`fact:<id>`**

- fact гарантированно существует в `bundle.facts` благодаря
  `ResponseSchemaBundle` validation;
- `active is True`;
- explicit `today` не раньше `active_from` и не позже `active_until`;
- пустой `allowed_service_ids` означает общую применимость;
- непустой список требует exact совпадения с переданным `service_id`;
- `fact.id` отсутствует в `shown_fact_ids`;
- full ref отсутствует в `shown_amplifier_refs`, если candidate пришёл из scenario;
- candidate не конфликтует с уже selected fact в любом направлении
  `incompatible_with`; authored order побеждает, более поздний conflicting fact
  пропускается.

**`kb:<doc>#<chunk>`**

- exact ref существует в `external_index.kb_refs`;
- ref отсутствует в `shown_amplifier_refs`.

**`doctor:<id>`**

- exact ref существует в `external_index.doctor_refs`;
- exact doctor существует в catalog;
- при заданном `service_id` врач обязан иметь exact service link;
- при `service_id=None` doctor ref допустим **только** при exact
  `semantic_context == "doctors"`;
- при любом другом context и `service_id=None` doctor ref отбрасывается;
- ref отсутствует в `shown_amplifier_refs`.

Missing/ineligible external `kb:`/`doctor:` marketing candidate просто отбрасывается:
optional overlay не должен ломать основной content/price answer. Selector не заменяет
его похожим фактом. Missing local `fact:` невозможно в validated bundle: это остаётся
fail-closed `ResponseSchemaBundle` validation и не тестируется обходом модели.
Cross-reference validators S3/S6 всё равно остаются обязательной pack acceptance до
product wiring.

### Exact input errors

`TargetMarketingSelectionError(ValueError)` хранит exact public fields `code` и
`value`; message имеет стабильную форму `f"{code}: {value!r}"`.

| Условие | `code` | `value` |
|---|---|---|
| context не `str` или blank | `marketing_semantic_context_invalid` | исходный context |
| service не `None`/`str` или blank | `marketing_service_id_invalid` | исходное значение |
| exact service key отсутствует | `marketing_service_not_found` | exact service string |
| `type(today) is not date` | `marketing_today_invalid` | исходное значение |
| `type(include_initial_block) is not bool` | `marketing_include_initial_block_invalid` | исходное значение |
| scenarios не non-string `Sequence` либо element не exact allowed scenario string | `marketing_scenario_invalid` | container либо первый offending element |
| duplicate scenarios | `marketing_scenario_duplicate` | скопированный tuple |
| shown facts не non-string `Sequence` либо element не nonblank `str` | `marketing_shown_fact_id_invalid` | container либо первый offending element |
| duplicate shown facts | `marketing_shown_fact_id_duplicate` | скопированный tuple |
| shown amplifiers не non-string `Sequence` либо element не valid frozen `SourceRef` string | `marketing_shown_amplifier_ref_invalid` | container либо первый offending element |
| duplicate shown amplifiers | `marketing_shown_amplifier_ref_duplicate` | скопированный tuple |

Validation идёт сверху вниз в порядке signature/table: context, service, date, bool,
scenarios, shown facts, shown amplifiers. Exact case сохраняется; selector ничего не
strip/normalize. Tuple/list принимаются как `Sequence`; `str`, `bytes`, mapping и set
не принимаются. Existing typed bundle/catalog/index валидируются их owner contracts,
а не дублируются в S21 error table.

### 5. Initial commercial fill

Если `include_initial_block is True` и после amplifiers остались marketing slots:

1. используется только block с exact key `semantic_context`;
2. отсутствие block не вызывает fallback на другой context;
3. `ordered_fact_refs` идут сверху вниз;
4. применяются те же fact active/date/service/shown/conflict gates;
5. ref, уже выбранный как scenario amplifier, не дублируется и занимает один общий
   marketing slot;
6. fill останавливается на `max_marketing_facts_per_turn`;
7. неприменимые кандидаты не заменяются данными вне authored block.

`include_initial_block=False` позволяет future caller представить neutral follow-up:
без scenarios selector возвращает пустые ingredient lists, а не прокручивает initial
block повторно.

### 6. CTA

- exact `policy.cta_contexts[semantic_context]` имеет приоритет;
- иначе используется обязательный `policy.cta_contexts["default"]`;
- CTA не входит в `selected_refs`, marketing/amplifier limits;
- S21 предполагает, что S20 CTA-reference validation уже выполнена;
- возврат CTA key не разрешает показывать CTA в manual-contact, spam/off-topic, pure
  clarify, после отказа или внутри lead-flow — эти safety/product gates остаются
  upstream и unwired.

## Slot accounting examples

### Один `cost` scenario для All-on-4

На demo data и дате `2026-07-21`:

1. `fact:installment_12` — amplifier + marketing slot;
2. `fact:implant_same_day_discount` — amplifier + marketing slot;
3. `fact:free_implant_consult` — initial marketing slot;
4. CTA `price` отдельно.

Итого: 3 marketing refs, 2 amplifiers, одна CTA. Дубли scenario/initial не повторяются.

### Professional whitening initial block

Три implantation facts отбрасываются по service eligibility. Остаётся только
`fact:professional_whitening_discount`; пустые места не заполняются другими данными.

### Doctor trust по конкретной услуге

Doctor refs без соответствующего service link отбрасываются. KB refs pool остаются
доступны, если exact source существует. При общем doctors context без service exact
doctor refs разрешены без рейтинга или выбора «лучшего».

## Что S21 сознательно не делает

- не определяет scenario из текста и не добавляет regex/classifier;
- не выбирает/не сохраняет service/dialog focus;
- не отвечает на direct fact question: прямой ответ остаётся основным source content и
  отдельно обходит только repeat suppression;
- не читает и не выбирает S18/S19 `consultation_value`; future evidence assembly
  отдельно проверит оставшиеся 3/2 slots перед consultation close;
- не создаёт session state и не отмечает refs показанными — показ можно записать только
  после фактического включения в будущий ответ;
- не читает тексты KB/facts/doctors и не формирует natural-language output;
- не применяет manual-contact/lead/refusal routing;
- не подключается к ResponseSpec/composer/UI/product path.

## Затрагиваемые файлы

- `TASK.md`;
- `core/target_marketing_selector.py` — new pure offline selector;
- `tests/test_target_marketing_selector.py` — new synthetic unit contract;
- `tests/test_demo_target_marketing_selection.py` — new read-only real-data acceptance;
- `docs/MARKETING_SCENARIO_ARCHITECTURE.md` — S21 algorithm/status boundary;
- `docs/STRANGLER_ROADMAP.md` — pending `[ ]`, затем `[x]` только после completion
  checker `✅`.

Любой другой файл требует остановки и отдельного решения владельца/Архитектора.

## Protected / вне scope

- весь `clients/**`, включая current/target marketing, tone, playbook, MD, doctors,
  pricebook, service/brand/strategy data;
- весь `contracts/**`, включая frozen S1/S3/S5/S20 models/validators;
- existing `core/marketing_policy.py`, `marketing_loader.py`, `response_strategy.py`,
  `service_data_context.py` и все current runtime paths;
- изменение S20 exact order/refs/contexts/CTA map или S18/S19 consultation values;
- TurnFrame/planner extraction/scenario classification;
- session persistence, TTL, client resolver/cache, shown-state mutation;
- direct-question evidence, consultation-close placement и incompatibility copy;
- ResponseSpec/evidence/composer/prompt/FullContext/routes/API/app/UI/config;
- adapters, dual-read, fallback, feature flags и product wiring;
- protected golden/eval fixtures;
- A9 design/raw/frozen/harness/evidence и live re-audit;
- live/LLM, merge, `main`, другие ветки и изменение product authority.

## Acceptance tests

### Synthetic selector contract

`tests/test_target_marketing_selector.py` обязан доказать:

1. single-scenario pool order, amplifier cap и initial fill до общего cap;
2. two-scenario round-robin и fallback при пустом/ineligible pool;
3. context filtering происходит до scenario cap; empty allowed contexts deny automatic;
4. fact active flag, inclusive date range и service eligibility; missing local fact
   отдельно fail-closed отклоняется `ResponseSchemaBundle` без обхода validation;
5. missing external KB/doctor availability skip и doctor
   existence/service-link/general-`doctors` context eligibility, включая отрицательный
   `service_id=None` + non-doctors context;
6. shown fact/amplifier suppression, cross-pool/initial deduplication;
7. bidirectional incompatibility: first authored candidate wins;
8. exact zero/partial limits и отсутствие нерелевантного fill;
9. exact CTA context/default selection вне slot counts;
10. neutral `include_initial_block=False` path;
11. stable typed validation errors для invalid context/service/date/sequences/scenarios;
12. stateless repeated calls, no mutation, frozen/slots result;
13. selector imports only stdlib + target contracts; no IO/client/runtime/session/LLM.

Round-robin acceptance обязательно включает shared-first-ref fixture: второй scenario
пропускает уже выбранный shared ref и в тот же ход даёт свой следующий eligible ref.

### Real demo acceptance

`tests/test_demo_target_marketing_selection.py` обязан доказать:

1. S2/S4/S5/S6/S20 boundaries строят explicit real inputs read-only;
2. All-on-4 cost example возвращает exact 3/2 refs и CTA `price`;
3. professional whitening initial возвращает только применимую скидку;
4. doctor-trust для конкретной услуги не возвращает несвязанных doctors;
5. general doctors context разрешает exact doctor refs и CTA `doctor`;
6. shown refs/date меняют выбор только по exact deterministic rules;
7. source/current/target files не меняются;
8. no product imports/writes/skip/xfail/live/LLM.

## Verification

До implementation:

1. governance TASK + roadmap pending коммитятся отдельно и push только в
   `codex/stage-a`;
2. independent read-only checker читает TASK, S18–S20 data/contracts/tests,
   architecture, checklist/guardrails и existing pure strategy style;
3. checker подтверждает slot math, round-robin, eligibility, no-repeat snapshots,
   conflict handling, CTA and no-runtime/no-authority boundary;
4. при `❌`/`❓` governance исправляется и проверяется повторно до code.

После implementation:

1. `.venv/codex312/Scripts/python.exe -m pytest tests/test_target_marketing_selector.py tests/test_demo_target_marketing_selection.py -q --basetemp=.pytest_tmp_s21_selector`;
2. `.venv/codex312/Scripts/python.exe -m pytest tests/test_demo_target_marketing_policy.py tests/test_marketing_cta_refs.py tests/test_response_schema_refs.py tests/test_doctor_schema_refs.py tests/test_target_strategy_resolution.py -q --basetemp=.pytest_tmp_s21_neighbors`;
3. `git diff --check`, exact allowlist, no skip/xfail, no full pytest;
4. independent completion checker повторяет review/tests;
5. roadmap `[x]`, completion commit/push only `codex/stage-a`, tree clean/synced.

## Definition of Done

- pure selector deterministically returns only eligible automatic refs within 3/2/2;
- exact source/service/date/doctor/no-repeat/conflict gates independently tested;
- S20 target policy/data and frozen contracts unchanged;
- no text generation, session mutation, runtime/product path, A9 or authority changes;
- independent governance and completion reviews `✅`;
- commits/push only `codex/stage-a`, working tree clean and HEAD synced with origin.
