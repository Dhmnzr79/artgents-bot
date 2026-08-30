# Выбор модели и подготовки контекста — передача в новый чат

Обновлено: 28.08.2026. Это передача решений владельца, не отчёт о реализации и не завершённый Architecture Lock. Имя файла сохранено для ссылок: Prepared Hybrid теперь КАНДИДАТ, а не выбранная архитектура.

## 1. Рабочий контекст и границы

- Проект: `C:/Cursor Projects/demo-bot-one-call-baseline`.
- Публикационная база перед checkpoint 1e: branch `codex/one-call-cached-fullcontext-baseline`, HEAD `c577a7b733dfd90cf8020854e3b275d73579cb08`. Актуальный опубликованный HEAD после публикации checkpoint 1e проверяется через git; итоговый commit указывается в отчёте публикации. Stage53/eval WIP не входит в checkpoint 1e.
- Бот работает только локально у владельца; production-клиентов и задачи сохранения старых ответов нет.
- Не снимать новый LIVE-baseline старой архитектуры, не сохранять старые ответы ради паритета, не строить shadow/dual-run/legacy fallback ради совместимости. Существующие файлы и незакоммиченные изменения при этом не удалять.
- Сохраняются продуктовые требования: полезные ответы, точные условия, работа кнопок и заявки, изоляция клиник. Не сохраняются ошибочные старые ответы и устаревшие архитектурные ограничения.
- Владелец — маркетолог, не программист; утверждает продуктовые решения и разрешает этапы работы.
- Codex — архитектор и куратор: читает код/документы, разбирает причины, предлагает решения, ведёт дорожную карту, готовит задания для Cursor и критерии приёмки, анализирует отчёты. Продуктовый код и тесты не пишет, прогоны и checker сам не запускает. Документацию обновляет по заданию владельца.
- Cursor — исполнитель: по согласованному заданию меняет код/данные, пишет и запускает тесты, затем запускает отдельного независимого checker в Cursor. Checker работает read-only и проверяет результат, а не принимает отчёт исполнителя на веру. Реальные API-прогоны и staging/commit/push также выполняет Cursor, только с соответствующим разрешением владельца.
- Сейчас разрешена подготовка документации/плана. Это не разрешение на произвольные изменения runtime, LIVE или git-публикацию.

## 2. Актуальное решение: сначала сравнение, затем архитектура

Последнее решение владельца заменяет прежний план немедленной миграции на Hybrid:

1. Устранить противоречия данных, определить единственные источники точных фактов. Не переписывать все MD и не удалять сведения до работающей передачи их из нового источника.
2. Обеспечить передачу нужных точных данных ДО написания ответа. Сначала оценить технический scope: это не заведомо маленькая prompt-правка. Сейчас часть точных данных добавляется после генерации, а pre-model hints намеренно ограничены.
3. На одной очищенной базе и одном наборе вопросов сравнить четыре варианта: Flash / Plus × FullContext / вручную подобранный компактный контекст. Во всех четырёх — одинаковые необходимые structured facts, продуктовые правила и условия теста.
4. По качеству, задержке и стоимости выбрать дальнейший путь. FullContext с подходящей моделью — допустимая постоянная архитектура. Hybrid строить, только если эксперимент даёт для этого основание.

Ручной компактный контекст — контроль возможностей модели, НЕ работающий RAG. Это исходные фрагменты и данные, а не написанный за модель ответ. «2–5 фрагментов» — ориентир, не ограничение полноты. Улучшение с ними показывает пользу отбора контекста, но само по себе не доказывает, что проблема только в его длине или что автоматический поиск повторит результат.

Если Hybrid понадобится: PREPARE собирает несколько релевантных источников и точные данные → Composer пишет связный ответ → UI собирается по согласованным правилам. Основной MD нужен для metadata, но не обязан быть единственным источником знаний. Для ответа из структурированных контактов/цен MD-посредник не обязателен.

Цены, условия, врачи, контакты и основные правила не должны зависеть только от нахождения MD. Считать стоимость и задержку всего пути, включая подготовку, embedding/reranking при их наличии. Один Composer — рабочая гипотеза, не догма: альтернативу с дополнительным вызовом можно предложить с обоснованием, но нельзя скрытно реализовать или запустить. Ни превосходство Plus, ни достаточность Flash, ни качество Hybrid пока не доказаны.

Не возвращать общий фильтр чисел/предложений, медицинские keyword-классификаторы или десятки специальных веток. Ошибка необязательного дополнения убирает дополнение, не нормальный основной ответ. При полном отсутствии данных — честное сообщение, что администратор уточнит; при частичном — сохранить известную полезную часть. Не выдумывать сведения.

Общий стоматологический FAQ разрешён по базе. Граница проблемного ответа уточнена владельцем в §3: смысл обращения и маршрут определяет Composer в том же вызове; словесный медицинский gate не развивать. Для всех проблемных/неконверсионных сценариев используется одна детерминированная эмпатичная ADMIN-заглушка с призывом позвонить при срочности и каноническим номером текущей клиники. Персональные диагнозы и назначения не давать; автоматическую рекламу к ADMIN не добавлять. Отсутствие данных или неуверенность сами по себе не означают проблемный сценарий. Медицинские/юридические формулировки источника не смягчать и не усиливать самовольно.

## 3. Согласованные продуктовые решения

### Последнее решение владельца — Composer и служебные записи, 28.08.2026

**Статус: checkpoint 1e принят владельцем/Codex 29.08.2026; разрешён к отдельной публикации.** Offline: адресный набор 216/216, смежный 206/206; checker ACCEPT. LIVE/API не выполнялись. Stage53/eval WIP не входит в checkpoint. CP-EXACT-1 не начинался. Fake/offline доказывает wiring, не качество понимания русского языка моделью. Эта запись заменяет прежнее направление доработки словесного медицинского gate.

**Последнее упрощение владельца от 29.08.2026 имеет приоритет:** проблемные сценарии неконверсионные; Composer не должен писать для каждого из них отдельный patient-facing текст. Он только выбирает существующий `ADMIN`, после чего код показывает одну общую эмпатичную заглушку. Это отменяет более раннее предложение сохранять индивидуальный текст модели для model-ADMIN.

**Один Composer — основной ответ и маршрут в одном вызове:**

