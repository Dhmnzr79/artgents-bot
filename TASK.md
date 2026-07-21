# TASK — S11 Demo Target Service Catalog Materialization

**Ветка:** `codex/stage-a`

**Baseline:** `c548423 feat: assemble target service data context S10`

**Серия / checkpoint:** `S11` — материализация полного target-каталога всех 21
demo-услуг в final S1 wire shape и offline-доказательство его целостности.

**Режим:** client data materialization only. Никаких target offers, product consumers,
routes/UI, live/LLM или product authority.

## Цель

Создать `clients/demo/target_response/service_catalog.json`, который:

- содержит все 21 существующие demo-услуги с теми же exact `service_id`;
- хранит только semantic identity услуги: имя, aliases, family/roles, active,
  content ref, coarse selection и semantic options;
- соответствует frozen S1 `TargetService` без отдельной/упрощённой schema;
- сохраняет exact авторские name/aliases/active/MD-связи текущего demo-каталога;
- материализует нормативную минимальную применимость из
  `docs/PRICE_SERVICE_ARCHITECTURE.md`, не превращая её в медицинское назначение;
- исправляет только две уже зафиксированные target-классификации: partial/full
  removable denture и open/closed sinus lift являются options, а не брендами.

S11 создаёт service-side общей связи «описание → цена → врач». Он не переносит цены,
не строит offers и не вызывает S10 на реальном demo pack: target bundle ещё неполон.

## Почему это следующий минимальный scope

S1–S4 уже определили и проверили target response-data contracts/loaders/indexes,
S5–S9 — doctor schema и реальный demo doctor catalog, S10 — pure join по exact
`service_id`. Но S10 пока доказан только на synthetic service/offer data.

Перед переносом price offers нужен один проверенный target service catalog, потому что
каждый будущий offer и каждая doctor-связь обязаны ссылаться на него. Переносить
services и offers одним checkpoint нельзя: legacy units/package/payment-stage data
требуют отдельной точной проекции и checker-review, а S11 не должен принимать эти
решения скрыто.

## Final pack boundary

`clients/demo/target_response/` является изолированным корнем будущего S2 target pack.
S11 создаёт в нём только `service_catalog.json`. Отсутствующие пока
`brand_catalog.json`, `pricebook/**`, `clinic_strategy.yaml` и target `marketing.yaml`
не подменяются пустыми заглушками.

Поэтому S2 `load_response_schema_bundle(...)` намеренно ещё не вызывается на этом
каталоге: fail-closed loader требует полный pack. Следующие отдельные checkpoints
добавят остальные owner-файлы. Current runtime не ищет и не читает этот каталог.

## Затрагиваемые файлы

- `TASK.md`;
- `clients/demo/target_response/service_catalog.json` (new);
- `tests/test_demo_target_service_catalog.py` (new);
- `docs/STRANGLER_ROADMAP.md` — pending `[ ]`, затем `[x]` только после completion
  checker `✅`.

Любой другой файл требует остановки и отдельного решения владельца/Архитектора.

## Protected / вне scope

- существующий `clients/demo/service_catalog.json`, все MD, pricebook, marketing,
  policies, doctor catalog и остальные current client files;
- весь `clients/cesi/**` и `clients/nikadent/**`;
- frozen S1–S10 contracts/loaders/builders/tests;
- target brands, offers, prices, packages, facts, strategy, marketing и CTA;
- преобразователь/adapter/dual-read между legacy и target formats;
- current service/price/doctor loaders, retrieval, caches и client discovery;
- query recognition, TurnFrame/session/follow-up/dialog focus, applicability selector,
  ranking/recommendations и answer composition;
- routes/API/app, prompts, answers, UI/cards и feature flags;
- doctor data, booking, availability, schedule/calendar/CRM;
- protected acceptance/golden/eval fixtures;
- весь A9 design/raw/frozen/harness/evidence и A9 live re-audit;
- live/LLM, merge, `main`, другие ветки и изменение product authority.

## Нормативная форма файла

UTF-8 JSON содержит один top-level mapping без wrapper/version. Keys и их authored
order exact равны текущему `clients/demo/service_catalog.json`. Каждое значение
содержит ровно поля frozen S1 `TargetService`:

```json
{
  "name": "...",
  "aliases": [],
  "family": "...",
  "roles": [],
  "active": true,
  "content_ref": "...md",
  "selection": {"mode": "..."},
  "options": []
}
```

