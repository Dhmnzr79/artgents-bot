# TASK — S9 Demo Target Doctor Catalog Materialization

**Ветка:** `codex/stage-a`

**Baseline:** `6f12b16 feat: load strict doctor catalogs S8`

**Серия / checkpoint:** `S9` — материализация одного final-wire
`clients/demo/doctor_catalog.json` для шести утверждённых demo-врачей и offline
доказательство его целостности через S4/S5/S6/S8.

**Режим:** client data materialization only. Никаких current runtime consumers,
routes/UI, live/LLM или product authority.

## Цель

Создать один target-каталог врачей в окончательной S5 JSON-форме и отдельный read-only
acceptance test, который доказывает:

- S8 строго загружает реальный demo-файл;
- все шесть записей дословно соответствуют утверждённым данным;
- transitional MD metadata пока exact совпадает с JSON и не становится production
  loader/adaptor;
- все doctor→service/profile refs проходят S6 на реальном demo service catalog и S4
  KB index;
- `doctor:<id>` refs детерминированны;
- единственная clinic-level услуга без врача — `tomography`.

S9 не подключает каталог к ответам. Он создаёт проверенный источник структурированных
doctor facts, который следующий отдельный checkpoint сможет передать read-only
service-context builder для цепочки «описание → цена → врач» по exact `service_id`.

## Почему JSON и MD временно содержат пересекающиеся поля

Target ownership уже определён:

- JSON владеет `name`, `position`, `experience_years`, `service_ids` и `profile_ref`;
- MD владеет продающим profile text.

Текущие MD ещё содержат legacy/transitional frontmatter и текстовый стаж, потому что
current local product path пока не заменён. В S9 они не считаются вторым target source:
их читают только acceptance tests как migration evidence. Exact parity test не даёт
копиям разойтись.

Удаление структурированных frontmatter-дублей и числового стажа из MD разрешается
только после отдельного доказанного answer-context/product-wiring checkpoint, где
JSON-стаж автоматически присутствует в каждом doctor answer. S9 ничего не сохраняет
ради live-клиентов; это ограниченная последовательность миграции до готовой замены.

## Затрагиваемые файлы

- `TASK.md`;
- `clients/demo/doctor_catalog.json` (new);
- `tests/test_demo_doctor_catalog.py` (new);
- `docs/STRANGLER_ROADMAP.md` — pending `[ ]`, затем `[x]` только после completion
  checker `✅`.

Любой другой файл требует остановки и отдельного решения владельца/Архитектора.

## Protected / вне scope

- все существующие `clients/demo/**`, включая doctor MD, overview, service catalog,
  pricebook, marketing и policies;
- весь `clients/cesi/**` и `clients/nikadent/**`;
- frozen S1–S8 contracts/loaders/index builders/tests;
- S2 target-pack layout и `ResponseSchemaBundle`;
- `doctors_lookup.py`, current loaders, retrieval, routing/orchestration и caches;
- client discovery/default/fallback/dual-read и feature flags;
- service→price→doctor context builder, selection, recommendation/ranking и rendering;
- query recognition, follow-up/session logic, prompts, answers, CTA, UI/cards;
- booking, availability, schedule/calendar/CRM;
- protected acceptance/golden/eval fixtures;
- весь A9 design/raw/frozen/harness/evidence и A9 live re-audit;
- live/LLM, merge, `main`, другие ветки и включение product authority.

## Нормативный demo catalog

`clients/demo/doctor_catalog.json` — UTF-8 JSON с единственным top-level key
`doctors`. Порядок doctor keys лексикографический и фиксирован:

1. `doctors__doctor__fedorova`;
2. `doctors__doctor__grigoriev`;
3. `doctors__doctor__kuznetsov`;
4. `doctors__doctor__morozova`;
5. `doctors__doctor__orlov`;
6. `doctors__doctor__volkov`.

Каждая запись содержит ровно пять обязательных S5-полей, без extras.

### Фёдорова

- `name`: `Фёдорова Ирина Михайловна`;
- `position`: `Врач-стоматолог-терапевт`;
- `experience_years`: `16`;
- `service_ids` exact order: `caries`, `pulpitis`, `teeth_treatment`,
  `professional_whitening`, `veneers`, `zirconia_crowns`;
- `profile_ref`: `kb:doctors__doctor__fedorova.md#korotko`.

### Григорьев

- `name`: `Григорьев Павел Игоревич`;
- `position`: `Врач-пародонтолог`;
- `experience_years`: `12`;
- `service_ids`: `periodontitis`;
- `profile_ref`: `kb:doctors__doctor__grigoriev.md#korotko`.

### Кузнецов

- `name`: `Кузнецов Дмитрий Андреевич`;
- `position`: `Врач-стоматолог-ортопед`;
- `experience_years`: `19`;
- `service_ids` exact order: `zirconia_crowns`, `veneers`, `all_on_4`, `all_on_6`,
  `temporary_teeth`, `classic`, `implant_supported_prosthetics`, `clasp_dentures`,
  `removable_dentures`;
- `profile_ref`: `kb:doctors__doctor__kuznetsov.md#korotko`.

### Морозова

- `name`: `Морозова Анна Сергеевна`;
- `position`: `Врач-ортодонт`;
- `experience_years`: `11`;
- `service_ids`: `aligners`;
- `profile_ref`: `kb:doctors__doctor__morozova.md#korotko`.

### Орлов

- `name`: `Орлов Никита Владимирович`;
- `position`: `Врач-имплантолог`;
- `experience_years`: `16`;
- `service_ids` exact order: `classic`, `one_stage`, `sinus_lift`, `all_on_4`,
  `all_on_6`, `temporary_teeth`, `implant_supported_prosthetics`;