- Основная модель получает доступный контекст диалога, понимает обращение целиком, пишет patient-facing текст для обычного ответа/уточнения и возвращает существующий маршрут. Не добавлять отдельный классификатор, второй LLM-вызов, семантический verifier или словари/regex симптомов. Код не проверяет смысл сообщения до или после модели через словесные правила; прежний медицинский gate должен перестать принимать такие решения на активном пути.
- Переиспользовать существующий `route: ANSWER / ADMIN / CLARIFY`; не создавать рядом независимый router или новые категории `medical_help`, `current_medical_problem`, `emergency`, страхов, сравнений, симптомов и т. п. `ADMIN` охватывает текущую медицинскую проблему, просьбу о персональном диагнозе/назначении, жалобу, конфликтное обращение и просьбу о руководителе/сотруднике. Обычный FAQ, будущие опасения и сравнение услуг остаются `ANSWER`; недостаточный понятный scope — `CLARIFY`.
- Для `ADMIN` сохранить простой действующий принцип `patient_text=null`: индивидуальный текст Composer не выводится, presentation/маркетинг не запускаются. Код показывает одну каноническую заглушку для всех таких случаев. Согласованный смысл шаблона: «Понимаю, что ситуация может вызывать беспокойство. Здесь лучше обратиться к администратору клиники — он поможет с дальнейшими действиями. Если ситуация срочная, пожалуйста, позвоните: {канонический номер текущей клиники}». Точную редакцию можно сделать компактнее без изменения смысла.
- Номер всегда берётся детерминированно из структурированных контактов текущего клиента; модель его не выбирает и не сочиняет. Нет своего номера — не подставлять demo/другую клинику и не выдумывать контакт; шаблон должен корректно материализоваться без чужого номера. Это рекомендация обратиться, а не обещание фактической передачи сообщения администратору.
- Отдельный `emergency` не вводить: одна ADMIN-заглушка уже содержит условный призыв позвонить, если ситуация срочная. В `CLARIFY`, обычный ответ и техническую ошибку эту заглушку/телефон автоматически не добавлять.
- Владелец принимает возможность отдельных ошибок модели ради простой логики и сохранения полезных ответов. Независимой семантической страховки нет; это не обещание безошибочной медицинской маршрутизации и не разрешение выдумывать лечение. Качество оценивать на разнообразных диалогах; offline/fake проверяет проводку, реальное понимание — только отдельно разрешённый модельный эксперимент. Это не выбор Hybrid/FullContext.

**Служебные записи: сначала проверить, потом убрать дубли — утверждено:**

- Для `references.direct_fact_ids` сначала проверить тип списка и корректность каждого элемента по действующему контракту. Затем свернуть только одинаковые корректные ID, сохранив порядок первого появления.
- Не выкидывать молча неверные элементы, чтобы превратить испорченный список в корректный. Например, `["installment_12", "installment_12"]` можно свернуть; `["installment_12", 17]`, список с `null` или пустым ID нельзя «исправлять» удалением плохого элемента. Дубли ключей самого JSON не относятся к допустимым дублям ID.
- Это проверка служебной структуры, не словесная проверка ответа. Узкая нормализация лишних top-level полей при валидных обязательных данных сохраняется; неверные типы, повреждённый JSON и неизвестные вложенные поля не объявляются корректными. Новые причины подавления полезного текста этим решением не вводятся.

### Обязательное дополнение владельца — подключить существующую историю к Composer, 28.08.2026

**Утверждено для ближайшего scope завершения checkpoint 1e; реализовано 29.08.2026 (offline, без LIVE/API).** Прежняя формулировка «память в этом checkpoint не добавляем» больше не означает откладывание передачи истории. Новую систему памяти не создавать: подключена уже существующая переписка к одно-вызовному пути.

**Что установлено чтением кода, без прогонов:**

- В `session.py` уже сохраняются реплики пользователя и бота; `recent_dialog_history` возвращает недавние сообщения (текущий default — шесть сообщений, не шесть пар). HTTP-обвязка обычного и streaming-ответа сохраняет историю с существующими ограничениями для сбора заявки.
- Прежний путь передаёт историю в Planner (`core/turn_planner_llm.py`). Этот механизм есть и в пути с FullContext, а не только в старом RAG.
- Новый one-call путь обходит Planner. В его Composer поступают база клиники, текущий вопрос и служебные подсказки, включая предыдущую услугу, но не тексты предыдущих реплик. Хранилище памяти не исчезло; отсутствует его подключение к этому модельному вызову. Вывод относится к проверенному пути, а не ко всем режимам проекта или конфигурации запущенного сервера.

**Требуемое поведение:**

- Передавать Composer недавние сообщения пользователя и ответы бота из существующей сессии до генерации, вместе с текущим вопросом. Это общее требование к диалогу на всех темах, не отдельная медицинская функция и не специальный случай All-on-4/врачей.
- Модель должна иметь контекст для продолжений «А какой врач делает?» → «А какой у него стаж?», «Почему второй вариант дороже?», «Я именно этого и боюсь», а также смены темы. Не заменять переписку одним `last_service_id` и не добавлять словесные правила для каждого продолжения.
- Сохранить один основной LLM-вызов. Не возвращать Planner, RAG, отдельную модель-пересказчик, новую БД или сложную долговременную память ради передачи истории. Служебная память выбора услуги и показов маркетинга сохраняется отдельно.
- История служит контекстом разговора, не каноническим источником цен, контактов или медицинских фактов. Прошлый ответ бота не должен становиться подтверждением ошибочного факта. Сохранить приоритет актуальных данных клиники и текущего сообщения над устаревшими предположениями.

**Что включить в обновлённый scope и критерии приёмки:**

- Переиспользовать существующее чтение истории; предложить небольшой ограниченный объём на основе текущего helper, без бесконечного накопления в prompt. Точный лимит и затронутые файлы ещё не согласованы. Историю помещать в динамическую часть запроса, не в общий кешируемый корпус клиники.
- Проверить порядок и роли реплик, отсутствие двойного добавления текущего вопроса, передачу ответов, соответствующих тому, что видел пользователь, и изоляцию по клиенту/сессии. Сохранить reset/истечение сессии и существующие ограничения на включение данных заявки; не обходить их сборкой истории из логов.
- Проверить реальный цикл «первый ответ записан → следующий вызов получил историю» для обычного и streaming-путей, а не только вручную заполненную тестовую историю. Не допустить дублей записи и переноса переписки между клиентами.
- Различать текстовую историю и служебное состояние: требование не загрязнять выбор услуги/историю автопоказов при scope-уточнении не запрещает сохранять само уточнение в переписке.
- Offline/fake доказывает передачу нужных реплик, но не понимание продолжений настоящей моделью. Многоходовую оценку качества проводить только при отдельном разрешении LIVE/API; в сравнении моделей/контекстов использовать одинаковую историю.

Сейчас разрешена фиксация этого обязательного дополнения в документах. Реализация checkpoint 1e + correction/finishing pass выполнена Cursor 29.08.2026 offline; checkpoint принят владельцем/Codex и разрешён к отдельной публикации. LIVE/API не выполнялись.

### Checkpoint «Сохранение полезного ответа при мягких ошибках» — 28.08.2026

База публикации: `c577a7b733dfd90cf8020854e3b275d73579cb08` (contacts, price, marketing, commerce). CP-EXACT-1 **не** реализован.