`content_ref` отсутствует только у `tomography`; optional `None` fields semantic options
также не записываются. Никаких legacy `facts`, `response_mode`, `price_key`, `price_ref`, `price_display`,
`concern_ref`, `suggest_refs`, денег, CTA или doctor IDs в target catalog нет.

## Exact transitional projection

Для каждого exact `service_id` из current demo catalog target сохраняет:

- `name` = exact current `title`;
- `aliases` = exact current `aliases`, включая authored order;
- `active` = exact current `active`;
- `content_ref` = `<md_entry_ref>.md`, если current `md_entry_ref` не `null`;
- key `content_ref` отсутствует для `tomography`, где утверждённого MD entry нет;
  validated S1 model при этом имеет `content_ref is None`.

Это read-only migration evidence, а не runtime adapter. Новый acceptance test строит
projection только внутри test module и требует exact parity. После будущего authority
transfer legacy catalog и transitional parity test удаляются отдельным checkpoint.

## Exact family / roles / selection inventory

Нормативная проекция дословно следует таблице «Inventory минимальной применимости demo»
в `docs/PRICE_SERVICE_ARCHITECTURE.md`:

| service_id | family | roles | selection |
|---|---|---|---|
| `tomography` | `diagnostics` | `supporting` | `direct` |
| `professional_whitening` | `aesthetics` | — | `context` |
| `classic` | `implantology` | `protocol` | `scope`; extent `one_tooth`, `few_teeth` |
| `one_stage` | `implantology` | `protocol` | `context`; extent `one_tooth`, `few_teeth`; stage `extraction_context` |
| `all_on_4` | `implantology` | `protocol` | `scope`; extent `full_arch` |
| `all_on_6` | `implantology` | `protocol` | `scope`; extent `full_arch` |
| `temporary_teeth` | `prosthodontics` | `supporting` | `direct`; stage `extraction_context`, `implant_placed` |
| `implant_supported_prosthetics` | `prosthodontics` | — | `scope`; extent `one_tooth`, `few_teeth`, `full_arch`; stage `implant_placed` |
| `caries` | `therapy` | — | `direct` |
| `pulpitis` | `endodontics` | — | `direct` |
| `teeth_treatment` | `therapy` | — | `context` |
| `tooth_extraction` | `surgery` | — | `direct` |
| `periodontitis` | `periodontology` | — | `direct` |
| `aligners` | `orthodontics` | — | `context` |
| `veneers` | `aesthetics` | — | `context` |
| `zirconia_crowns` | `prosthodontics` | — | `scope`; extent `one_tooth`, `few_teeth`; stage `natural_tooth_present`, `implant_placed` |
| `clasp_dentures` | `prosthodontics` | — | `scope`; extent `few_teeth`; stage `natural_tooth_present` |
| `sinus_lift` | `implantology` | — | `context`; jaw `upper`; reported_context `reported_bone_deficit` |
| `zygomatic_implants` | `implantology` | `advanced_protocol` | `context`; extent `full_arch`; jaw `upper`; reported_context `reported_bone_deficit` |
| `pterygoid_implants` | `implantology` | `advanced_protocol` | `context`; extent `few_teeth`, `full_arch`; jaw `upper`; reported_context `reported_bone_deficit` |
| `removable_dentures` | `prosthodontics` | — | `scope`; extent `few_teeth`, `full_arch` |

`—` означает exact empty list. Отсутствующие selection axes не записываются и не
заполняются `null`.

## Semantic options

Только две услуги имеют options в S11.

`removable_dentures` exact order:

1. `option_id: partial`, `name: Частичный съёмный протез`, empty aliases,
   `selection.extent: [few_teeth]`;
2. `option_id: full`, `name: Полный съёмный протез`, empty aliases,
   `selection.extent: [full_arch]`.

`sinus_lift` exact order:

1. `option_id: closed`, `name: Закрытый синус-лифтинг`, empty aliases;
2. `option_id: open`, `name: Открытый синус-лифтинг`, empty aliases.

У этих options `active` и `content_ref` отсутствуют (`None` в S1 model), то есть они
наследуют parent. Sinus option selection отсутствует: бот не выбирает способ процедуры
по coarse patient facts. У всех остальных услуг `options` exact empty.

