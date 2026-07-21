# TASK — S24 Exact Brand Offer Projection

**Ветка:** `codex/stage-a`

**Baseline:** `935b126 feat: project active service offers S23`

**Серия / checkpoint:** `S24` — pure offline-фильтр exact бренда внутри одной уже
выбранной услуги с повторным использованием S23 active/option/strategy projection.

**Режим:** governance + один новый unwired projection module + synthetic/real-data unit
tests + price architecture status. Никаких изменений client data, распознавания текста,
выбора услуги, session/runtime, ответов, routes/UI, authority или live/LLM.

## Owner direction

После завершённого S23 владелец разрешил идти дальше. Ближайший минимальный пробел:
S23 умеет безопасно показать активные offers выбранной услуги и option, но намеренно не
фильтрует их по бренду. Будущему контуру нужен точный ответ на уже разрешённое upstream
уточнение вроде «Nobel»: предложения других брендов и без бренда не должны попасть в
ценовую проекцию.

Demo не имеет live-клиентов. S24 не строит compatibility path для current/legacy
архитектуры и ничего не подключает к локальным ответам.

## Минимальная граница S24

Создать `core/target_brand_offer_projection.py` с pure function, принимающей:

- `ServiceDataContext` S10 для exact уже выбранной услуги;
- `TargetBrandCatalog` S1 из того же уже проверенного bundle;
- `TargetClinicStrategy` S1/S15 и explicit `TargetStrategyMatch`;
- обязательный exact `selected_brand_id`, уже определённый upstream;
- optional exact `selected_option_id` и `explicit_offer_id` с тем же смыслом, что в S23.

Exact public API:

```python
@dataclass(frozen=True, slots=True)
class TargetBrandOfferProjection:
    service_id: str
    selected_option_id: str | None
    selected_brand_id: str
    brand: TargetBrand
    matched_rule_id: str | None
    max_options: int
    offers: tuple[TargetOffer, ...]


def project_target_service_brand_offers(
    service_context: ServiceDataContext,
    brand_catalog: TargetBrandCatalog,
    strategy: TargetClinicStrategy,
    strategy_context: TargetStrategyMatch,
    *,
    selected_brand_id: str,
    selected_option_id: str | None = None,
    explicit_offer_id: str | None = None,
) -> TargetBrandOfferProjection:
    ...
```

Result имеет frozen/slots shell. `brand` — deep copy canonical brand record; offers уже
возвращаются S23 как deep copies. Изменение результата не меняет входные catalog/context,
bundle или strategy.

S24 не получает текст пациента, TurnFrame или A9 patient scope. `selected_brand_id`,
option и explicit offer уже выбраны upstream и передаются явно; checkpoint не получает
product authority.

## Exact algorithm

### 1. S24-only validation

1. `selected_brand_id` обязан быть exact nonblank `str`.
2. ID не strip/case-fold/normalize и обязан exact присутствовать в
   `brand_catalog.brands`.

`TargetBrandOfferProjectionError(ValueError)` хранит public `code` и `value`; message:
`f"{code}: {value!r}"`.

| Условие | `code` | `value` |
|---|---|---|
| brand ID не `str` или blank | `brand_offer_projection_brand_id_invalid` | исходное значение |
| exact brand ID отсутствует в catalog | `brand_offer_projection_brand_not_found` | exact string |

Typed context/catalog/strategy остаются owner-contract inputs. Валидация option и
explicit offer остаётся у S23 и не дублируется.

### 2. Exact brand candidate boundary

1. Из `service_context.offers` в authored order остаются только offers, где
   `offer.brand_id == selected_brand_id`.
2. Generic offers с `brand_id=None`, offers другого бренда и любые похожие строки не
   допускаются.
3. Никакой alias/canonical-name/country/natural-language resolution не выполняется.
4. Если бренд существует в catalog, но у выбранной услуги нет его offers, возвращается
   нормальная пустая projection — без fallback к другому бренду, generic offer, другой
   услуге или вычисленной цене.
5. Inactive offers намеренно остаются во внутреннем отфильтрованном context и затем
   исключаются S23: одна существующая граница владеет active semantics.

### 3. Делегирование S23

Собрать временный `ServiceDataContext` с той же service/doctors и brand-filtered offers,
затем вызвать существующий:

```python
project_target_service_offers(
    filtered_context,
    strategy,
    strategy_context,
    selected_option_id=selected_option_id,
    explicit_offer_id=explicit_offer_id,
)
```

- active service/offer/option filtering полностью принадлежит S23;
- exact option validation, S15 first-match order, priorities, caps и explicit pin также
  полностью принадлежат S23/S15;
- priority map не может вернуть offer другого бренда, без бренда или inactive;
- explicit offer другого бренда получает существующий
  `TargetStrategyResolutionError("strategy_explicit_offer_not_candidate", id)` без
  переупаковки;
- price mode, amounts, currency, billing unit, package, payment stages, fact refs и
  followups не меняются и не пересчитываются;
- result копирует S23 service/option/rule/limit/offers и добавляет exact selected brand ID
  и deep-copied canonical brand record.

## Что S24 сознательно не делает

- не распознаёт бренд/alias/country/group из natural language и не меняет legacy brand
  resolver;