**Статус реализации checkpoint 1e (29.08.2026):** реализовано Cursor поверх той же базы; принят владельцем/Codex; разрешён к отдельной публикации. Stage53/eval WIP сохранён отдельно и не входит в этот checkpoint. CP-EXACT-1 не начинался.

**Что реализовано:**
1. **Маршрутизация Composer:** только `ANSWER / ADMIN / CLARIFY`; смысл определяет модель по текущему сообщению и переданной истории. `local_problem_gate` — только spam/noise; словесные словари симптомов/жалоб/диагнозов удалены с активного пути.
2. **ADMIN:** `patient_text=null`, одна детерминированная заглушка с каноническим телефоном текущей клиники (`canonical_contact_phone`); без marketing/presentation/CTA; положительный отзыв и обычная связь с врачом — `ANSWER`.
3. **История:** `recent_dialog_history` + `format_dialog_context_for_understanding` читаются один раз в widget-runtime и передаются immutable string в dynamic suffix Composer (не в cached FullContext prefix).
4. **`direct_fact_ids`:** сначала структурная валидация всего списка, затем dedupe только корректных дублей; mixed invalid lists отклоняются. Диагностика нормализации — request-local, не process-global.
5. **Scope CLARIFY:** без `fallback_answer_with_phone`; служебное состояние автопоказов не меняется.
6. **Backend failure:** нейтральный технический ответ «Сейчас не удалось подготовить ответ…», не ADMIN и без телефона.

**Offline доказано (fake/wiring):** gate spam-only; fake ADMIN wiring; история JSON/streaming двухходовый цикл; контакты demo/nikadent; dedupe/mixed lists; clarify без телефона; technical failure без второго вызова. **Fake не доказывает:** понимание русского языка моделью, качество маршрутизации на реальных диалогах.

**Прогоны (29.08.2026, offline):** адресный набор checkpoint 1e — 216/216; смежный finishing pass — 206/206. LIVE/API не запускались. Checker ACCEPT. Итоговый commit публикации — в отчёте публикации.

**Ограничения:** leadflow/lead-paused overlay может изменить видимый ответ после выбора текста — существующее ограничение, не расширялось. CP-EXACT-1B, MD-очистка и Hybrid — вне scope; CP-EXACT-1A реализован offline 29.08.2026 (см. ниже).

### CP-EXACT-1A — полный exact-commercial каталог до Composer (29.08.2026)

**Статус:** реализован Cursor offline на базе `41bf8a8`; product/runtime presentation path не изменён. LIVE/API не выполнялись. Stage53/eval WIP сохранён отдельно.

**Что доказано offline (wiring-checkpoint):**
- product/runtime presentation path, authoritative commerce, direct commercial materializer, CP-MKT-1, CTA/UI и маршруты на fake/offline fixtures **не регрессировали**;
- Composer теперь получает полный `EXACT_COMMERCIAL_CATALOG` в stable prefix и `COMMERCIAL_AS_OF` в dynamic suffix;
- fingerprint и cache lookup key меняются при изменении exact-commercial данных и не меняются от одной только runtime-даты.

**Что не доказано этим checkpoint:**
- фактическое поведение **настоящей** модели после расширения pre-model контекста;
- byte-for-byte неизменность реальных model answers до отдельно разрешённого LIVE-сравнения.

Это ожидаемое ограничение wiring-checkpoint, а не дефект реализации.

**Что сделано:**
1. **Stable prefix:** тонкий `COMMERCIAL_FACT_CATALOG` заменён на детерминированный `EXACT_COMMERCIAL_CATALOG` из уже загруженного `ResponseSchemaBundle` (facts + offers + active services). Второй коммерческий блок в prompt не передаётся.
2. **Dynamic suffix:** `COMMERCIAL_AS_OF` с `as_of_date` и `date_eligible_fact_ids` (не automatic-marketing allowlist). Мягкая деградация: `availability=unavailable`, пустой список — основной ответ сохраняется, ADMIN не используется.
3. **Prompt contract v6:** модель видит полные exact-данные для grounding, но не должна самостоятельно вставлять code-owned цены/канонические тексты в `patient_text` и не должна спонтанно рекламировать service_value/promo/amplifiers/warranty. Автоматический маркетинг остаётся за `marketing.yaml` + CP-MKT-1 + существующим presentation pass.
4. **Fingerprint:** stable prefix учитывает полный exact-каталог; смена только runtime-даты не меняет fingerprint; demo/nikadent изолированы.

**Что сознательно не сделано (до CP-EXACT-1B-MULTI-V1):** multi-offer canonical list в видимом ответе, `used_offer_id`, multi-brand ranking, Hybrid/RAG, LIVE.

**Offline (29.08.2026):** CP-EXACT-1B-SINGLE — 38/38 в `test_one_call_exact_1b_single_offline.py`; checkpoint_a — 33/33; scoped-evidence suites синхронизированы в **CP-SCOPED-EVIDENCE-SYNC-SAFE** (см. ниже).

### CP-SCOPED-EVIDENCE-SYNC-SAFE — test sync + post-Composer typed fail-open (29.08.2026)

**Статус:** реализован Cursor offline на базе `66591e7`; checker pending. LIVE/API не выполнялись. Stage53/eval WIP сохранён отдельно.

**Что сделано:**
1. Синхронизированы stale fixtures/tests после CP-MKT-1 (`c577a7b`): promo-only automatic pool; `scenario_rules` не исполняются selector'ом.
2. External KB assertions переведены на явную инъекцию согласованных `plan/materials.external_source_refs` в unit/governance tests — без возврата scenario→KB wiring.
3. Узкий post-Composer fail-open в `_build_verified`: только `TargetScopedResponseEvidenceError` и `TargetComposerRequestError`; готовый `patient_text`/price/marketing сохраняются; диагностика `post_composer_evidence_degraded` + `post_composer_evidence_error_code`; `TypeError` не подавляется.
4. Strict `build_target_scoped_response_evidence` при прямом вызове без изменений.

**Offline:** scoped/composer/assembly suites green; widget degraded-path tests; CP-EXACT-1B + checkpoint_a regression green.

### CP-EXACT-1B-SINGLE — isolated `price_text` for one pre-selected fixed offer (29.08.2026)

**Статус:** correction pass + finishing pass Cursor offline на базе `18fe65b`; checker ACCEPT. LIVE/API не выполнялись. Stage53/eval WIP сохранён отдельно.

**Поддержанные production-path случаи (demo):**
- `tomography` — singleton fixed offer (`tomography.default`, 3 000 ₽) при authoritative `service_id`.
- `all_on_4` + ровно один бренд из закрытого каталога (`Implantium` / `Impro` / `Nobel Biocare` и aliases) при authoritative `service_id` из governed UI / exact_turn / valid_session.
- Продолжение диалога: `Сколько стоит All-on-4?` → `А Nobel?` — `service_id` из fresh `valid_session`, `brand_id` из текущего сообщения (offline wiring-checkpoint; понимание русского реальной моделью не доказано).

