# REVIEW_CHECKLIST — универсальный чек-лист Ревьюера

Постоянный, стабильный. По нему **Агент-Ревьюер** проверяет дифф Исполнителя **до коммита**.
Меняется редко (это инварианты проекта). Критерии конкретной задачи — в текущем согласованном prompt/checkpoint-документе или явно указанном разделе `TASK.md`, не во всём историческом TASK.

## Уточнение владельца 28.08.2026 — область текущего эксперимента

Для программы `docs/PREPARED_HYBRID_HANDOFF.md` / `docs/PREPARED_HYBRID_ROADMAP.md` это уточнение имеет приоритет над несовместимыми историческими пунктами ниже:

- Codex — архитектор: анализ, решения, задания и критерии, разбор отчётов. Cursor — исполнитель кода/тестов и запускает отдельного независимого checker в Cursor. Codex не реализует код и не запускает тесты/checker; git-публикацию выполняет Cursor с соответствующим разрешением владельца.
- Сначала подготовка данных и exact facts до генерации, затем сравнение Flash/Plus × FullContext/ручной контекст. Hybrid не выбран заранее. §C2 не запрещает согласованное сравнение, но изменение runtime требует отдельного checkpoint; текущий production-контракт не отменён задним числом.
- Scope, allowlist и acceptance берутся из текущего задания; старый TASK A9R не применяется автоматически. Чужой WIP сохраняется, чистое дерево не обязательно при отделённых границах.
- Бот локальный. Не требовать LIVE-паритета старых ответов, новых их снимков, shadow/dual-run и re-pin CP2. Реальные вызовы — только с отдельным разрешением; docs-only не требует pytest.
- Отсутствие факта/обычная uncertainty сами по себе не terminal defer/ADMIN: честный grounded ANSWER, при необходимости администратор уточнит. Диагнозы/назначения и проблемные обращения остаются в согласованной короткой границе.
- Точность чисел и сила медицинских/юридических утверждений обязательны, но побуквенное совпадение всего ответа и общий числовой постфильтр не требуются. Ошибка optional-добавки не уничтожает основной ответ.
- Авторское изменение демо-данных по разрешённому scope допустимо; выдумки модели — нет. Expectations можно менять по утверждённым данным/поведению с объяснением, не под текущий ошибочный вывод.
- Контакты только текущей клиники на всех выходах, включая error/ADMIN/срочные и actions. Нет своих данных — нет чужого fallback.
- Для checkpoint 1e действует последнее решение владельца 29.08.2026: один Composer определяет существующий `ANSWER / ADMIN / CLARIFY` с недавней историей; никаких словесных medical/complaint/urgency gates, отдельного классификатора/verifier или `emergency`. `ADMIN` — одна детерминированная заглушка «Спасибо, что написали. С этим вопросом лучше обратиться к администратору клиники — он поможет дальше. Если ситуация срочная, пожалуйста, позвоните: {номер клиники}.», `patient_text=null`, без маркетинга; номер только текущей клиники. Положительный отзыв и обычная просьба связаться с врачом/сотрудником остаются `ANSWER`.
- Существующую историю из `session.py` передавать Composer в динамическом контексте для всех тем, не создавая новую память/Planner/RAG/второй вызов. История — контекст продолжения, не канон фактов. Offline проверяет реальный цикл записи/чтения, normal/streaming, роли, порядок, отсутствие дубля текущего вопроса и изоляцию сессий/клиентов.
- Для эксперимента checker проверяет сопоставимость четырёх вариантов, смысловую оценку и отделение retrieval/передачи данных/генерации/renderer. Ручной контекст и fake PASS не доказывают работающий RAG или production-готовность. Подробности — `.cursor/agents/checker.md`.

## Как читать (два слоя)

```
Слой 1 — этот файл          → «не нарушены ли инварианты проекта?»   (всегда)
Слой 2 — TASK.md, критерии  → «сделано ли именно то, что заказано?»  (для этой задачи)

Вердикт ✅ — только если ОБА слоя зелёные.
```

Ревьюер **не пишет код** — только проверяет и выносит вердикт. Нашёл проблему → возвращает Исполнителю с конкретикой.

---

## Чек-лист (Слой 1 — инварианты)

### A. Честность (жёсткий стоп при нарушении → сразу ❌)

