# TASK — S7 Demo Doctor Template Hardening

**Ветка:** `codex/stage-a`

**Baseline:** `c2ee27f feat: validate doctor source refs S6`

**Серия / checkpoint:** `S7` — точечная правка demo doctor content/service links и
offline доказательство, что demo является согласованным примером для S5/S6.

**Режим:** data/template hardening only. Никаких runtime code, routes/UI, live/LLM или
product authority.

Текущий legacy demo читает эти MD и service links, поэтому его локальные doctor results
и тексты ожидаемо отразят одобренные data changes. Это не новое runtime wiring: код
query recognition/routing, prompts, UI/session и source authority не меняется, а S5/S6
не подключаются к product path.

## Решение владельца продукта

- новых врачей не создавать: существующих шести достаточно;
- simple doctor→service links, без ролей/фаз/ранжирования;
- Фёдорова остаётся связана с veneers/zirconia и получает whitening; MD явно это
  подтверждает;
- Орлов получает sinus lift;
- Волков получает sinus lift, zygomatic и pterygoid implants;
- tomography остаётся clinic-level diagnostic service без doctor link;
- doctor overview не хранит вручную вычисленные count/sum/range опыта и не дублирует
  `99,8%`;
- стаж важен и должен появляться в любом будущем doctor answer. До target wiring число
  временно остаётся и во frontmatter, и в персональном MD-тексте, чтобы current local
  path не потерял его. Удаление текстового дубля — только после отдельного доказанного
  answer-context checkpoint.

## Цель

Исправить только четыре demo MD и добавить один read-only template test, который
доказывает:

- все шесть персональных файлов детерминированно преобразуются в S5 catalog;
- все service/profile refs проходят S6 на реальных demo service catalog и S4 KB index;
- все doctor-relevant catalog services покрыты хотя бы одним врачом, а единственное
  осознанное исключение — tomography;
- overview не притворяется doctor record и не содержит производных/дублированных чисел.

S7 не меняет authoring field names и не объявляет current frontmatter окончательным
target wire format. `name_full/services` → `name/service_ids` остаётся явным test-only
materialization mapping до отдельного loader checkpoint, без production adapter.

## Затрагиваемые файлы

- `TASK.md`;
- `clients/demo/md/doctors__doctor__fedorova.md`;
- `clients/demo/md/doctors__doctor__orlov.md`;
- `clients/demo/md/doctors__doctor__volkov.md`;
- `clients/demo/md/doctors__doctor__overview.md`;
- `tests/test_demo_doctor_template.py` (new);
- `docs/STRANGLER_ROADMAP.md` — pending `[ ]`, затем `[x]` только после checker `✅`.

Любой другой файл требует остановки и отдельного решения владельца/Архитектора.

## Protected / вне scope

- остальные `clients/demo/**` и весь `clients/cesi/**`, `clients/nikadent/**`;
- `doctors_lookup.py`, current loaders, routing/orchestration, prompts и caches;
- frozen S1–S6 contracts/loaders/index builders/tests;
- переименование doctor files/frontmatter fields или удаление legacy aliases/CTA;
- удаление индивидуального стажа из MD body до target answer-context wiring;
- изменение service catalog, prices, marketing, CTA, UI/cards или session;
- исправление двух непризнанных фраз «кто крутой спец...» / «что за врачи...» — это
  отдельная future common-planner/runtime задача, не новый regex в S7;
- booking, schedule/calendar/CRM;
- protected acceptance/golden/eval fixtures;
- весь A9 design/raw/frozen/harness/evidence и A9 live re-audit;
- live/LLM, merge, `main`, другие ветки и включение product authority.

## Точные content changes

### Фёдорова

- добавить `professional_whitening` в `services`;
- сохранить `veneers` и `zirconia_crowns`;
- short selling paragraph/bullets exact и недвусмысленно говорят о профессиональном
  отбеливании, винирах и циркониевых коронках;