**Сознательно не поддержано в 1B:** multi-brand/multi-offer в одном сообщении; подмена бренда; `from`/`range`/`no_public_price`; `jaw=both`; арифметика; `used_offer_id`; model-selected offer; multi-offer.

**Что сделано:**
1. `resolve_precomposer_selected_offer_for_turn` — pre-model resolver + catalog-driven brand mention extraction (`core/target_brand_mention_extraction.py`) + session `valid_session` для follow-up без нового service term.
2. Dynamic `SELECTED_EXACT_OFFER` в suffix (не в stable prefix / fingerprint / history).
3. Envelope/prompt contract **v8:** top-level `price_text`; `patient_text` остаётся основным prose; `used_offer_id` отсутствует.
4. Узкая post-model validation только `price_text` + canonical fallback; **`patient_text` не редактируется** на precomposer path (legacy sanitizer на других путях без изменений).
5. Видимая цена только при `commercial_intent=price`; pre-model selection допустим раньше, но non-price turn не добавляет цену автоматически.
6. Presentation order: `price_text|fallback` → `patient_text` → promo/amplifiers (price profile, без `service_value`) → CTA/UI; legacy authoritative price block отключён на eligible turn.
7. Observability: `price_text_patient_monetary_amount` при любой сумме в `patient_text` на price-turn; route/ADMIN/CLARIFY не меняются.

**Brand mention contract:** casefold; word/phrase boundary match по `canonical_name`, `aliases`, `brand_id`; без fuzzy/substring-in-word; 0 или 2+ брендов → fail-closed; alias collision → typed ambiguity.

**Residual risk:** модель может вставить сумму в `patient_text` — допустимый наблюдаемый residual; каноническая `price_text` line обязательна; удаление предложений из `patient_text` запрещено.

### CP-EXACT-1B-MULTI-V1 — canonical multi-offer price list (30.08.2026)

**Статус:** реализован Cursor offline на базе `58c4af5`; correction pass (unsafe eligible-set validation, no internal offer_id labels, jaw-scenario acceptance) — offline; checker pending. LIVE/API не выполнялись. Stage53/eval WIP сохранён отдельно.

**Multi V1 runtime coverage (demo, structural gate: uniform jaw fixed offers):**
- `all_on_4` — 3 brand offers (Implantium / Impro / Nobel Biocare; 318 000 / 368 000 / 428 000 ₽).
- `all_on_6` — 3 brand offers (398 000 / 458 000 / 528 000 ₽).
- `removable_dentures` — 2 option offers (Частичный / Полный съёмный протез; 45 000 / 65 000 ₽).

**Поддержанные production-path случаи (demo v1):**
- jaw-сервис без бренда/опции → `availability=multiple`, 2–3 jaw fixed offers в neutral catalog order.
- один бренд → прежний single path (`availability=selected`, `price_text`).
- два бренда в сообщении → filtered multi (catalog order); если active остался один — `selected`.
- Неизвестный бренд → известные offers, без выдуманного бренда.
- Non-price / broad-family price / `classic` per-tooth overview — без multi list.
- Unsafe eligible set (malformed/mixed fixed+from/>3/mixed billing units) → `availability=none` + diagnostic; **без partial list**; legacy ranked overview blocked; `patient_text` сохранён.
- Patient-facing labels только из `brand_catalog.canonical_name` или `service.options[].name`; internal `offer_id` не показывается.

**Что сделано:**
1. Contract `none|selected|multiple` + fail-fast invariants; generic resolver без service hardcode; neutral `brand_catalog` order; full eligible-set validation до formatter.
2. Dynamic `SELECTED_EXACT_OFFER` payload для `multiple`; prompt contract **v9** (`price_text=null`, patient_text без сумм).
3. `core/one_call_multi_offer_price_block.py` — code-owned canonical list + дословный shared `package.label`; без fallback на `offer_id`.
4. Presentation `precomposer_multi_price_turn`: list → patient_text → promo → amplifiers → CTA; без `service_value` на price profile; widget v1 text-only (без `offers[]`).
5. Diagnostics: `precomposer_offer_availability=multiple`, `multi_price_owner=canonical_multi`, `multi_patient_monetary_amount`, `multi_attempted_but_unsafe`, `unexpected_multi_price_text`.

**Structural v1 gate:** multi активируется только при uniform `billing_unit=jaw` у 2–3 eligible fixed offers. Per-tooth `classic` / `one_stage` остаются на legacy overview — не маркируются как повреждённые.

**Сознательно не в v1:** `from`/range support; новый public UI contract; model `price_text` на multi; service_id hardcode в production.

### CP-STAGE3B-EVAL-SYNC — Stage3B eval aligned with current prefix contract (30.08.2026)

**Статус:** реализован Cursor offline на базе `973bd35`; LIVE/API не выполнялись. Stage53/eval WIP сохранён отдельно.

**Проблема (baseline debt на `973bd35`):** `tests/test_one_call_stage3b_offline.py` — 58 collected → 43 passed, 15 failed. Причины: (1) устаревший expectation `<EXACT_SALES_RESOLUTION>` в dynamic suffix; (2) `evals/v5/one_call_flash_capability_plan.py` вызывал `build_one_call_stable_prefix()` без `service_reference_catalog` / `exact_commercial_catalog`.

**Что сделано:**
1. `build_demo_eval_stable_prefix()` передаёт канонические `ServiceReferenceCatalogSnapshot` и `ExactCommercialCatalogSnapshot` из demo bundle через production builders.
2. Cache suffix test синхронизирован с текущим dynamic contract: `<PRE_MODEL_HINTS>` + `resolution_hint`, без восстановления `<EXACT_SALES_RESOLUTION>`.
3. Добавлен `TestStage3bCacheContract`: stable prefix содержит service/exact catalogs; deterministic fingerprint; catalog change → fingerprint change; dynamic suffix меняется между ходами; `SELECTED_EXACT_OFFER` только в dynamic suffix (single/multi), не в stable prefix.

**Граница cache (актуальная):** stable prefix = contract + policy + catalogs + corpus; dynamic suffix = `COMMERCIAL_AS_OF` + `SELECTED_EXACT_OFFER` (при наличии) + `PRE_MODEL_HINTS` + `USER_MESSAGE_DATA`.

**Offline:** `test_one_call_stage3b_offline.py` — 65/65; смежные cache/prompt/one-call regressions green. Product runtime не менялся.

### CP-ARCH-COMPARE-OFFLINE-V1 — offline 4-way architecture compare stand (30.08.2026)

**Статус:** реализован Cursor offline на базе `c7c58b6`; LIVE/API не выполнялись. Stage53/eval WIP сохранён отдельно. Hybrid не выбран.