- `profile_ref`: `kb:doctors__doctor__orlov.md#korotko`.

### Волков

- `name`: `Волков Александр Сергеевич`;
- `position`: `Главный врач, стоматолог-хирург, имплантолог`;
- `experience_years`: `13`;
- `service_ids` exact order: `classic`, `one_stage`, `sinus_lift`,
  `zygomatic_implants`, `pterygoid_implants`, `all_on_4`, `all_on_6`,
  `temporary_teeth`, `tooth_extraction`;
- `profile_ref`: `kb:doctors__doctor__volkov.md#korotko`.

Запрещены `version`, `active`, aliases, education/certificates, photo, schedule/slots,
availability, rating/priority, roles/phases, CTA и UI/card fields.

## Transitional parity law

Новый test локально и read-only strict-parses шесть personal doctor MD frontmatters,
игнорируя overview, и строит только migration-evidence projection:

- mapping key = exact `doc_id`;
- `name` = exact `name_full`;
- `position` = exact `position`;
- `experience_years` = exact `experience_years`;
- `service_ids` = exact `services`, включая authored order;
- `profile_ref` = `kb:<exact filename>#korotko`.

Полученный plain mapping должен быть exact равен `catalog.model_dump()` из S8. Этот
helper существует только в test module, не импортируется product code и не является
compatibility adapter. Он будет удалён вместе с transitional MD metadata после
отдельного wiring/cleanup governance.

## External integrity law

Acceptance test:

1. читает service IDs как top-level keys реального
   `clients/demo/service_catalog.json`;
2. строит KB refs через frozen S4 из `clients/demo/md`;
3. создаёт frozen S6 `DoctorCatalogExternalIndex`;
4. требует `validate_doctor_catalog_external_refs(...) is None`;
5. требует exact sorted `build_doctor_source_refs(...)` для шести IDs;
6. union всех doctor `service_ids` exact равен service catalog IDs минус
   `{"tomography"}`; неизвестных service IDs нет.

Это доказывает doctor side общей `service_id` связи, но не объявляет current pricebook
target price source и не строит answer context в S9.

## Protected tests / честность

- новый `tests/test_demo_doctor_catalog.py` читает только новый catalog, шесть personal
  doctor MD, demo service catalog и demo MD-root через frozen S4;
- overview не материализуется как doctor;
- тест не импортирует current doctor/runtime/routes/session/price loaders;
- source files до/после теста имеют exact одинаковые hashes;
- frozen tests не меняются;
- запрещены skip/xfail, conditional PASS, mocks product runtime и snapshot current
  output.

## Минимальные acceptance tests

Compact module доказывает:

1. S8 загружает real catalog как `TargetDoctorCatalog`, keys имеют exact order;
2. `model_dump()` exact равен нормативному owner-approved payload для всех шести
   записей и пяти полей;
3. JSON содержит только `doctors`, каждая запись — только S5 fields, запрещённых extras
   нет;
4. exact transitional MD projection равна loaded target catalog;
5. real service/KB index проходит S6 и exact doctor refs построены;
6. service coverage exact, единственное missing — `tomography`;
7. All-on-4 exact связан минимум с Кузнецовым, Орловым и Волковым; whitening — с
   Фёдоровой; aligners — с Морозовой; periodontitis — с Григорьевым;
8. before/after hashes catalog, six MD и service catalog идентичны;
9. source/AST audit test module не импортирует current doctor/runtime/session/price
   loaders и не вызывает filesystem write APIs.

## Verification

До data edits:

1. independent read-only checker читает TASK, planned exact payload, six MD, service
   catalog, S4/S5/S6/S8 contracts/tests, checklist и guardrails;
2. checker подтверждает exact data, JSON ownership, временную parity law, conscious
   tomography exception и отсутствие runtime/price/A9 claims;
3. при `❌`/`❓` governance исправляется и повторно проверяется до data edits.

После реализации:

1. `.venv/codex312/Scripts/python.exe -m pytest tests/test_demo_doctor_catalog.py -q --basetemp=.pytest_tmp_s9`;
2. `.venv/codex312/Scripts/python.exe -m pytest tests/test_doctor_schema_loader.py tests/test_doctor_schema_contract.py tests/test_doctor_schema_refs.py -q --basetemp=.pytest_tmp_s9_contracts`;
3. `.venv/codex312/Scripts/python.exe -m pytest tests/test_demo_doctor_template.py tests/test_response_schema_kb_index.py -q --basetemp=.pytest_tmp_s9_neighbor`;
4. `.venv/codex312/Scripts/python.exe scripts/lint_content.py --client demo`;
5. `git diff --check`, `git status --short`, diff only по allowlist;
6. independent read-only checker сначала читает data/test diff, затем сам запускает те
   же команды;
7. live/LLM и полный pytest не запускаются: product consumers не меняются.

## Definition of Done

- real demo target doctor catalog существует в final S5 wire shape;
- exact owner-approved data и transitional MD parity доказаны;
- real demo проходит S8 load и S4→S6 external integrity;
- JSON владеет structured doctor facts, MD остаётся продающим content source;
- service-price answer context и product wiring не реализованы и не объявлены;
- current runtime, answers, routes, UI, session, A9 и authority не изменились;
- roadmap отмечает S9 как offline demo materialization, не product activation;
- checker `✅`, отдельные governance/completion commits и push только в
  `origin/codex/stage-a`, рабочее дерево чистое.