- [ ] Тесты **не подогнаны костылями**: нет `assert True`, `skip`/`xfail`/`skip`-маркеров ради зелёного, ослабленных проверок, ожидаемого значения, подменённого под текущий вывод, хардкода ответа, мока, прячущего реальную логику.
- [ ] Красные тесты чинились **кодом/логикой**, а не правкой теста. Если тест изменён — есть внятное объяснение, что он **был неверен**.
- [ ] Ревью начато **с diff тестов/eval/golden**, до чтения отчёта Исполнителя. Protected acceptance из `TASK.md` после spec review не изменены: вопросы, target/current, expected, суммы, refs, required/forbidden и порядок UI.
- [ ] Нет resnapshot «текущий вывод = новый target», условного PASS или проверки вида «если поле отсутствует — пропустить assert».
- [ ] Ничего не выдумано сверх базы (`clients/{client_id}/`): факты, цены, услуги, формулировки. Ничего не «смягчено на всякий случай».

### B. Границы задачи

- [ ] Тронуты **только** файлы из списка `TASK.md`. Нет «заодно», нет рефакторинга мимо задачи.
- [ ] До начала был однозначный task baseline. Предсуществующий грязный diff не смешан с реализацией; если смешан и происхождение нельзя доказать — `❓ эскалация`.
- [ ] Смежные находки — в отчёте, **не** в диффе.
- [ ] Новый флаг поведения — по умолчанию **OFF** (`config.py`). Флип дефолта в задаче не сделан скрытно.

### C. Инварианты продукта

- [ ] **Route authority (ROUTE-AUTHORITY-1):** на free-text ходе `PreComposerPlan` не фиксирует semantic route заранее; Composer один раз выбирает пару из closed matrix. Deterministic bypass — только для структурированного UI-события без NL. Scope ≠ route.
- [ ] **Медзона checkpoint 1e:** общий FAQ/будущее опасение/сравнение → `ANSWER`; проблемное обращение определяется Composer и даёт одну детерминированную ADMIN-заглушку с каноническим номером текущей клиники, без свободного текста модели, рекламы и продающего CTA. Нет словесного hard-stop до Composer, новых режимов или отдельного semantic verifier.
- [ ] **Booking:** нигде не подтверждается/эхоится конкретная дата ИЛИ время; нейтральный ответ + сбор контакта.
- [ ] Продающие/успокаивающие формулировки **не выхолощены** осторожными правками.
- [ ] **Clarify** не задаёт медицинских/диагностических переспросов.

### C2. FINAL_FULLCONTEXT_ONLY (architecture law — жёсткий стоп при нарушении в target/final wiring → ❌)

См. `docs/ARCH_TARGET_DESIGN.md` § «Owner law: FINAL_FULLCONTEXT_ONLY».

- [ ] **Финальный Composer** получает **весь валидированный MD-корпус** через **cached FullContext**; scoped primary evidence **дополняет**, а **не заменяет** и **не скрывает** корпус.
- [ ] Нет нового **per-MD routing**, thematic document routers, **vector/chunk retrieval** или retriever-gate для обычных знаний без явного owner exception.
- [ ] Нет **временных product response paths**, legacy fallback ради сохранения текущих ответов, interim shadow bridges без постоянной роли, дублирования FullContext routing-таблицами.
- [ ] **Structured selectors** используются только для strict domains (услуги, цены/этапы, врачи, marketing/CTA, safety policy, provenance) — не как thematic knowledge routers.
- [ ] **`medical_handoff`** — safety mode, не отдельный MD-маршрут; **`used_doc_ids`/source refs** — audit/grounding, не pre-RAG router.
- [ ] При corpus overflow или предложении RAG/retriever вместо FullContext — **СТОП**, эскалация владельцу; eval harness/offline checker не превращены в product path.
- [ ] Любое исключение документировано: явное разрешение владельца, постоянная роль, доказательство недостаточности cached FullContext.

### C3. Problem route semantics — последнее решение владельца 29.08.2026

Для checkpoint 1e этот раздел заменяет несовместимую историческую схему `medical_handoff`/S42/S43:

- [ ] Существующий Composer, получив историю, сам выбирает `ANSWER / ADMIN / CLARIFY`; код не определяет медицинский смысл, жалобу или срочность по словам/regex и не перепроверяет его отдельной моделью.
- [ ] `ADMIN` сохраняет `patient_text=null` и один согласованный статический текст; номер детерминированно принадлежит текущей клинике. Нет собственного номера — нет чужого fallback.
- [ ] В ADMIN нет service_value, promo, amplifiers, offer, продающего CTA, видео или индивидуального model prose. Фраза не обещает фактическую передачу сообщения сотруднику.
- [ ] Положительный отзыв, запрос способа оставить отзыв и обычная просьба связаться с врачом/сотрудником не считаются проблемным ADMIN. Негативная жалоба/конфликт или требование реакции руководителя могут быть ADMIN по решению Composer.
- [ ] Общий стоматологический FAQ, будущий страх и сравнение вариантов получают grounded `ANSWER`; отсутствие факта само по себе не ADMIN. `CLARIFY` не содержит ADMIN-заглушку или навязанный телефон.
- [ ] История поступает в динамический prompt только как контекст продолжения; актуальный канон клиники и текущий вопрос имеют приоритет. Обычный и streaming-пути не дублируют реплики и не смешивают клиентов/сессии.
- [ ] Fake route проверяет только wiring. Он не считается доказательством, что настоящая модель верно поняла свободный русский текст.

### C4. Response contract — one-call target (`docs/RESPONSE_CONTRACT.md`)

Применяется к checkpoint'ам, реализующим или утверждающим новую архитектуру ответа:

- [ ] **One call:** обычный ход — ровно один Composer LLM call; без дополнительных LLM для классификации, цены, гарантии, sanitizer или marketing.
- [ ] **Shared lower path:** Full Context Strategy и Hybrid Strategy сходятся в `PreComposerPlan → Composer → ResolvedResponsePlan → TextRenderer → UIProjection`; отдельный Hybrid renderer запрещён.
- [ ] **`TextRenderer`** — единственный владелец финального visible text; после него нет commercial append.
- [ ] **Price lane:** один visible price block; `exact_price` — единственный owner amount/currency/unit; required offer conditions — закрытый enum (`per_jaw`, `per_tooth`, `package_includes`, `mandatory_exclusion`, `ct_separate`, `bone_grafting_separate`).
- [ ] **Fact roles:** приоритет `requested_fact > required_offer_condition > promo > automatic_amplifier`; один ID — одна visible role.
- [ ] **`implant_warranty` explicit_only:** automatic warranty запрещена; показ только через structured `requested_fact_ids`; misleading legacy `scenario_rules` не считается активным wiring.
- [ ] **Requested facts** не расходуют automatic amplifier cap.
- [ ] **BASE ANSWER MUST SURVIVE:** optional promo/amplifier/service value/CTA/UI failure не уничтожает полезный `patient_text`; optional failure до freeze плана; сломанный optional block и его ID не попадают в finalized visible IDs/session delta.
- [ ] **Finalized IDs:** `ResolvedResponsePlan` — единственный owner finalized visible commercial IDs; `UIProjection` только проецирует plan-owned IDs; анализ visible text запрещён.
- [ ] **Terminal plans:** matrix ADMIN / CONTACTS / CLARIFY / medical terminal (= ADMIN subtype) по contract §16.
- [ ] **Session IDs** только из `ResolvedResponsePlan`, не из анализа final text.
- [ ] **Blocking/streaming parity:** один plan/render path; различие только transport.
- [ ] **No semantic regex gates** для медицинского/коммерческого смысла до/после Composer.
- [ ] **No permanent old/new fallback** между TFC Product Runtime и one-call path после cutover.
- [ ] **COMPOSER-CONTRACT-1 (unwired):** published six-key Composer schema; five core fields without defaults; fail-open `source_identity`; policy sidecar is not full prompt; parser/adapter/resolver boundary not duplicated; production runtime not wired; `bound_package` is contract-owned structural type (not `Any`); public sidecar types are strict; shim tests are not reported as real builder integration.

### C5. ONE-CALL-ARCHITECTURE-1 (`docs/ONE_CALL_ARCHITECTURE.md`)

Применяется к checkpoint'ам, фиксирующим или реализующим целевой one-call flow:

- [ ] **No semantic planner before Composer:** free-text ход не использует legacy planner, regex/keyword classifier или pre-Composer semantic route/service/situation authority.
- [ ] **One free-text LLM call:** обычный free-text ход = ровно один provider/Composer call; deterministic typed UI bypass = ноль вызовов.
- [ ] **ComposerDecision semantic fields:** target output содержит `service_reference_kind`, nullable `topic_id`, `explicit_service_id`, `requested_aspect_ids` (`AspectKind`), `patient_situation`, `requested_fact_ids` — достаточно для post-Composer selection без анализа `patient_text`.
- [ ] **Session follow-up:** «А сколько стоит?» после обсуждения услуги использует `service_reference_kind=active_session`, а не fake `explicit_service_id` из session.
- [ ] **Topic nullable:** `topic_id` key required, value nullable; отсутствие topic не ломает clinic-wide flow и не означает CLARIFY само по себе.
- [ ] **AspectKind closed:** `requested_aspect_ids` exactly reuses `contracts.answer_plan.AspectKind`; `composition` не alias для `included`.
- [ ] **ServiceOptionsBlock:** code-ranked services материализуются в typed `ServiceOptionsBlock` (max 3); terminal routes запрещают service options.
- [ ] **No price/service duplicate:** `ServiceOptionsBlock` не дублирует варианты, уже показанные canonical price block.
- [ ] **No model-owned service recommendation:** Composer не формирует `recommended_service_ids` и не ранжирует услуги в `patient_text`; ranking — code-owned после merge/applicability/strategy.
- [ ] **Price code-owned:** нет `price_text` в target; price intent через `requested_aspect_ids`; canonical price block только в Resolver/Renderer.
- [ ] **Requestable facts independent:** inventory из `facts.json` не зависит от automatic marketing selection.
- [ ] **Post-Composer selection deterministic:** scope merge, applicability, strategy, materialization — код, не модель и не парсинг `patient_text`.
- [ ] **Session not from text:** session writer получает finalized typed delta; visible text не анализируется для восстановления IDs/ситуации.
- [ ] **FullContext corpus ≠ legacy runtime:** cached FullContext corpus — target knowledge input; legacy multi-call FullContext runtime — отдельный migration debt, не путать.

---

### D. Тесты и evals прогнаны честно

- [ ] Unit-тесты зелёные. Прогон с **канонным набором флагов** (`docs/FLAGS_AND_STATUS.md`), в чистом окружении (нет залипших `$env:` из прошлого прогона).
- [ ] Кейсы, зависящие от доп. флагов (F1/F2 → `CLARIFY_STATE_ON`; brand → `BRAND_FILTER_ON`), прогнаны с нужными флагами — красный не «ложный из-за флага».
- [ ] Live evals: сохранённый вывод (`eval_*.txt`) не переписан «под красоту»; регрессий против базлайна нет.
- [ ] Ревьюер сам запустил команды из `TASK.md` либо явно перечислил, что технически не смог воспроизвести. Все `skip/xfail/not run`, logging errors и таймауты отражены в вердикте; «зелёный» без этого не принимается.

### D2. UI и денежный паритет (когда затронут ответ/widget/маршрут)

- [ ] Сохранены обязательные follow-up refs/actions, кнопки и их видимый порядок, а не только текст ответа.
- [ ] PriceBook amounts, currency, unit (`one_tooth`/`jaw`), service_id и состав deterministic cards не изменились без отдельного продуктового решения.
- [ ] Contacts/booking/medzone payload не подменён общим composer-ответом.
- [ ] Падение необязательного marketing/promo overlay не блокирует и не меняет базовый content/price/contacts ответ.

### E. Границы контекста

- [ ] Тронут только `demo` (dental). `cesi`/`nikadent` не задеты без явной задачи.
- [ ] Нет `git branch`/`checkout`/`push` без команды владельца.
- [ ] Документация синхронизирована, если менялось поведение флага/крупный блок (`docs/FLAGS_AND_STATUS.md`).

---

## Формат вердикта Ревьюера

```
ВЕРДИКТ: ✅ / ❌

Слой 1 (инварианты): пройдено / нарушения: <список пунктов A–E, C2, C3, C4>
Слой 2 (критерии TASK.md): пройдено / не выполнено: <какие критерии>

Замечания Исполнителю (если ❌): <конкретика — файл:строка, что не так, что проверить>
Открытые вопросы владельцу (если есть): <то, что требует решения Архитектора/Дениса>
```

При **любом** нарушении блока A → сразу ❌, без разбора остального.
Если Ревьюер **сам не уверен** (архитектурная развилка, спорный инвариант, происхождение diff не доказано) → вердикт `❓ эскалация` и вопрос выносится Архитектору на контрольной точке. Не угадывать и не выдавать ✅ условно.