**Что сделано:**
1. Новый eval namespace `evals/v5/arch_compare/`: 4 config_id (`flash_full`, `flash_curated`, `plus_full`, `plus_curated`), frozen matrix 16 scenarios / 19 turns, curated context из канонических MD refs без ручных выдержек.
2. FullContext через production `build_one_call_stable_prefix`; curated — subset того же corpus snapshot по allowlist refs.
3. Parity: одинаковые exact/service catalogs, `COMMERCIAL_AS_OF`, dynamic suffix и session history; full vs curated отличаются только content-context block.
4. Fake transport + dry-run: 0 provider/network calls; blind review A–D без утечки config/model/context.
5. Plus `provider_model_id` зафиксирован owner snapshot: `qwen3.7-plus-2026-05-26` (официальные источники Alibaba Model Studio — text-generation, pricing, context-cache; checked 2026-08-30). Flash snapshot: `qwen3.7-flash-2026-07-15`.

**Граница:** fake/offline доказывает wiring и parity, **не** качество модели. Presentation/widget decomposition через public response boundary (`full` / `terminal_boundary_full` / `code_only_boundary_full`); без regex/sanitizer и без `visible_answer=patient_text` fallback.

**Offline:** arch_compare offline + regressions (Stage3B, exact single/multi, commercial prompt, Stage3A) green.

**Публикация (30.08.2026):** commit `ce3a467` остановлен до push — snapshot REJECT: `frozen_matrix_digest()` хешировал сырые байты JSON; correction `cc42fc4` нормализует только переносы строк. Оба commit опубликованы на `cc42fc4`.

**CP-ARCH-COMPARE-LIVE-PREP-V1 (30.08.2026):** eval-only подготовка coordinated LIVE attempt: Latin rotation schedule (16×4 scenario/config, 19×4 turn/config), session/config isolation, capability preflight budget **2** + measurement **68** = **70** authorized provider calls, default-deny guard, mock preflight state machine, boundary capture, structured fields + blind review pack, fake full-path runner (`run_arch_compare_live.py`). Inference settings Flash/Plus идентичны production Composer (`enable_thinking=false`, `temperature=0`, `max_completion_tokens=1024`, `response_format=json_object`). LIVE/API не выполнялись; offline readiness **`READY_FOR_AUTHORIZED_PREFLIGHT`**. Optional cache probe **4** — отдельно, не входит в 70.

**CP-ARCH-COMPARE-LIVE-RUNNER-V1 (30.08.2026):** guarded LIVE branch подключён к существующему production provider client (`llm.chat_completions_create`) через eval-only адаптер `arch_compare_live_transport.py`. Схема: authorization guard → `create_guarded_live_transport()` → Flash preflight → Plus preflight → 68 measurement → artifacts + blind review. Default deny сохранён: без `--live`/manifest/credentials/real key transport не создаётся; unconditional `LIVE_RUNNER_NOT_ENABLED_IN_PUBLISHED_SNAPSHOT` заменён на guarded path. Offline: mock provider client, 0 network/provider calls. Статус: **`READY_FOR_AUTHORIZED_PREFLIGHT`** (реальный LIVE на этом checkpoint не запускался).

### CP-MD-COMMERCE-1 — очистка demo MD от structured commerce-дублей (29.08.2026)

**Статус:** реализован Cursor offline на базе `41bf8a8` + companion CP-EXACT-1A WIP. LIVE/API не выполнялись. Stage53/eval WIP сохранён отдельно.

**Что сделано:**
1. Удалён `clients/demo/md/clinic__info__payment_terms.md`; `detail_ref` на него убраны у `tax_deduction`, `installment_12`, `payment_stages`, `fixed_price` в `facts.json`.
2. Очищены demo MD: `consultation`, `implantation__faq__cost`, `tooth_loss`, `curator`, `benefits`, service scope-дубли в pterygoid/zygomatic/prosthetics/comparison. `free_implant_consult` в structured data не менялся.
3. Из `marketing.yaml` cost-сценария убран kb-ref на удалённый payment-документ.
4. Prompt contract **v7:** семантические примеры общего cost objection (`route=ANSWER`, `scenario=cost`, `commercial_intent=none`) vs прямого ценового вопроса (`commercial_intent=price`). Без regex/Python-классификатора.
5. Ожидаемая сборка cost objection: полезный ответ из оставшегося cost FAQ → optional `service_value` по profile → до 2 promo → до 2 amplifiers → CTA/UI отдельно.

**Что не доказано:** фактическое поведение настоящей модели на live-фразах cost objection; wiring-checkpoint only.


- История автоматических показов общая на весь диалог по стабильному ID: смена услуги не разрешает повтор уже показанного общего усилителя. По новой услуге можно показать её подходящие, ещё не показанные элементы. По прямому запросу сведения сообщаются повторно.
- Гарантию, собственную лабораторию и прочие сведения о клинике **сохранить в базе demo как информацию о клинике**. Прежние слова «гарантию удаляем» и «остальное удаляем» относятся к исключению из автоматических маркетинговых дополнений, а не к удалению знаний. Эти сведения остаются доступны для содержательных ответов на соответствующие вопросы; наличие в базе само по себе не разрешает рекламную вставку в посторонний ответ.
- Это фиксация продуктовых решений в ходе обсуждения новой схемы автодобавок, не отчёт о её реализации. Изменения кода, тестов и клиентских данных сейчас не разрешены; LIVE и git-публикация также не разрешены.

### Текст и коммерция

- Основной ответ — по вопросу пользователя; не вводить классификатор «простой/сложный» или жёсткий счётчик предложений.
- Новая продуктовая схема 28.08.2026 заменяет прежний общий лимит двух коммерческих элементов. Обычный вопрос об услуге: основной ответ → максимум один `service_value` → до двух промо текстом → до двух усилителей списком. Ценовой вопрос: ответ с ценой и существенными условиями → до двух промо → до четырёх усилителей списком; автоматического `service_value` в этой схеме нет.
- Заголовок списка усилителей — «Также мы предлагаем:». Пустые блоки и заголовки не выводить; до лимита искусственно не добирать. Дополнения допустимы с первого подходящего ответа. CTA/follow-up/situation/UI остаются отдельной существующей логикой.
- Набор и привязку к конкретным услугам контролирует владелец. Рассрочка — первый усилитель, если доступна и ещё не показана; остальные — простой заданный порядок без semantic scoring. Актуальность, применимость и явно заданную совместимость проверять; не придумывать ограничения клиники.
- Каждый автоматический элемент показывается один раз за диалог по стабильному ID; смена услуги не сбрасывает историю. По новой услуге доступны её ещё не показанные элементы. По прямому вопросу повтор допустим. Прямые вопросы об акциях, рассрочке, гарантии и других условиях — основной ответ, не ограниченный квотой автодобавок. Лимиты автоматических блоков относятся ко всему ответу, не умножаются на число упомянутых услуг.
- Полный канонический факт хранится один раз вне MD; привязки к услугам — по ID. В MD остаются полезные объяснения и при необходимости ссылки-ID, не повтор маркетингового текста. Не включать `service_value` в поисковый контент как дублирующую рекламную вставку. Предлагается использовать существующие `pricebook/facts.json` и `marketing.yaml`; окончательный формат привязок ещё требует технического scope, два источника одних привязок не создавать.
- Связь «факт нужен для ответа» не равна «факт разрешён как реклама»: рассрочка в теме оплаты — основной ответ, в All-on-4 — возможное дополнение. Одно и то же условие не повторять в основном ответе и автоматическом блоке.
- Эмпатия — существующая ручная рекомендация в MD, не обязательный шаблон.
- Бесплатная консультация и её короткая польза — один promo. Отдельный дублирующий `consultation_value` не добавлять; существующие поля MD удалить при содержательной миграции после сохранения нужного смысла. Это заменяет прежнее требование сохранять самостоятельный автоматический блок `consultation_value`.

