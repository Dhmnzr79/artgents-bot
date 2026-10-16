# Общий каталог и цены — owner GO 2026-10-16

Владелец подтвердил реализацию после согласования последовательности: общая
схема и ценовой слой → карточки в разговоре → самостоятельный каталог и три
вкладки → общая форма → два локальных демо. При архитектурных вопросах — Astra.
UX-решения: THREE_TABS_DEMOS_HANDOFF.md с последующими уточнениями в
MEDICAL_DEMO_CONTENT_TASK.md; последнее решение о клиентской подаче без демо-
маркировок сохраняется. Начальная тема страницы входит в первую готовую
локальную реализацию интерфейса, а не в этот отдельный schema checkpoint.

## Этап 1: единый действующий каталог и сборка предложения

Тип: архитектурное обобщение/упрощение, дополнительно исправление startup.
Ответственность — только таблица DEMO_D2_TARGET_CONTRACT.md §3.

До → после → удаляемая зависимость:
- Встроенный dental enum пропускает pack → непустые авторские family/unit IDs
  проходят тот же строгий каталог → загрузка не зависит от списка ниш в коде.
- Числовой offer сначала требует legacy billing dictionary, потом берёт свою
  обязательную подпись → берёт авторскую подпись сразу → legacy unit dictionary
  удалён из D2 сборки цены и опубликованных условий.
- Frozen row собирается внутри dialogue materializer → одна чистая функция
  собирает существующий D2FrozenPriceRow для выбранного canonical offer → старое
  тело и дублирование форматирования удалены; chat использует её непосредственно.
- Startup/операционный validator требуют старые strategy/marketing → используют
  текущий immutable D2 snapshot/catalog/model view → эти legacy readers и
  обязательные файлы удалены из startup/validator/template. Legacy tooling
  вне живого D2 пути не переводится и не служит fallback.

Единственные владельцы: таксономия и подписи — pack; суммы/состав/условия — offers;
форматирование — общая чистая сборка; применимость/выбор — прежний код по данным;
свободный смысл — модель; контекст/revision/replay/lead/privacy — прежние owners.
Нет нового resolver, API, control envelope, модели, fallback или второй цены.

Результат этапа: medical pack загружается и готовые предложения формируются тем
же кодом, что dental. Tenant ещё не регистрируется в runtime/panel. Это не
приёмка трёх вкладок и не обещание готовности общего интерфейса.

Следующие этапы сохраняют свою очередь: точная offer-применимость промо;
выбор вариантов перед раскрытием деталей/no-public-price card; read-only API
без изменения беседы; общая форма; начальная тема страницы; demo admission.
Dental volume controls, niche prompt примеры и hint ещё не обобщены здесь.
Удалять defaults без сохранения прежних dental кнопок нельзя. Pack НикаДент
остаётся read-only; зависимый перенос controls в его данные отложен.

## Preflight и границы

Repository/Git top: C:/Cursor Projects/artgents-bot-active.
Fresh fetch origin/main: f7629491f2bb93ed80e2f58aea53770841bbd6a3; merge base тот же.
Ветка codex/three-tabs-catalog создана от этого ref. Явно перенесены handoff
cefb2ee → 6081343, content 5d463e0 → a718e12, copy cleanup 6b9dbf5 → c3d61ae.
Implementation baseline: c3d61aeeb9a3b789e20c48483836a72bac8f5b5e.
Tracked/index перед этапом чистые. Foreign otzyv-1/2/3.jpg не трогать.
VPS, deployed demo, НикаДент pack, routing и ALLOWED_CLIENTS не менять.
Provider/SMTP calls: 0; merge/deploy запрещены. Topic push/draft PR разрешены.
Временные offline результаты только в ignored drafts/three-tabs-catalog/.

Точный allowlist:
- contracts/response_schema.py
- core/d2_price_offer.py
- core/d2_published_offer_terms.py
- core/response_plan_materialization.py
- core/startup_check.py
- core/prod_readiness.py
- core/d2_tenant_snapshot.py
- core/d2_http_adapter.py
- scripts/validate_client_pack.py
- clients/_template/target_response/marketing.yaml (удаление)
- clients/_template/target_response/clinic_strategy.yaml (удаление)
- clients/_template/target_response/d2_commercial.json
- clients/demo_medical/README.md
- docs/CLIENT_PACK_AUTHORING.md
- docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md
- docs/tasks/THREE_TABS_CATALOG_TASK.md
- tests/test_response_schema_contract.py
- tests/test_validate_client_pack.py
- tests/test_client_pack_template_scaffold.py
- tests/test_d2_catalog_generalization.py
- tests/release/offline.txt

## Приёмка и проверки

Одинаковый snapshot/validator для demo, nikadent, demo_medical и _template.
Все medical offers; fixed/from/range/no_public_price; произвольная новая family
и единица с авторской подписью; refs/неактивные/чужие IDs/forged terms reject.
Проверить старые dental brand/extent/count и актуальные price/native/replay,
JSON/SSE paths с fake provider; отсутствие model/effect у чистой сборки.
Consent/UI/contact/MD refs остаются проверяемыми, legacy YAML не влияет на D2.
Startup должен читать тот же root, что проверяемый D2 pack; malformed current
commercial/tenant/ref должен блокировать, а не проходить через legacy fallback.
Один независимый read-only Checker завершённого этапа. Полный CI перед merge.