Option names подтверждаются текущими authored pricebook variant labels, но S11 не
читает варианты как brands и не переносит их цены. Acceptance test проверяет exact
names против двух соответствующих current price files read-only.

## Content-ref integrity

Для каждого non-null `content_ref`:

1. exact файл существует в `clients/demo/md`;
2. S4 `build_response_schema_kb_refs(...)` содержит exact
   `kb:<content_ref>#korotko`;
3. `tomography` является единственным service без content ref.

S11 не расширяет frozen S3 external-ref contract: service `content_ref` остаётся plain
S1 field, а integrity доказывается только real-data acceptance test.

## Protected tests / честность

- новый test читает target catalog, current service catalog, два option source price
  files и demo MD-root только read-only;
- target records валидируются напрямую frozen `TargetService`; новая schema/wrapper не
  создаётся;
- current→target helper существует только в test и сравнивает разрешённую projection;
- family/roles/selection inventory задан независимой expected-константой, а не копируется
  из target output;
- тест не импортирует current runtime loaders/routes/session/price selection;
- source files до/после имеют exact одинаковые hashes;
- frozen tests не меняются; skip/xfail, conditional PASS и runtime mocks запрещены.

## Минимальные acceptance tests

Один compact module доказывает:

1. target JSON strict-decode с reject duplicate keys на любом уровне проходит,
   top-level mapping имеет exact 21 IDs и order; compact synthetic duplicate-key case
   доказывает fail-closed decoder test helper;
2. каждая запись проходит frozen S1 `TargetService.model_validate`, а
   `model_dump(exclude_none=True)` exact равен raw payload;
3. target содержит только S1 service fields и не содержит legacy/price/doctor/UI keys;
4. exact name/aliases/active/content-ref projection совпадает с current catalog;
5. family/roles/selection exact равны нормативной inventory для всех 21 услуг;
6. options exact существуют только у removable dentures и sinus lift, имеют
   нормативные IDs/order/names/selection и не считаются brands;
7. все non-null content refs существуют и имеют exact `#korotko` в S4 KB index;
8. doctor catalog `service_ids` являются subset target IDs, а exact union равен target
   IDs минус clinic-level `tomography`;
9. before/after hashes всех прочитанных real files идентичны;
10. source/AST audit подтверждает отсутствие writes, current runtime/session/A9 imports,
    adapter/normalization и product wiring.

## Verification

До data edits:

1. independent read-only checker читает TASK, current service catalog, two option price
   files, doctor catalog, frozen S1/S4/S5/S8/S10 contracts/tests, architecture docs,
   checklist и guardrails;
2. checker подтверждает final pack boundary, exact 21-service inventory, transitional
   projection, option classification и отсутствие offer/runtime/A9 authority;
3. при `❌`/`❓` TASK исправляется и повторно проверяется до data edits.

После реализации:

1. `.venv/codex312/Scripts/python.exe -m pytest tests/test_demo_target_service_catalog.py -q --basetemp=.pytest_tmp_s11`;
2. `.venv/codex312/Scripts/python.exe -m pytest tests/test_response_schema_contract.py tests/test_response_schema_kb_index.py -q --basetemp=.pytest_tmp_s11_contracts`;
3. `.venv/codex312/Scripts/python.exe -m pytest tests/test_demo_doctor_catalog.py tests/test_service_data_context.py -q --basetemp=.pytest_tmp_s11_neighbors`;
4. `.venv/codex312/Scripts/python.exe scripts/lint_content.py --client demo`;
5. `git diff --check`, `git status --short`, diff only по allowlist;
6. independent read-only checker сначала читает data/test diff, затем сам запускает те
   же команды;
7. live/LLM и полный pytest не запускаются: product consumers не меняются.

## Definition of Done

- один полный target service catalog всех 21 demo-услуг существует в final S1 shape;
- exact current content identity и нормативная minimal selection inventory доказаны;
- partial/full и open/closed представлены как semantic options, не brands;
- content refs и doctor service links целостны;
- target offers/full S2 pack и product wiring честно остаются следующими checkpoints;
- current runtime, answers, routes, UI, session, A9 и authority не изменились;
- roadmap отмечает S11 как offline demo materialization, не product activation;
- checker `✅`, отдельные governance/completion commits и push только в
  `origin/codex/stage-a`, рабочее дерево чистое.
