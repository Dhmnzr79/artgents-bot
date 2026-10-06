# D2 S2-C7 — реальные tenant-данные и их передача в изолированный план

Дата: 2026-09-18. Статус: архитектурный Checker PASS; готово к поручению Terra.
Baseline: 36a57e22dc44c8bbc8c6b19d994fabc0292e2113.
Папка/Git root: C:\Cursor Projects\artgents-bot.
Ветка: codex/demo-d2-service-volume.
Локальные origin/main и merge-base: 141ce91fb1731cd990fcf8391550150016c73e7f.
Приоритет: решения D2-076–084, актуальные TARGET_CONTRACT и ACCEPTANCE.
Этот gate заменяет прежний проект C7 и его HOLD; старые Checker PASS не применяются.
Реализация не начата; запуск по отдельному поручению владельца.

## 1. Один checkpoint и его смысл

Цель: реальные файлы клиники → неизменяемый snapshot → model view и проверенные
источники → существующий D1R parser → существующий изолированный D2 resolver →
единый frozen plan → renderer/UI. Проверить самостоятельную конкретную цену,
выбранный раздел документа и их сочетание на настоящем demo без редактирования базы.

Чтобы адаптер не обходил старые ограничения, включены две необходимые замены
внутри изолированного D2: опубликованные условия вместо completeness-фильтра
и адресация разделов вместо одного постоянного текста на документ.
Это один мост реальных данных, а не все оставшиеся продуктовые маршруты S2.

Важно: информационная часть в C7 — точный выбранный текст источника, как в C1–C6,
но теперь из любого раздела. Это временная проверяемая граница materialization,
НЕ окончательный режим всех ответов. Обычная свободная проза модели и её T3
проверки/релевантная резервная цитата остаются отдельным обязательным участком S2.
C7 не объявляет B15 целиком или model-first человеческий ответ законченными.
Полный документ публикуется модели уже здесь; запрещено скрывать его за korotko.

## 2. Что остаётся вне C7

HTTP/SSE/виджет, сессии и TTL, replay, lead/privacy/SMTP, provider invocation,
production prompt/cache, policy/terminal/contact как маршруты, маркетинговые
блоки и brand/family-price selection. Также вне C7: новые clinic-конфигурации,
наполнение контента, полноценный обзор направлений, обработка нескольких ценовых
вопросов по D2-080 и общее частичное восстановление ошибочных content-частей.
Эти принятые правила не отменяются; закрыть их нужно до S3, а не маскировать
старый exception как готовое поведение. S2 не завершён; S3 не начинается.

## 3. Единственный смысловой вход и две проекции данных

Публичные границы (имена можно уточнить без изменения ответственности):

- load_d2_tenant_snapshot(client_id, *, clients_root): явный доверенный root,
  containment tenant/path, immutable captured bytes и DTO, typed load errors.
- build_d2_model_view(snapshot): реальные ActiveServiceCatalogSnapshot,
  ServiceReferenceCatalogSnapshot, CommercialFactCatalogSnapshot через from_bundle;
  полный body каждого материала, список доступных разделов и явные связи.
- build_d2_snapshot_sources(snapshot, *, model_view, envelope, session_key,
  transport_kind, shown_secondary_ref_ids=()): проверяет snapshot/view/tenant/refs,
  возвращает ResponsePlanMaterializationSources. Не принимает raw question.

Модельный смысл только RequestUnderstanding.requests внутри OneCallEnvelope.
Никаких query-dependent retrieval/selector, словарей/regex понимания, второго
parser/envelope, response_plan_composer или LLM retry. Model view — входные
данные, не новый ответ модели. Внешние payload в C7 только заранее заданные offline.

Snapshot: immutable strings/bytes/tuples; frozen оболочка вокруг общего dict
недостаточна. На выдаче fresh validated bundle/sources. Fingerprint включает
version, tenant, канонические пути и bytes всего read set. Различает отсутствие
optional файла и его появление. Подменённый view проверяется содержательно,
не только caller-provided digest. Один view публикует всё поддержанное множество.

