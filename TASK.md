# TASK — S10 Target Service Data Context Builder

**Ветка:** `codex/stage-a`

**Baseline:** `ba6f843 data: materialize demo doctor catalog S9`

**Серия / checkpoint:** `S10` — pure read-only сборка target service data context по
одному exact `service_id` из уже проверенных S1 и S5 моделей.

**Режим:** in-memory foundation only. Никаких filesystem/client loaders, query/session,
routes/UI, live/LLM или product authority.

## Цель

Добавить один изолированный builder:

```python
def build_service_data_context(
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    service_id: str,
) -> ServiceDataContext: ...
```

Он по одному exact `service_id` собирает рядом:

- validated `TargetService` с `content_ref` для описания;
- все связанные validated `TargetOffer` с точными price/package/fact/follow-up данными;
- всех связанных врачей с `doctor_id`, именем, должностью, стажем и `profile_ref`.

S10 реализует offline common-context law «описание → цена → врач», но не выбирает
услугу по фразе пациента, не читает MD/JSON, не применяет eligibility/marketing и не
формирует ответ.

## Почему это следующий минимальный scope

S1 уже задаёт target services/offers, S5–S9 — target doctor catalog и его demo data.
Архитектурный закон требует, чтобы короткие продолжения «сколько стоит?» и «кто
делает?» использовали один semantic `service_id`, а не независимо угадывали тему.

Следующий безопасный boundary — pure join уже validated in-memory records. Реальный
demo target service/offer pack ещё не материализован, поэтому S10 использует только
synthetic target models. Отдельный следующий checkpoint сможет материализовать
минимальный demo service/price slice и прогнать его вместе с S9 catalog. Product wiring,
dialog focus и authority идут ещё позже.

## Затрагиваемые файлы

- `TASK.md`;
- `core/service_data_context.py` (new);
- `tests/test_service_data_context.py` (new);
- `docs/MARKETING_SCENARIO_ARCHITECTURE.md` — зафиксировать точную offline S10 boundary
  без заявления product activation;
- `docs/STRANGLER_ROADMAP.md` — pending `[ ]`, затем `[x]` только после completion
  checker `✅`.

Любой другой файл требует остановки и отдельного решения владельца/Архитектора.

## Protected / вне scope

- весь `clients/**`, включая S9 `doctor_catalog.json`, MD, service catalog и pricebook;
- frozen S1–S9 contracts/loaders/index builders/tests;
- изменение `ResponseSchemaBundle`, `TargetDoctorCatalog` или target-pack layout;
- current service/price/doctor loaders и `doctors_lookup.py`;
- filesystem, client discovery/default/fallback/dual-read, caches и feature flags;
- query recognition, semantic resolution, follow-up/dialog-focus и session writes;
- service applicability, strategy, active filtering, offer priority, recommendation,
  ranking и max-options;
- marketing/CTA selection, source-text loading, rendering/composer/verifier;
- routes/API/app, prompts, answers, UI/cards;
- booking, availability, schedule/calendar/CRM;
- protected acceptance/golden/eval fixtures;
- весь A9 design/raw/frozen/harness/evidence и A9 live re-audit;
- live/LLM, merge, `main`, другие ветки и включение product authority.

## Нормативный output contract

Новый `core/service_data_context.py` определяет frozen/slots dataclasses:

```python
@dataclass(frozen=True, slots=True)
class ServiceDoctorContext:
    doctor_id: str
    name: str
    position: str
    experience_years: int
    profile_ref: str

@dataclass(frozen=True, slots=True)
class ServiceDataContext:
    service_id: str
    service: TargetService
    offers: tuple[TargetOffer, ...]
    doctors: tuple[ServiceDoctorContext, ...]
```

`ServiceDoctorContext` намеренно не содержит `active`, расписание, availability,
рейтинг, роль/фазу, CTA или UI data. Стаж всегда присутствует в structured context и
не зависит от отдельного вопроса пациента.

`service` и `offers` являются deep `model_copy` уже validated S1 records. Поэтому
context не разделяет mutable nested state с input bundle. Wrapper dataclasses frozen;
builder не создаёт вторую service/price schema и не повторно валидирует frozen models.

## Exact join law

1. `service_id` обязан быть `str` и не whitespace-only. Иначе
   `ServiceDataContextError.code == "service_id_invalid"`.
2. Значение не trim/lower/normalize. Exact key отсутствует в `bundle.services` →
   `code == "service_not_found"`.
3. `ServiceDataContextError(ValueError)` хранит `code` и исходный `service_id`; текст
   ошибки не является API. Tests обязаны отдельно подтвердить сам class, наследование
   от `ValueError`, exact `code` и exact исходный `.service_id`, включая non-string и
   строки с surrounding spaces.
4. `service` берётся только из exact `bundle.services[service_id]`.
5. `offers` включает все bundle offers с exact `offer.service_id == service_id` в
   authored bundle order.
6. `doctors` включает всех doctors, у которых exact `service_id` присутствует в
   `doctor.service_ids`, в authored catalog mapping order.