Baseline: старый test_d2_price_modes не проходит из-за удалённого поля
content_realization в его историческом helper; это не регрессия нового этапа.
Текущие HTTP tests на исходном c3d61ae падают при app import: startup использует
legacy load_target_client_data и обнаружение pack из другого root, видит новую
папку demo_medical, которой нет в изолированном root fixture. Исправляется общий
startup механизм, не отключение проверки. Первый запуск pytest также упирался
в системный sandbox TEMP; последующие используют отдельные ignored basetemp.

## Результат

Реализован этап 1 на codex/three-tabs-catalog поверх c3d61ae. Нормативные роли
не изменились. Основной путь: /ask либо /ask/stream → D2 turn →
resolve_d2_operations → _d2_price_block → build_d2_price_offer_row. Прежнее тело
_d2_frozen_price_row и копии formatter/variant/payment-stage helpers удалены из
materializer. Один core/d2_price_offer.py собирает существующую frozen row;
выбор offers, цена из данных, native completion, история и replay прежние.

Удалены закрытые ServiceFamily/BillingUnit перечисления, вызовы legacy unit
dictionary из D2 row и published terms, legacy loader из startup/readiness и
операционного validator, старые обязательные strategy/marketing из шаблона.
Добавлены непустые data-owned IDs, чистая общая сборка предложения, один
configured D2 root для dialogue/startup/readiness, текущий commercial scaffold,
проверка authored refs по captured snapshot и целевые offline regressions.
Эта ref-проверка общая для startup/readiness/validator; не создаёт semantic
проверку модельного ответа и не меняет per-turn recoverable source-claim путь.

Изменение поведения: новые медицинские family/unit теперь загружаются и
показывают точную авторскую подпись; startup проверяет реально используемый D2
pack выбранного root. Невалидные current commercial/tenant/content refs
блокируют readiness/startup/validator. Стоматологический выбор/суммы/бренды,
consent, privacy, effects, replay и transport owners не заменены. Все правки
в пределах exact allowlist; данные clients/demo и clients/nikadent не менялись.

Offline evidence:
- Snapshot/model view/validator: demo 23 services/33 offers, nikadent 34/26,
  medical 21/45, template 1/1 — PASS одним loader.
- Основной набор: test_d2_catalog_generalization, response_schema_contract,
  validate_client_pack, template_scaffold, d2_tenant_snapshot,
  d2_native_price_runtime — 225 passed, 2 historical failures ниже.
  Проверены все 45 medical offers, fixed/from/range/no_public_price, новая
  произвольная family/unit, ownership/forged terms/disabled option, current
  graph, native JSON/SSE price → replay → continuation и adverse completion.
- Focused после исправлений: 43 passed — 12 dental topic/count/transport,
  6 local/prod startup/ref failures, validator и release selection.
  Промежуточная ref-проверка отдельно: 12 passed.
- Для независимого сравнения экспортирован чистый origin/main f762949 в ignored
  drafts/three-tabs-catalog/baseline-main (не Git checkout/worktree). Шесть
  native topic×count сценариев там дали 6 passed. Новые regression tests
  фиксируют именно эти offer tuples и точные суммы, включая отсутствие
  умножения. Начальные ошибочные ожидания были взяты из obsolete helper и
  исправлены по clean baseline; production selection не менялся.
- Обе historical ошибки test_d2_tenant_snapshot::test_legacy_policy_edits_preserve_price_replay_and_next_turn
  (json/sse) воспроизведены на чистом main: тот же assert строки 128, старый
  raw JSON публикуется как prose вместо native show_price. Это существующий
  долг тестового helper, не регрессия. Старый test_d2_price_modes также падал
  до edits из-за удалённого content_realization. Их внеочередная миграция не
  выполнялась; пробные старые cards/guidance suites не считаются приёмкой.
- Independent Astra Checker первоначально REJECT: authored MD refs не были
  общими для readiness/startup; dental test expectations не совпадали с
  baseline. Исправления описаны выше. Focused recheck: 22 passed, оба P1
  устранены; финальный focused verdict Astra — PASS после чтения этого
  результата. Новых P0/P1/P2 нет. PASS относится только к этапу 1.
- diff --check PASS. Новый набор включён в tests/release/offline.txt.

Остатки/риски: medical пока не зарегистрирован в маршрутизации/панели; offer-
применимость акции «Три зоны» остаётся следующему этапу. UI по-прежнему открывает
первый вариант; общий новый список и no-public-price card не приняты этим
checkpoint. Dental controls/prompt/hint, read-only API, общая форма, page context
и demo admission не объявляются реализованными. Поэтому живое обобщение всего
помощника не сертифицируется. Общий код изменён локально, НикаДент pack read-only.

Provider/model calls бота 0, SMTP 0. Только подставные транспорты и локальные
offline данные. VPS, серверы и deployed dialogue не проверяли и не меняли.
Полный CI/build/deploy не запускались; merge/deploy не разрешены. Перед commit
будут проверены staged names/stat/diff/check; commit/push/PR и фактический hash
сообщаются в итоговом ответе. Foreign otzyv-1/2/3.jpg сохранены вне индекса.