Read set: обязательные service_catalog, brand_catalog, clinic_strategy, marketing,
pricebook/facts, pricebook/services/*.json из target_response; optional
pricebook/family_prices.json; md/*.md, tone.yaml, ui.yaml, video_catalog.yaml,
doctor_catalog.json для существующих schema refs. До реализации сверить фактические
имена с pack, без расширения содержательного scope. Не читать .env, логи или БД.
Отсутствие обязательного файла — ошибка подготовки; валидные пустые необязательные
списки нормальны. После capture повторно проверить набор/bytes; изменение — typed
error без retry. После проверки парсить только captured bytes. Транзакционное
обновление произвольно переписываемых файлов не обещается.

Pure captured-text entry point добавить в существующий response_schema_loader;
path API использует те же JSON/YAML/schema validators. Не копировать загрузчик.
Старые cache/build_one_call_stable_prefix не использовать: они перечитывают tenant.
Новый cache не нужен. UI/config parsing допускает структурные anchors/frontmatter,
но не старые aliases/triggers для понимания вопроса.

## 4. Цена: один владелец опубликованных условий

Выбранное решение: D2 непосредственно проецирует валидированный TargetOffer
в immutable D2PublishedOfferTerms (в contracts/d2_tenant_snapshot.py) через pure
helper core/d2_published_offer_terms.py. Источник — material_authority.bundle
того же snapshot. Не добавлять альтернативный caller-provided evidence map.

DTO хранит точные package.label, price_scope_label, includes, excludes,
payment_stages (label/amount/currency/timing), required_conditions_metadata.conditions
если они есть, tenant/offer identity. Пустой список означает отсутствие
опубликованных дополнительных записей, НЕ утверждение «доплат нет».
Отдельного признака complete для разрешения цены в D2 больше нет.

_d2_price_block, _d2_scope_offer_ids и _d2_frozen_price_row используют эту проекцию.
D2 не читает condition_evidence_by_offer для отбора, отображения или scope choices.
Общий legacy build_condition_evidence_for_offer и старый materializer сохраняются
без изменений. Это замена зависимости внутри D2, не fallback «new или old».
Активность, явная применимость к объёму и clinic strategy сохраняются.

В frozen row переносятся все опубликованные оговорки. Для fixed/from/range
package.label уже входит в display_text — не продублировать его. Остальные записи входят в condition_texts
в стабильном порядке: scope label (если не повторяет видимую единицу/label),
includes, excludes, этапы оплаты, metadata conditions. Подписи групп «Входит»,
«Не входит», «Оплата» — только техническое оформление; факты/суммы/сроки точные
из записей. Только точная дедупликация, не смысловая склейка похожих фраз.
Не складывать суммы этапов, не умножать стоимость, не добавлять «под ключ».
При no_public_price display_text/approved_text сохраняют исходный approved_text,
не подставляется число. В этом режиме package.label ещё не входит в display_text:
сохранить его отдельной записью condition_texts, если он не повторяет approved_text.
Матрица #3 проверяет этот край вместе с обычной ценой без дополнений.

Невалидные обязательные записи не превращать в пустые: strict schema rejection
до подготовки источников. Для валидного offer отсутствие metadata не ошибка.
Существующий D2 reason d2_no_complete_price_candidates переименовать в
 d2_no_price_candidates во всех D2 типах/тестах allowlist: причина теперь отсутствие
допустимых активных предложений, не отсутствие отметки completeness.
 d2_no_scope_price_candidates сохраняется. Брать общую/чужую цену вместо
неприменимой к известному объёму запрещено.

Snapshot binder поставляет две стандартные failure authorities для этих причин:
«К сожалению, у меня пока нет информации о стоимости этой услуги».
Это утверждённый системный текст D2-079, не выдуманные данные клиники.
Tenant identity берётся из проверенного snapshot; уникальные message IDs.
Новая схема clinic overrides вне C7; не искать похожие тексты в tone.

## 5. Материалы: документ целиком и явные адреса разделов

Добавить в существующий RequestUnderstandingRequest одно optional поле:
content_section_refs: tuple[str, ...] = (). Оно допустимо только для content
с content_ref. content_ref сохраняет формат имени .md без slash/anchor.
Refs — opaque IDs из model view выбранного документа; дубликаты/пустые запрещены.
Nested validation проходит через нынешний parse_production_envelope_json;
второго parser нет. Отсутствие поля сохраняет прежний wire contract.
Production prompt не меняется; перед его будущим подключением обновить описание
поля и версию prompt/cache в соответствующем checkpoint, не забыть об этом.

D2AuthoredContentAuthority расширяется immutable sections с уникальными section_ref
и display_text. display_text authority — весь очищенный body, а не korotko.
Структурный разбор Markdown: убрать frontmatter/служебные HTML comments;
учесть code fences, заголовки и вложенность. Явные anchors сохраняют identity;
для неякорных разделов — deterministic ordinal refs в пределах данного snapshot,
не slug/семантическая нормализация заголовка. Namespace IDs различает explicit
anchor и ordinal. Дубликат explicit anchor — diagnostic: anchor непубликуем,
body сохраняется и доступен как документ; не угадывать нужное совпадение.
Секция — contiguous subtree до следующего заголовка того же/выше уровня.

Каждый непустой body публикуется независимо от korotko. Полный body присутствует
в model view даже при существовании section refs. Пустой документ диагностируется
как пустой, не подменяется выдуманной справкой. Явные разделы ниже korotko доступны.

В _d2_information_blocks:
- refs заданы → точные section texts этого документа в указанном порядке;
- refs пусты → точный полный body (совместимая authored граница), не автоматически
  первый/korotko раздел. Не обрезать его скрытым лимитом.
Нет копирования content_text модели в доверенную authority. В C7 этот текст
остаётся модельным входом, обычная его публикация/T3 не реализуются.

Данные выбранных refs замораживаются в InformationSourceBlock через additive
поле source_section_refs и его текст, чтобы provenance не исчезла после сборки.
Те же refs сохраняются в D2ResolvedRequestPart.content_section_refs; frozen
validation проверяет равенство refs части и блока, чтобы подмена linkage
отвергалась. Старые blocks/parts без refs остаются допустимыми. Renderer не
выбирает раздел повторно. Матрица #4/#10 включает повреждённый frozen linkage.
Два запроса по разным разделам одного документа дают два правильных блока,
а UI по прежним правилам относится к документу первого content-запроса.

Существование ссылки доказывает допустимость, не смысловую релевантность.
Offline тест выбирает refs заранее; правильность выбора живой моделью и качество
прозы — будущая отдельная live-проверка, не обещание C7.
Не выдавать полную цитату или exact-section тест за готовую свободную AI-консультацию.

## 6. Scope, UI и честные границы подготовки данных

Service content: точная обратная связь service.content_ref → .md.
Topic FAQ: явный metadata.topic и связи service docs с тем же точным topic.
Нет aliases, filename guesses или словаря implantology→implantation.
Пустой allowed_service_ids не wildcard: binder разрешает unscoped документ,
но service/topic привязка требует опубликованной явной связи.
Чужие tenant/подменённые refs останавливаются, не подбирается соседний материал.

suggest_h3 → реальный anchor и заголовок; video_key → captured catalog entry;
cta_action=lead + cta_key → точная tone.lead.cta_variants запись. Никаких обещаний
бесплатности из догадки. Стандартная CTA для ценовой части использует точный ключ
price этой схемы, если запись есть; отсутствие ключа не блокирует цену.
Source CTA приоритетнее общей согласно существующему resolver.
Неисправный optional anchor/video/CTA исключается отдельно с diagnostic до общей
валидации sources; tenant breach не маскируется optional degradation.
При единственной недоступной цене blanket очистку всего UI убрать: сохраняется
разрешённая CTA, а secondary остаются подавленными ценовым намерением.
Доставка/исполнение действий по этим ID — S3, здесь только frozen projection.

Directions в snapshot — структурные связи, НЕ утверждённая витрина основных цен.
В текущем demo нельзя выдумать curated overview из первых трёх offers, заполнить
недостающую вводную или четвёртую кнопку. C7 реальная интеграция поддерживает
конкретный service-price, а готовность broad overview выдаёт отдельной capability
состоянием unconfigured. Topic-only price binding для неподготовленной витрины
возвращает typed preparation error direction_overview_not_configured, не sources
с произвольным списком. Это проверка подготовки изолированного адаптера, НЕ
согласованный ответ пользователя/новый runtime route. До S3 витрину подготовить
и доказать нормальный ответ A01/A07. Недостающий optional UI не причина такого error.
Существующие C4/C5 authored-fixture обзоры сохраняются; старый runtime не fallback.

Неактивная услуга не означает публичное «не оказываем». Policies не выводятся
из отсутствия catalog row. Clinic content остаётся в собственных источниках.

## 7. Exact write allowlist реализации

```text
contracts/d2_tenant_snapshot.py                         NEW snapshot/view/terms DTO
contracts/request_understanding.py                     additive section refs only
contracts/response_plan_materialization.py              content sections + failure reason
contracts/response_plan.py                              section provenance + failure reason
core/d2_tenant_snapshot.py                             NEW capture/full material/model view
core/d2_snapshot_sources.py                            NEW projection/ref binding/defaults
core/d2_published_offer_terms.py                        NEW pure offer terms projection
core/response_schema_loader.py                         pure captured-text seam
core/response_plan_materialization.py                   D2-only price/sections/failed CTA
 tests/test_response_schema_loader.py
 tests/test_request_understanding_schema_offline.py
 tests/test_d2_single_request.py
 tests/test_d2_multi_request.py
 tests/test_d2_price_modes.py
 tests/test_d2_part_failure.py
 tests/test_d2_tenant_snapshot.py                       NEW
 tests/test_d2_snapshot_sources.py                      NEW
 tests/test_d2_demo_snapshot.py                         NEW
docs/tasks/DEMO_D2_S2_C7_TERRA_TASK.md                    report/matrix
```

Leading spaces в test paths выше только выравнивание, не часть пути.
Gate и уже согласованные PRODUCT_DECISIONS/TARGET_CONTRACT/ACCEPTANCE — read-only,
но stage-only task-owned исключение для будущего exact C7 commit после проверки
всего документационного diff. Остальные файлы read-only, особенно clients/**,
legacy helpers/runtime, HTTP/session/provider/lead/privacy, production prompt.
Не менять core/response_plan_condition_evidence.py или существующие non-D2 funcs.
Не вводить второй resolver. Если необходим другой файл — остановка до расширения.

## 8. Матрица (planned tests, не результаты PASS)

| # | Planned test node | Доказательство |
|---|---|---|
| 1 | test_d2_demo_snapshot.py::test_real_simple_prices_without_metadata | Реальные extraction/whitening/veneers: raw D1R → parser → sources → plan → text/UI; исходные суммы, from, units, package.label; нет обязательного complete и лишнего «всё включено» |
| 2 | test_d2_demo_snapshot.py::test_real_implant_terms_are_preserved | Classic Impro: сумма, package/includes/excludes/payment stages/metadata условия сохранены; не складываются и не теряются |
| 3 | test_d2_snapshot_sources.py::test_terms_absence_and_corruption_are_distinct | Простая валидная цена без дополнений проходит; повреждённое условие не заменяется пустым; deliberate legacy evidence unknown не подавляет D2, не переносится в новый DTO |
| 4 | test_d2_demo_snapshot.py::test_real_content_below_korotko | Полный pain document в view; выбран sedatsiya-i-narkoz → его exact text и source UI, не общий абзац. Два разных раздела одного документа дают разные blocks |
| 5 | test_d2_tenant_snapshot.py::test_material_without_korotko_is_published | Pack copy без korotko, без anchors, с nested headings/fences/comments, duplicate anchor и пустым документом: публикация не зависит от специального заголовка; refs детерминированы |
| 6 | test_d2_demo_snapshot.py::test_real_price_and_section_are_ordered | Конкретная цена + раздел о боли и обратный порядок: обе части, exact conditions, price suppression реальных follow-up/video, CTA сохраняется |
| 7 | test_d2_snapshot_sources.py::test_unavailable_price_defaults_keep_content_and_cta | Валидный pack без активного offer/без применимого scope offer, без clinic failure copy: approved default, сохранённый content/CTA, никакой подменной цены |
| 8 | test_d2_snapshot_sources.py::test_optional_ui_does_not_block_answer | Missing/invalid anchors/video/CTA исключаются индивидуально; нет другого source UI, отсутствие дополнений не ошибка; foreign tenant fatal |
| 9 | test_d2_tenant_snapshot.py::test_snapshot_capture_identity_and_mutation | Каждый вид файла/набор файлов/family_prices presence меняет hash; detected mid-read change; mutation выданного bundle не меняет snapshot; после capture чтений нет |
| 10 | test_d2_snapshot_sources.py::test_tenant_view_and_source_binding | Два tenant с одинаковыми IDs; forged view/section/doc/session; path traversal/symlink escape; нет wildcard service scope и no default demo |
| 11 | test_d2_demo_snapshot.py::test_overview_readiness_is_not_optional_ui | Структурные направления не считаются витриной; реальный demo unconfigured overview явно диагностирован; никаких invented prices/buttons; отсутствие optional UI не выключает service price |
| 12 | test_response_schema_loader.py::test_captured_text_loader_matches_path_loader | Parity strict JSON/YAML duplicate/merge/schema/errors, empty valid sections vs missing required files, optional family data |
| 13 | test_request_understanding_schema_offline.py::test_d2_section_refs_use_existing_envelope | Новый optional field through real parser, absent-field compatibility, invalid shape/duplicates/kind/ref reject; без второго parser |
| 14 | test_d2_demo_snapshot.py::test_real_path_never_calls_legacy_or_network | Sentinels actual aliases legacy Composer/materializer/semantic selector/provider/network; counters 0; frozen render/UI без filesystem |

Real-demo сценарии не импортируют _sources fixtures и не monkeypatch resolver,
builder или renderer. Raw model outputs синтетические, данные клиники настоящие.
Synthetic/copied packs через тот же публичный loader только для граничных случаев.
Все positive объекты проходят validation, без unchecked model_copy обходов.
Expected суммы/фрагменты проверяются независимыми assertions, не тем же helper.

Миграция старых тестов намеренная, не ослабление: unknown_conditions_do_not_publish
заменяется положительным B13. C6 unavailable cases строятся на отсутствии реально
допустимых offers; безопасность/mixed order/frozen linkage/неожиданные exceptions
сохраняются. Общий legacy condition-evidence тест остаётся прежним и проходит.

## 9. Stop-conditions, Checker и завершение

Стоп при втором parser/semantic regex/LLM retry, clinic edits/новом runtime,
изменении non-D2 поведения, произвольном complete, default korotko, выдаче
unchecked model prose, изменении scope applicability, подмене неизвестного source,
попытке впихнуть T3/все policies/memory в этот checkpoint, выходе за allowlist.
При реальном конфликте — конкретный вопрос Astra с двумя вариантами; после двух
неудачных реализационных попыток — Sol только на воспроизводимый участок.

До Checker: все 14 строк имеют реальные test IDs/results, один связный offline
regression из Terra task, exact diff, provider/SMTP 0. Проверка на реальных данных
до freeze обязательна; data readiness не маскируется PASS адаптера.
После REJECT только исправление findings и focused recheck.
После implementation PASS — точный commit/push, без merge/deploy/нового PR.

До S3 остаются: T3 prose/релевантная fallback provenance; общее отсутствие сведений
и уточнения с памятью; first-price deferral; policies/terminals/commercials;
утверждённая витрина направлений и model prompt binding к snapshot; остальные
acceptance и интеграция. C7 не заявляет готовность этих возможностей.

## 10. Проверка gate

2026-09-18: independent read-only c7_revised_gate_checker — PASS, без P0/P1.
Проверены оба C7 документа и необходимые действующие типы/границы. Allowlist
достаточен; нового parser или renderer не требуется. Неблокирующее замечание
о package.label в режиме no_public_price учтено в §4 и матрице #3.
Это архитектурный PASS задания, не implementation PASS. Тесты при подготовке
не запускались, код/данные не менялись, provider/SMTP/network calls = 0.
Документы подготовки пока не committed/pushed; staging пуст.