7. Doctor entry проецируется только в пять output fields; authored doctor service-list
   order не используется для ranking.
8. Наличие нескольких doctors означает равную data relevance; builder не выбирает
   «лучшего» и не сортирует.
9. `content_ref is None`, empty offers или empty doctors допустимы. Clinic-level
   service без врача не является ошибкой; отсутствие offer означает только отсутствие
   target price record в supplied bundle.
10. `service.active` и `offer.active` копируются дословно, но не фильтруются и не
    трактуются. Eligibility/availability/priority — не S10 authority.
11. Builder не вызывает S6 автоматически и не проверяет KB filesystem: callers должны
    передавать отдельно validated data/indexes.

## Determinism и side-effect invariants

- builder не мутирует `bundle`, `doctor_catalog`, nested records или authored order;
- output service/offers не alias input models благодаря `model_copy(deep=True)`;
- два последовательных вызова независимы, global/cache state отсутствует;
- нет filesystem, environment, network, logging или time/date dependency;
- модуль импортирует только stdlib `dataclasses` и frozen S1/S5 model types;
- нет current product/runtime imports и legacy adapters;
- функция не читает source text, не форматирует деньги и не строит answer/UI;
- S10 не подключается к product path и не меняет A9/product authority.

## Protected tests / честность

- новый `tests/test_service_data_context.py` использует только synthetic valid S1/S5
  payloads;
- `clients/**` не читается и не копируется;
- frozen tests не меняются;
- запрещены skip/xfail, conditional PASS, runtime mocks и snapshot current output.

## Минимальные acceptance tests

Compact module доказывает:

1. exact service context содержит исходный `service_id`, validated service/content ref,
   минимум два полных связанных offer и всех связанных doctors; synthetic offers имеют
   непустые `option_id`, `brand_id`, `fact_refs`, `followups`, authored `active`,
   вложенные `price` и `package`, а test сравнивает exact полный
   `TargetOffer.model_dump()` каждого offer;
2. doctor context всегда содержит exact ID/name/position/experience/profile ref и
   ровно пять полей;
3. обе dataclass имеют exact объявленный набор и порядок полей; introspection доказывает
   `frozen=True`, `slots=True` и отсутствие `__dict__` у instances;
4. offer order и doctor mapping order сохраняются без sorting/ranking;
5. offers/doctors другой услуги не попадают в context;
6. service без content ref/offers/doctors успешно возвращает `None`, `()`, `()`;
7. inactive service/offer остаются в context с authored flags: builder не является
   eligibility selector;
8. non-string и whitespace-only ID дают отдельные `service_id_invalid` cases; unknown,
   case mismatch и surrounding spaces дают отдельные `service_not_found` cases. Каждый
   case проверяет `ServiceDataContextError`, `ValueError`, exact `code` и exact исходный
   `.service_id`; normalization отсутствует;
9. `bundle.model_dump()` и `doctor_catalog.model_dump()` до/после builder идентичны;
   output service/offers имеют другие object identities и их nested mutation не меняет
   ни один input;
10. dataclass wrappers frozen, sequential calls не делят state;
11. source/AST audit подтверждает только allowed imports, отсутствие IO/client/current
    loaders/session/query/selection/rendering/write/cache APIs и отсутствие второй
    service/price schema или `model_validate`.

## Verification

До кода:

1. independent read-only checker читает TASK, S1/S5/S6 contracts/tests, S9 catalog
   acceptance, обе architecture docs, checklist и guardrails;
2. checker подтверждает exact join/output/error laws, experience-by-default, отсутствие
   ranking/active filtering/runtime/A9 authority и честный synthetic-only scope;
3. при `❌`/`❓` governance исправляется и повторно проверяется до кода.

После реализации:

1. `.venv/codex312/Scripts/python.exe -m pytest tests/test_service_data_context.py -q --basetemp=.pytest_tmp_s10`;
2. `.venv/codex312/Scripts/python.exe -m pytest tests/test_response_schema_contract.py tests/test_doctor_schema_contract.py tests/test_doctor_schema_refs.py -q --basetemp=.pytest_tmp_s10_contracts`;
3. `.venv/codex312/Scripts/python.exe -m pytest tests/test_demo_doctor_catalog.py tests/test_response_schema_refs.py -q --basetemp=.pytest_tmp_s10_neighbor`;
4. `git diff --check`, `git status --short`, diff only по allowlist;
5. independent checker сначала читает test diff, затем implementation/docs diff и сам
   запускает те же команды;
6. live/LLM и полный pytest не запускаются: product consumers не меняются.

## Definition of Done

- one exact service ID pure-собирает service description pointer, full price offers и
  doctor contexts с обязательным стажем;
- authored values/order сохраняются, input не мутируется и output не alias input models;
- builder не выполняет selection, eligibility, ranking, source loading или rendering;
- `clients/**`, current runtime, answers, routes, UI, session, A9 и authority не
  изменились;
- architecture docs/roadmap отмечают S10 как offline context foundation, не product
  activation;
- checker `✅`, отдельные governance/completion commits и push только в
  `origin/codex/stage-a`, рабочее дерево чистое.
