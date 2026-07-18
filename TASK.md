# TASK — S1 Target Schema Models and Deterministic Validation

**Ветка:** `codex/stage-a`

**Baseline governance:** `4251918 docs: materialize response data schema`

**Серия / checkpoint:** `S1` — модели и детерминированные валидаторы новой схемы без
подключения к ответам бота.

**Режим:** offline contract foundation only. Никаких live/LLM, client migration,
loaders, selectors, route/UI wiring или product authority.

## Цель

Материализовать минимальный типизированный контракт для source-owned данных target-схемы
из `docs/PRICE_SERVICE_ARCHITECTURE.md` и
`docs/MARKETING_SCENARIO_ARCHITECTURE.md`:

- каталог услуг и semantic options;
- brand dictionary;
- pricebook offers с четырьмя состояниями цены;
- commercial facts;
- коммерческий порядок clinic strategy;
- ссылочную marketing policy;
- детерминированную проверку связей этих объектов в одном in-memory bundle.

S1 доказывает только, что будущие данные можно строго представить и проверить. Он не
читает `clients/**`, не переносит demo-данные и не выбирает, что показывать пациенту.

## Почему scope минимален

В S1 входят только persisted authoring contracts, у которых уже зафиксированы владельцы
и нормативные поля. Не входят runtime/session contracts, потому что они требуют
отдельных решений о loading, state lifecycle и product wiring. Не моделируются KB,
doctor и CTA/tone content: в S1 policy хранит только typed refs, а существование внешних
KB/doctor refs будет проверять будущий client-pack loader с соответствующими индексами.

Один новый модуль предпочтительнее набора преждевременных пакетов: схема ещё не
подключена, а единый aggregate validator должен видеть межфайловые ссылки. Разделение
модуля допускается только новым TASK после появления реальных loaders/consumers.

## Затрагиваемые файлы

- `TASK.md`;
- `contracts/response_schema.py` (new);
- `tests/test_response_schema_contract.py` (new);
- `docs/STRANGLER_ROADMAP.md` — только краткий статус S-series и честная отметка S1 после
  завершения; A9 status/raw/frozen/live не менять.

Любой другой файл требует остановки и отдельного решения владельца/Архитектора.

## Protected / вне scope

- весь `clients/**`, включая demo JSON/YAML/md и их migration;
- существующие `contracts/pricebook.py`, `contracts/price_offer.py`,
  `contracts/price_brand_aliases.py` и их current-runtime semantics;
- `contracts/__init__.py`: S1 импортируется явно из нового модуля и не меняет общий
  public surface до появления consumer;
- весь `core/**`, orchestration/resolver/composer, prompts, routes, API и widget/UI;
- loaders, filesystem discovery, environment/config flags и feature toggles;
- session-state модель и запись patient facts/history;
- selection, shortlist, price/marketing selector, CTA selector, rendering и source text;
- KB/doctor/CTA/tone models и проверка существования их refs;
- любые regex/classifiers, LLM parsing или второе понимание ситуации;
- protected acceptance/golden/eval fixtures, весь A9 design/raw/harness/evidence;
- live/LLM, merge, `main`, другие ветки и изменение product authority.

## Нормативные модели S1

Все persisted models используют Pydantic v2, `extra="forbid"`, строгие non-empty IDs и
не мутируют входные данные скрытой нормализацией.

### 1. Service catalog

- direct root mapping `service_id -> service` без придуманного wrapper/version;
- service: `name`, `aliases`, `family`, `roles`, `active`, `content_ref`, `selection`,
  `options`;
- option: `option_id`, `name`, optional aliases/active/content_ref/selection;
- family enum ровно из target-doc;
- role enum: `protocol`, `advanced_protocol`, `supporting`;
- selection mode: `scope`, `context`, `direct`;
- coarse fields используют только target enums:
  `extent={one_tooth,few_teeth,full_arch}`,
  `stage={natural_tooth_present,extraction_context,implant_placed}`,
  `jaw={upper,lower}`,
  `reported_context={reported_bone_deficit}`;
- `ServiceSelection`: обязательный `mode`; optional `extent`/`stage`/`jaw`/
  `reported_context` — непустые списки уникальных enum values;
- `OptionSelection`: без `mode`; те же optional coarse fields как непустые списки
  уникальных enum values; полностью отсутствует, если option не уточняет parent;
- вычисление option inheritance и eligibility в S1 не выполняется.

### 2. Brand catalog