### Утверждённое наполнение demo — уточнение 28.08.2026

- Это условная demo-клиника без реальных коммерческих данных. Владелец разрешил подготовить согласованное демонстрационное наполнение; не представлять коммерческие предложения как обязательные стоматологические стандарты. Изменения клиентских файлов выполняет Cursor в отдельно разрешённом checkpoint.
- Сохраняются три акции. Бесплатная **консультация** относится только к имплантации и протезированию; слова владельца «бесплатная имплантация» подтверждены как опечатка и не являются новым предложением бесплатного лечения. Польза внутри promo: «На консультации подготовим три варианта плана лечения по стоимости, чтобы вы могли выбрать подходящий под свой бюджет». Уточнение об отдельной оплате КТ сохраняется. Отдельный усилитель «три варианта стоимости» не создавать.
- Скидка на отбеливание — 10%, срок до **30 ноября 2026**, `active_until: 2026-11-30`. Это подтверждённое исправление даты «31 ноября»; обновить и текст, и структурированную дату в будущем data-checkpoint. Условия остальных акций без отдельного решения не менять.
- Создать ровно **два канонических service_value**: первый объединяет 3D-планирование и Diagnocat, второй посвящён APRF. Подготовить короткие тексты и распределить по имплантационным услугам существующего каталога, максимум один ref на услугу. Это два варианта для каталога, не два абзаца в одном ответе. Точные тексты и таблица распределения ещё не подготовлены.
- Имплантация и протезирование: обычный ответ — рассрочка до 12 месяцев и помощь в оформлении налогового вычета; ценовой — те же два усилителя плюс оплата по этапам и фиксация стоимости в договоре.
- Все остальные услуги: помощь в оформлении налогового вычета и фиксация стоимости — **как в обычном, так и в ценовом ответе**; других усилителей не добавлять. Следовательно, фиксация стоимости не является глобально `price-only`: разрешённый набор зависит и от услуги, и от типа ответа. Общие правила актуальности, истории и прямых вопросов сохраняются.
- `clients/demo/md/clinic__info__payment_terms.md` **удалён** в CP-MD-COMMERCE-1 (29.08.2026); канон — `installment_12`, `tax_deduction`, `payment_stages`, `fixed_price` в `facts.json`. Гарантия, лаборатория и прочие знания о клинике сохраняются.

### Рабочая схема сборки ответа — для будущего checkpoint и сравнения

- Необходимые точные данные поступают ДО Composer. Модель пишет основной ответ по вопросу и использует нужные факты, но не добавляет незапрошенную рекламу. Суммы, сроки и ограничения не сочинять; неизвестную смету не рассчитывать.
- Предложенный контракт: текст основного ответа + отдельный список использованных fact IDs. Код проверяет допустимость ссылок; соответствие ID фактически использованным в тексте данным и точность условий — обязательные критерии проверки, а не гарантия от самого наличия списка.
- Код собирает утверждённые автоматические блоки: исключает факты, уже использованные в основном ответе или ранее показанные в диалоге, проверяет применимость и лимиты, затем сохраняет историю фактически выданных элементов. Прямой запрос разрешает повтор; optional-сбой не должен уничтожать основной корректный ответ.
- Затем работает существующий CTA/UI. Схема совместима с FullContext и возможным Hybrid; это рабочая гипотеза для проверки, не окончательный Architecture Lock. Полная передача коммерческих фактов до модели ещё не реализована, изменение нынешнего распределения обязанностей модели и кода требует отдельного задания Cursor.

### Очистка MD — после подключения канонического источника

- Очищать MD не от всех фактов вообще, а от дублей тех сведений, для которых выбран и подключён канонический структурированный источник: условия акций/рассрочки, утверждённые маркетинговые тексты и другие явно мигрируемые записи.
- Порядок: перечень «что и куда переносим» → сохранение полного смысла в канонической записи → работающая передача и сборка ответа из неё → удаление дубля из MD с проверкой прямых вопросов и привязок. Не оставлять период, когда сведения удалены из MD, но недоступны ответу.
- Полезные объяснения об услугах и клинике, включая гарантию и лабораторию, сохранить. Если конкретное условие перенесено в структурированные данные, сохранить доступ к нему для прямого ответа; исключение из рекламы не является удалением знания.
- Нужные aliases, anchors, ссылки и UI metadata сохранить или явно перенаправить. Не удалять документ целиком автоматически; если после переноса в нём нет собственного полезного содержания, судьбу документа решить после проверки его потребителей. Пустые документы ради формы не создавать.
- Сейчас зафиксирован план; очистка MD, новые данные и реализация схемы в этом обсуждении не выполнялись и не разрешены.

**История checkpoint 28.08.2026 — прежняя упрощённая механика автодобавок:**

- Реализован offline путь: основной ответ → опциональный `service_value` → до двух автоматических коммерческих элементов → существующие UI/CTA.
- Finishing pass: узкая граница optional-ошибок; прямой перечень несовместимых акций без silent-filter; автодобавки учитывают eligible direct facts как контекст совместимости; widget/session цикл `service_value` на изолированном тест-пакете; dedicated streaming-проверка; fallback `extract_target_session_selection` в активном materialized-пути недостижим.
- Точечный pass 28.08 (2 ошибки): контекст совместимости сохраняется при выборе усилителей; optional-сбой при `commercial_intent="promotion"` не уничтожает materialized direct-ответ; недоступный direct promo → контролируемая фраза, не подмена другими акциями.
- По финальному отчёту Cursor: 141/141 offline-тестов; checker подтвердил поведение, но оставил REJECT из-за несамодостаточного для коммита scope без companion-файлов. Codex принял техническую часть прежней механики по адресному разбору; это не означает финальный ACCEPT checker или разрешение коммита.

**CP-MKT-1 (28.08.2026):** реализованы независимые лимиты промо/усилителей, профили `service`/`price`, список усилителей в presentation pass, `service_automatic_commercial` в контракте; demo `marketing.yaml` обновлён структурно (лимиты, гарантия убрана из `ordered_amplifier_refs`). Offline: 149/149 адресных тестов маркетинга.