- добавить bullet `**16 лет** практики`, сохранив `experience_years: 16`;
- position/name/other services не менять.

### Орлов

- добавить `sinus_lift` в `services`;
- существующую формулировку про костную и мягкотканную пластику расширить явным
  sinus-lift mention;
- остальные поля/услуги не менять.

### Волков

- добавить `sinus_lift`, `zygomatic_implants`, `pterygoid_implants` в `services`;
- selling text явно подтверждает эти сложные хирургические направления;
- остальные поля/услуги не менять.

### Overview

- сохранить общий продающий текст о команде и направлениях;
- удалить hardcoded «6», aggregate «более 85», range `11–19` и `99,8%`;
- не перечислять или дублировать персональные doctor records;
- не добавлять schedule, ranking, education, photos или UI cards.

## Template-test contract

Новый `tests/test_demo_doctor_template.py` читает только разрешённые реальные demo
doctor MD и `clients/demo/service_catalog.json`, используя safe/strict local test
helpers. Это намеренный data acceptance test, не production loader.

Тесты доказывают:

1. ровно шесть personal doctor files плюс один overview;
2. YAML frontmatter всех семи файлов strict parse без duplicate keys;
3. personal filename stem == `doc_id`, `doc_type=doctor`, `topic=doctors`, subtopic
   соответствует suffix, H2 exact совпадает с `name_full`, один `#korotko`;
4. все personal files имеют одинаковый обязательный transitional key set, нет
   `active`/education/photo/schedule/rating fields;
5. experience strict positive int и exact `**N лет**` временно присутствует в body;
6. services — non-empty unique strings;
7. deterministic mapping всех шести files в `TargetDoctorCatalog` проходит S5;
8. service index из реального demo catalog + KB refs из S4 валидирует catalog через S6;
9. exact `doctor:<id>` refs строятся для всех шести profiles;
10. union doctor services равен всем demo service IDs кроме exact allowlist
    `{"tomography"}`;
11. exact new links присутствуют у Фёдоровой/Орлова/Волкова, а продающие bodies содержат
    соответствующие явные terms;
12. overview не материализуется как doctor, содержит `#korotko`, но не содержит regex
    для team count, aggregate/range experience или `99,8`;
13. before/after test hashes real files identical: test ничего не пишет;
14. source/AST audit test module не импортирует current doctor runtime/routes/session и
    не вызывает write APIs.

## Verification

До data edits:

1. независимый read-only checker читает TASK, четыре planned MD, demo service catalog,
   S4/S5/S6 contracts/tests, checklist и guardrails;
2. checker подтверждает точность assignments, conscious tomography exception,
   transitional experience duplication и отсутствие runtime scope;
3. при `❌`/`❓` governance исправляется и повторно проверяется.

После реализации:

1. `.venv/codex312/Scripts/python.exe -m pytest tests/test_demo_doctor_template.py -q`;
2. `.venv/codex312/Scripts/python.exe scripts/lint_content.py --client demo`;
3. `.venv/codex312/Scripts/python.exe -m pytest tests/test_vague_doctor_followup.py tests/test_doctor_route_order.py tests/test_doctor_schema_contract.py tests/test_doctor_schema_refs.py -q`;
4. `git diff --check`, `git status --short`, diff только по allowlist;
5. independent checker сначала читает test/content diff, затем сам запускает команды;
6. live/LLM и полный pytest не запускаются.

## Definition of Done

- demo doctor profiles/content/services согласованы с простым решением владельца;
- реальный demo pack offline проходит S4→S5→S6 chain;
- overview не хранит производные/дублированные числа;
- current query-recognition/routing code, prompts, UI/session и authority source не
  менялись; legacy demo results могут ожидаемо измениться только из-за одобренных MD и
  service links;
- S5/S6 не подключены к product path и не получили authority;
- roadmap отмечает S7 как demo template foundation, не target wiring;
- checker `✅`, отдельные governance/completion commits и push только в
  `origin/codex/stage-a`, рабочее дерево чистое.