- versioned container и словарь `brand_id -> brand`;
- canonical name, country и aliases;
- brand не содержит price, service applicability, priority или medical advantage.

### 3. Offers

- отдельная persisted offer model; общий список offers существует только как поле
  in-memory `ResponseSchemaBundle`, без придуманного wrapper/version;
- stable `offer_id`, `service_id`, optional `option_id`/`brand_id`, `active`;
- discriminated price modes:
  - `fixed`: `amount`;
  - `from`: `min_amount`;
  - `range`: `min_amount` + `max_amount`, где min не больше max;
  - `no_public_price`: только non-empty `approved_text`;
- numeric amount — строгий целый `>= 0`: `bool`, float, decimal-string, NaN/Infinity и
  отрицательные значения запрещены. Это целые source currency units, как в
  канонических примерах и current price contracts; поддержка дробной валюты потребует
  отдельного versioned schema checkpoint;
- numeric modes требуют exact non-empty currency и target `billing_unit`:
  `tooth`, `implant`, `tooth_package`, `jaw`, `both_jaws`, `procedure`, `unit`, `course`;
- никакого вычисления/умножения или переноса суммы между units/packages;
- package хранит source label и ordered includes;
- `fact_refs` остаются текстовыми refs, `followups` — отдельными typed navigation
  records; S1 их не превращает в кнопки и не рендерит.

### 4. Commercial facts

- отдельная persisted fact model с внутренним `id`; общий словарь `fact_id -> fact`
  существует только как поле in-memory `ResponseSchemaBundle`, без придуманного
  wrapper/version;
- source-owned kind/text/render mode/active/active dates/allowed service IDs/detail ref/
  `incompatible_with`;
- даты имеют строгий ISO `YYYY-MM-DD` вид, `active_from <= active_until`;
- `incompatible_with` не получает выдуманного универсального правила и не обязан быть
  симметричным.

Поскольку target-doc пока не закрывает исчерпывающие enums `kind`, `render_mode` и
follow-up `action`, S1 валидирует их как non-empty source-owned IDs, а не придумывает
product taxonomy. Расширение до закрытого enum требует отдельного governance решения.

### 5. Clinic strategy

- versioned model с `default_max_options` в границе 2–3 и ordered rules;
- rule содержит stable ID, typed coarse match, optional max options,
  `service_priorities` и `offer_priorities`;
- `StrategyMatch`: optional scalar `family`, `extent`, `stage`, `jaw`,
  `reported_context`; это отдельная model, она не переиспользует list-valued catalog
  selection и не выполняет matching;
- priority — только конечное целое число; strategy не содержит active, selection,
  money, source text или CTA.

### 6. Marketing policy

- versioned model с limits, initial commercial blocks, scenario rules и CTA key mapping;
- `max_marketing_facts_per_turn <= 3`, `max_amplifiers_per_turn <= 2`,
  `max_scenarios_per_turn <= 2`, amplifier limit не выше общего fact limit;
- scenario IDs ограничены пятью target values;
- source ref сохраняет нормативную строковую wire-форму `fact:<fact_id>`,
  `kb:<doc>#<chunk>` или `doctor:<doctor_id>`; валидатор проверяет разрешённый prefix,
  непустую целевую часть и обязательный непустой `doc`/`chunk` для `kb`, не нормализуя
  и не переписывая исходную строку;
- policy не содержит свободный amplifier/fact text, dates, source eligibility или
  incompatibility.

### 7. Aggregate bundle validator

In-memory `ResponseSchemaBundle` принимает direct service mapping, brand catalog,
список отдельных offers, словарь отдельных facts, strategy и marketing policy и
детерминированно отклоняет:

- несовпадение dict key с внутренним ID там, где внутренний ID нормативно хранится;
- duplicate IDs и duplicate refs внутри одного ordered списка;
- offer с отсутствующим service;
- offer с `option_id`, которого нет внутри указанного service;
- offer с отсутствующим brand;
- offer/fact/strategy/marketing ref на отсутствующий локально принадлежащий объект;
- self-reference в `incompatible_with`;
- strategy priority для отсутствующего service/offer;
- `fact:` marketing ref на отсутствующий commercial fact.

Существование `kb` и `doctor` refs агрегат не проверяет: у S1 нет loaders и индексов этих
владельцев. Валидатор не отбрасывает inactive/expired source и не принимает решения
eligibility — это будущий selector/runtime checkpoint.