**CP-MKT-1 correction pass (28.08.2026):** три замечания Codex закрыты offline без LIVE и без изменения demo-наполнения. (1) Разделены автоматические и прямые пути акций. (2) Жёсткие потолки в схеме. (3) Полный ценовой widget-сценарий на изолированном пакете. Offline: 162/162 адресных тестов CP-MKT-1+correction.

**Demo commerce checkpoint (28.08.2026):** наполнены `facts.json`, `service_catalog.json`, `marketing.yaml` для demo: 3 promo, 4 автоматических усилителя, 2 `service_value`, явные `service_automatic_commercial` для 22 активных услуг; гарантия сохранена для прямых ответов, не в автосписках; дата отбеливания 2026-11-30. Offline: 172/172 адресных тестов commerce+CP-MKT-1. MD не менялись.

**Demo commerce correction pass (28.08.2026):** из `free_implant_consult` убрано внутреннее пояснение «не бесплатное лечение/операция»; в `_orchestrate_ask` исправлен порядок `bind_session_client("demo")` → `mem_reset`; усилена проверка обеих акций на price All-on-4; добавлена регрессия загрязнения клиентской привязки. Offline: 174/174. Runtime/привязки не менялись.

**Карта MD-миграции demo commerce (обновлено CP-MD-COMMERCE-1, 29.08.2026):**
| Исходное сведение в MD | Канон / сохранение | Что перенаправить |
| --- | --- | --- |
| `clinic__info__payment_terms.md` — рассрочка, вычет, этапы, фиксация | **удалён**; канон — `installment_12`, `tax_deduction`, `payment_stages`, `fixed_price` в `facts.json`; этапы сумм в offers | `detail_ref` убраны; cost FAQ очищен от commercial-дублей |
| `consultation_value` в implantation MD (3 файла) | польза «три варианта плана» внутри `free_implant_consult`; отдельный автоблок выключен | consultation MD нейтрален; promo fact не менялся |
| Дубли скидки/рассрочки в service MD | promo/amplifier refs в `marketing.yaml` | scope-дубли offers убраны из service/comparison MD |
| `clinic__info__warranty.md` | `implant_warranty` (прямой ответ, не автодобавка) | scenario `result_reliability` kb-refs |
| Гарантия/лаборатория в technology/warranty MD | знания о клинике, не автоматическая реклама | сохранены без содержательной чистки |

Полное demo-наполнение consultation_value в MD, exact facts до модели и выбор архитектуры — открытые пункты.

### UI и CTA

- В обычном ответе два secondary-слота; порядок: видео → кейсы → «Рассказать о ситуации» → follow-up, заполняющие остаток. Условия/ссылки берутся из основного MD, без отдельного semantic UI planner.
- Видео/кейсы показываются при наличии доступного материала; ситуация — при разрешении темы. Показанные/нажатые secondary не выводятся повторно. Точные ID и обновление истории после выдачи — инженерная задача.
- CTA отдельно, существующая механика сохраняется; CTA не занимает secondary-слоты.
- Ценовой вопрос: предусмотренные offer кнопки «Что входит» / «Оплата по этапам», до двух. Не добавлять их поверх обычных secondary. Само упоминание цены или акции не делает ответ ценовым.
- «Один зуб / Несколько зубов / Вся челюсть» — самостоятельный режим выбора, не смесь с follow-up.
- Использование текста MD в ценовом ответе не требует вывода его обычных кнопок.
- Situation intake сохраняется: описание ситуации → сохранение note → имя → телефон. Не придумывать новый медицинский диалог после описания.

### Данные demo

- Структуру клиентского пакета сохраняем по смыслу, не переписываем все MD с нуля.
- DoctorCatalog — точные ФИО, должность, стаж, услуги. MD — биография/подход. Обзор команды — промо без имён; «кто имплантолог?» — конкретные специалисты.
- Цены/единицы/пакеты и платежи — Pricebook. «Что входит» нужно сложным пакетам; пустой includes у простой услуги не дефект.
- Владелец делегировал исполнителю самостоятельную подготовку стоматологически согласованного демо-прайса. Выбранные решения и их обоснование — §6.6 аудита. Это demo, не реальная смета клиники.
- Известную цену единицы можно сообщить и при нескольких зубах/двух челюстях; неизвестный общий итог не придумывать. Не строить общий калькулятор без отдельной задачи.
- Artgents в нынешнем `brand.yaml` записан как clinic_name, но владелец уточнил: это название его продукта, не клиники. Не закреплять его как обязательное имя клиники в тестах.

### Контакты и подтверждённое нарушение изоляции

- Телефон, WhatsApp, адрес, график и парковка хранятся в одном структурированном источнике соответствующей клиники; сейчас это `clients/<client_id>/clinic_policies.yaml`.
- `clients/demo/md/clinic__info__contacts.md` сейчас содержит лишь заглушку «точные контактные данные указаны в официальных материалах». Такой MD не обязателен для любой из рассматриваемых архитектур и не должен заменять ответ с доступными контактами.
- При миграции проверить consumers и ссылки, сохранить нужные aliases/CTA, после чего заглушку можно удалить. Содержательный MD «как пройти / где вход» допустим, если действительно есть полезный текст. Не создавать пустые MD ради унификации.
- PREPARE и все последующие пути ответа берут контакты только из текущего клиентского контекста. Запрещена подстановка demo или другой клиники при ошибке загрузки, отсутствии контакта или неопределённом клиенте.
- Это правило действует для обычного ответа, error/fallback, ADMIN и срочного сценария, включая контактные ссылки/кнопки, если они есть. Недоступность своего контакта не оправдывает чужой номер; основной доступный ответ сохраняется.

Подтверждённый случай: CP2 LIVE `one_call_stage53_live_v2_f970b6f_2026-08-27-01`, кейс `s53_f02_nika_promo_overview`, `client_id=nikadent`, вопрос «Какие акции у вас есть?». В ответе об ошибке появился телефон demo `+7 (495) 128-47-60`. Доказательство: [существующий raw_turns.json](<C:/Cursor Projects/demo-bot-one-call-baseline/evals/v5/artifacts/stage53/one_call_stage53_live_v2_f970b6f_2026-08-27-01/raw_turns.json:2777>). Это не новый LIVE-прогон. Точная причина в коде в этом обсуждении не установлена, исправление не выполнено. Успешный j01 cache-isolation не доказывает корректность всех error/fallback-путей.

В новом checkpoint изоляции проверить offline: контакты demo; контакты Никадент и выбранного филиала; ошибка/ADMIN у Никадент без контактов demo; отсутствие своих контактов без чужого fallback; переключение клиник и cache/session без переноса контактов. Проверять реальные пути сборки ответа, не один helper. Не воспроизводить старый LIVE ради повторного доказательства.

## 4. Что реально сделано