- не выбирает service/family/option/offer и не делает общий service shortlist;
- не проверяет медицинскую применимость и не рекомендует лечение;
- не фильтрует по бюджету и не складывает/умножает цены;
- не выбирает doctors, marketing facts, consultation close или CTA;
- не создаёт ResponseSpec, prompt, FullContext packet или natural-language answer;
- не читает файлы/Markdown/client/session/clock и не меняет shown state;
- не подключается к composer/routes/API/app/UI/config;
- не меняет S1/S10/S15/S22/S23, target/current client data или product authority;
- не меняет/не перезапускает A9 artifacts и не запускает live/LLM.

Brand alias resolution, service shortlist, target session/runtime и response composition
остаются отдельными future checkpoints.

## Затрагиваемые файлы

- `TASK.md`;
- `core/target_brand_offer_projection.py` — new pure offline projection;
- `tests/test_target_brand_offer_projection.py` — new synthetic unit contract;
- `tests/test_demo_target_brand_offer_projection.py` — new read-only demo acceptance;
- `docs/PRICE_SERVICE_ARCHITECTURE.md` — S24 projection/status boundary;
- `docs/STRANGLER_ROADMAP.md` — pending `[ ]`, затем `[x]` только после completion checker `✅`.

Любой другой файл требует остановки и отдельного решения владельца/Архитектора.

## Protected / вне scope

- весь `clients/**`, включая target/current price, service, brand, strategy, marketing,
  MD и doctors;
- весь `contracts/**` и frozen S1/S5/S18/S20 models/validators;
- existing `core/target_offer_projection.py`, S10/S15/S21/S22 modules, loaders и current
  runtime paths;
- service/option/brand recognition, general shortlist, dialog focus и session state;
- ResponseSpec/composer/prompt/FullContext/routes/API/app/UI/config;
- protected golden/eval fixtures;
- A9 design/raw/frozen/harness/evidence и live re-audit;
- live/LLM, merge, `main`, другие ветки и product authority.

## Acceptance tests

### Synthetic projection contract

`tests/test_target_brand_offer_projection.py` обязан доказать:

1. exact API/result fields, frozen+slots shell, tuple offers и detached brand/offer models;
2. invalid/blank/unknown exact brand IDs дают stable S24 errors без normalization;
3. остаются только exact-brand offers; other-brand и unbranded generic исключены;
4. существующий бренд без offer выбранной service даёт empty result без fallback;
5. inactive service/offer и inactive option фильтруются через S23;
6. exact option filter сочетается с exact brand и не добавляет generic/other option;
7. strategy priority не может вернуть отфильтрованный offer;
8. explicit eligible same-brand offer pin-ится, explicit other-brand/unbranded/inactive
   получает existing S15 not-candidate error;
9. fixed/from/range/no-public-price, units, packages, payment stages и followups не
   меняются;
10. repeated calls stateless, inputs не мутируются;
11. implementation imports только stdlib + target contracts + pure S10/S23; нет
    IO/client/session/runtime.

### Real demo acceptance

`tests/test_demo_target_brand_offer_projection.py` обязан read-only доказать:

1. real S2/S5/S10/S15 inputs строятся через frozen boundaries;
2. All-on-4 + exact `nobel_biocare` возвращает только `all_on_4.jaw.nobel`, exact
   428000 RUB/jaw, package/payment stages/followups и canonical brand metadata;
3. All-on-4 + exact `implantium`/`impro` никогда не смешивает бренды и сохраняет exact
   authored money;
4. classic + `nobel_biocare` возвращает только соответствующий one-tooth offer;
5. существующий demo brand у услуги без branded offers даёт empty result, не generic
   price;
6. demo target/current files не меняются; новый module не импортирует runtime/client IO;
7. нет skip/xfail и live/LLM.

### Минимальные соседние regression tests

После target tests запустить только:

- `tests/test_target_offer_projection.py`;
- `tests/test_demo_target_offer_projection.py`;
- `tests/test_service_data_context.py`;
- `tests/test_target_strategy_resolution.py`;
- `tests/test_demo_target_clinic_strategy.py`.

Не запускать full suite, live/LLM и A9 harness/re-audit.

## Checker gates

### Gate 1 — governance, до кода

Read-only checker обязан подтвердить:

- scope действительно только exact brand filtering уже выбранной услуги;
- ownership S23/S15 не дублируется, empty/no-fallback и error contracts однозначны;
- allowlist/protected boundary и tests достаточны;
- нет runtime/authority/A9/live расширения.

До `✅` код/data S24 не писать.

### Gate 2 — completion, до completion commit

После реализации checker обязан подтвердить:

- diff совпадает с TASK и allowlist;
- точный brand boundary и делегирование S23 реализованы без fallback/денежных изменений;
- tests реально прошли без skip/xfail;
- product path/authority/A9/live не затронуты.

## Git protocol

1. Записать этот TASK и pending roadmap.
2. `git diff --check`; governance checker `✅`.
3. Commit `docs: govern exact brand offer projection S24` и push только
   `origin/codex/stage-a`.
4. Реализовать только allowlisted files; запустить target, затем минимальные neighbor tests.
5. `git diff --check`; completion checker `✅`.
6. Commit `feat: project exact brand offers S24` и push только
   `origin/codex/stage-a`.
7. Финал: clean tree и HEAD синхронизирован с `origin/codex/stage-a`.

## Definition of Done

- governance checker `✅` получен до code/data;
- exact brand projection реализована и независимо проверена;
- все target/neighbor tests green без skip/xfail;
- client data/current paths/runtime/authority/A9/live не затронуты;
- roadmap честно отмечает S24 `[x]` только после completion checker;
- два checkpoint commits pushed в `codex/stage-a`;
- рабочее дерево чистое и синхронизировано.