## Обязательные invariants

1. Модели target schema имеют отдельные имена и не переопределяют current-runtime
   `Pricebook*`/`PriceOffer`.
2. `extra="forbid"` действует на каждом persisted nested object; отдельный compact
   introspection-test проходит по всем S1 BaseModel classes и проверяет model config.
3. Unknown patient fact не представлен допустимым значением required selection: отсутствие
   поля означает отсутствие ограничения, а eligibility будет отдельной задачей.
4. Protocol, semantic option и brand остаются разными полями/типами.
5. `no_public_price` нельзя сконструировать с numeric amount; numeric price нельзя
   сконструировать без currency/unit.
6. `both_jaws` — самостоятельная единица, не результат `jaw * 2`.
7. Billing unit, package и price никогда не доказывают service applicability.
8. Model/validator не классифицирует текст пациента, не выбирает service и не меняет
   source-owned text.
9. Никакой model construction/validation не читает filesystem, environment, session или
   A9 shadow state.
10. S1 не объявляет target schema активной и не меняет ответы бота.

## Protected tests / честность

- Новый `tests/test_response_schema_contract.py` — implementation unit tests S1, не
  product golden и не разрешение менять существующие acceptance fixtures.
- Все существующие tests/evals/golden protected от правок.
- Запрещены skip/xfail, условные asserts, resnapshot, моки runtime и подмена target под
  текущий вывод.
- Тестовые payloads синтетические: не копируют и не мигрируют `clients/demo`.

## Минимальные acceptance tests

Новый test module должен доказать без параметрического взрыва:

1. один минимальный валидный bundle со всеми шестью источниками проходит;
2. compact model-config audit доказывает `extra="forbid"` для всех S1 BaseModel classes,
   а extra field в representative nested payload отклоняется;
3. service family/mode/coarse enums и option uniqueness строги; list-valued selection
   принимает только непустые уникальные values, `OptionSelection` отклоняет `mode`, а
   scalar `StrategyMatch` отклоняет списки;
4. четыре price modes проходят, а неправильная shape каждого класса, `bool`, float,
   numeric string и отрицательный integer отклоняются;
5. range с `min_amount > max_amount` отклоняется;
6. missing service/option/brand/fact cross-refs отклоняются;
7. duplicate offer/fact/rule IDs, duplicate ordered refs и fact self-incompatibility
   отклоняются;
8. invalid date format/order отклоняется;
9. strategy max и dangling priorities отклоняются;
10. marketing limits, scenario enum и dangling local fact ref отклоняются; неизвестный
    ref prefix, пустой target и `kb:` без непустых doc/chunk отклоняются; валидная
    исходная ref-строка сохраняется без нормализации, а внешние KB/doctor refs
    принимаются без filesystem lookup;
11. import нового contract не импортирует runtime/loader modules и не имеет side effects;
12. A9 types/state не являются входом bundle и не получают authority.

Тесты проверяют наблюдаемые законы и стабильные error tokens, а не полный текст Pydantic
ошибок.

## Verification

До кода:

1. независимый read-only checker читает этот TASK, оба target architecture docs,
   `REVIEW_CHECKLIST.md` и guardrails;
2. checker подтверждает минимальность scope, отсутствие скрытого wiring/A9 authority,
   достаточность normative fields и acceptance laws;
3. при `❌`/`❓` TASK исправляется и повторно проверяется до кода.

После реализации:

1. `python -m pytest tests/test_response_schema_contract.py -q`;
2. `python -m pytest tests/test_pricebook_contract.py tests/test_turn_frame_contract.py -q`
   как два узких соседних regression contracts;
3. `git diff --check`;
4. `git status --short` и проверка diff только по allowlist;
5. независимый read-only checker сначала читает test diff, затем code/doc diff и сам
   запускает те же команды;
6. live/LLM и полный pytest не запускаются: S1 не подключён к runtime, а узкие contract
   tests дают достаточную проверку с меньшим шумом.

## Definition of Done

- новый contract моделирует шесть source-owned частей target schema и их локальные refs;
- отрицательные tests доказывают детерминированные границы без client data/runtime mocks;
- нет imports/reads/writes из loaders, routes, session или A9;
- ответы, маршруты, UI, client packs и authority не изменились;
- roadmap честно отмечает S1 как contract foundation, не как schema activation;
- checker `✅`, отдельные governance/completion commits и push только в
  `origin/codex/stage-a`, рабочее дерево чистое.