- Read-only аудит всех 102 файлов demo: 55 MD, 32 ценовых предложения, 6 врачей, конфигурации и потребители.
- Все 32 offers прошли изолированную Pydantic-проверку; суммы всех 12 платёжных схем сошлись; 87 H3 follow-up ссылок существуют.
- Создан подробный аудит с последующими решениями владельца. Клиентские данные и runtime этим обсуждением НЕ изменены.
- Инвентаризация и продуктовые решения выполнены частично по прежнему плану; данные ещё не оптимизированы. Нумерация новой дорожной карты изменена: выбор архитектуры следует ПОСЛЕ эксперимента. Старые «этапы 1–2» нельзя объявлять реализованными.
- Нет необходимости заново читать всю переписку или весь репозиторий. Начать с этого файла и дорожной карты; аудит читать адресно.

## 5. Инструкции и короткий этап 0

28.08.2026 синхронизированы `.cursor/agents/checker.md`, `REVIEW_CHECKLIST.md`, `.cursor/rules/00-guardrails.mdc`. Для текущей программы сравнения ни FINAL_FULLCONTEXT_ONLY, ни Prepared Hybrid не предрешают результат. Это ограниченное исключение для планирования/проверки эксперимента, не разрешение менять production wiring.

Этап 0 по документации закрыт: источник требований — этот handoff, новая дорожная карта и конкретное согласованное задание. В новом чате достаточно один раз сверить git/WIP и перейти к scope подготовки данных и тестам. Не повторять полный аудит или многодневное согласование инструкций.

Старый `TASK.md` (A9R), `docs/STRANGLER_ROADMAP.md` и архитектурные Lock остаются историей/контрактом существующего runtime, а не заданием на новую реализацию. Код меняется только по отдельному разрешённому checkpoint. Проверки — по риску и scope; docs-only не требует pytest, LIVE, чистого дерева или re-pin CP2. Checker сохраняет независимость и не исправляет код сам.

## 6. Git/WIP и окружение

Не включать в новый checkpoint и не удалять:

- `.cursor/agents/checker.md` — предсуществующий WIP с согласованной точечной правкой инструкций 28.08; не откатывать и не включать автоматически в продуктовый checkpoint;
- CP2: contract/matrix/fake_transport/harness, stage53 offline test, untracked LIVE runner/helpers/tests;
- `.codex/**`, `evals/__init__.py`, `evals/v5/artifacts/**`, `evals/v5/reports/**`.

Нет требования получить полностью чистое дерево. Достаточно один раз отделить затрагиваемые пути от чужого WIP. Новые handoff/roadmap/audit тоже пока не закоммичены.

Исторический CP2 LIVE выполнен на snapshot `f970b6fe45b96ba7ef92c308dfb5ff99b36047ce` (не на текущем опубликованном HEAD `c577a7b`): 35/46, бюджет 40/40, активация FAIL; patient TTFT p95 = 6668 мс при пороге 6000. Его не повторять без нового разрешения владельца, не переоткрывать attempt и не чинить старую матрицу ради нового эксперимента. Gate закрыт; никаких новых provider calls сейчас не разрешено. Этот результат не изолирует влияние модели, данных и сборки ответа.

В аудите не удалось найти рабочий проектный Python; bundled Python имел Pydantic, но не PyYAML/frontmatter. Поэтому полный pytest тогда не выполнялся. Перед первым кодовым тестом найти штатное окружение либо подготовить его по зависимостям проекта; не маскировать отсутствие среды fake PASS. Для docs-only этапа полный pytest не нужен.

## 7. Что уже выяснено об истории поиска

Read-only разбор истории уже проведён. Не начинать его заново без конкретного вопроса:

- Ранний RAG находил MD-фрагменты, но финальный generator был ограничен одним источником. Позже появился Controlled Composer с подготовленными данными, затем FullContext. Это были изменения нескольких частей системы, не чистый эксперимент RAG против FullContext.
- PERF-6 был shadow; PERF-7 builder и PERF-8/9 поисковые эксперименты не доказывают работу нового RAG в product Composer. Их нельзя описывать как уже успешный production RAG, который просто откатили.
- PERF-7: нужный факт мог отсутствовать, хотя наличие любого content ref считалось закрытым дефицитом. Уже выбранный upstream документ мог предотвратить дополнительный поиск. Это не доказательство, что builder вырезал найденный правильный абзац: он передавал целые MD. Нужны три отдельные проверки: найдено → передано → использовано в ответе.
- Первоначальный PERF-7C PASS был недостоверен: часть expectations воспроизводила ошибочный результат, классификация пропускала неверные selected-пакеты. После исправления оценки: 118 случаев, 10 неправильных widened-пакетов. Builder этим не был исправлен.
- PERF-8: без embeddings; консервативные lexical-правила убрали критические ошибки на dev ценой примерно 86–88% fallback. Это не доказательство качества ответов.
- PERF-9: embeddings улучшили recall, но holdout всё ещё дал 4 критических ошибки dense и 2 fusion; fallback примерно 52% / 75%. Иногда нужный документ был вторым/третьим, иногда не попадал в top-3. Нельзя исправить всё только выдачей нескольких документов.
- FullContext fallback помогал расширить контекст при распознанном дефиците, но не при уверенном неверном выборе. Не доказано, сколько реальных ответов он спас: Composer в этих eval не проверялся. Fallback также не создаёт отсутствующие structured facts.

Источники для адресного чтения: `docs/evidence/performance/PERF7C_LOCAL_EVIDENCE_PACKAGE_EVAL_AUDIT.md`, `docs/evidence/performance/FINAL_RETRIEVAL_RELEVANCE_DECISION_AUDIT.md`, `docs/evidence/performance/PERF9_QWEN_EMBEDDINGS_HOLDOUT_DECISION.md`, `evals/v5/perf9_qwen_holdout_result.json`, `core/target_evidence_package_builder.py`.

## 8. Что читать дальше и первое действие нового чата

- `docs/PREPARED_HYBRID_ROADMAP.md` — новая рабочая дорожная карта и предложение по тестам.
- `docs/audits/DEMO_CLIENT_PREPARED_HYBRID_AUDIT_2026-08-27.md`: §1 — принципы; §6/6.6 — цены; §7 — врачи; §8 — текст/факты/consultation_value; §9 — UI; §12 — задачи. Приложения — по необходимости.

От нового чата Codex требуется архитектурная работа: принять закрытие документального этапа 0, один раз сверить репозиторий, адресно оценить передачу exact data до модели и предложить небольшой первый checkpoint плюс тестовый план четырёх вариантов. Подготовить задание Cursor с критериями и запуском отдельного checker на стороне Cursor. Финальный Architecture Lock — после результатов, не сейчас. Не переоткрывать согласованные продуктовые вопросы. Codex не начинает реализацию, тестовые прогоны или запуск checker; LIVE никому не разрешён без отдельного согласования.
