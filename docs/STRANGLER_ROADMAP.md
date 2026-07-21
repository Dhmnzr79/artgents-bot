# Архитектурная миграция A1–A9 — roadmap для владельца продукта

Этот документ показывает, как мы строим новое внутреннее понимание вопроса пациента в локальном demo. Production-клиентов пока нет: legacy используется временно как измерительный и контрольный контур, а не как продукт, который нужно сохранять ради действующих пользователей. Цель — проверенная новая архитектура, после чего ненужные legacy-ветви можно удалять.

## Как читать чекбоксы

- [x] checkpoint действительно выполнен, проверен checker’ом и зафиксирован в git;
- [ ] checkpoint ещё не завершён;
- завершённый аудит может иметь `[x]`, даже если он честно показал плохой результат;
- `[x]` не означает, что новая функция уже влияет на ответы пациенту;
- отдельно смотрите строку **Authority**: она показывает, разрешено ли новому механизму управлять ответом.

Короткий словарь:

- **Shadow** — новый механизм работает параллельно для измерения, но не управляет ответом.
- **Authority** — право реально влиять на маршрут, факты, цену, текст или UI ответа.
- **Legacy path** — текущий продуктовый путь, который пока продолжает отвечать пациенту.
- **TurnFrame** — структурированная «карточка понимания» одного сообщения: тема, намерение, аспекты, ситуация пациента и другие поля.

## Текущий статус

| Вопрос | Ответ |
|---|---|
| Текущий этап | **A9 — Native Patient-scope Extraction** |
| Последний завершённый checkpoint | **A9 Frozen Matrix/Harness v2 Review** (governance `71aa405`, completion `8700721`) |
| Следующий технический checkpoint A9 | **A9 One-run Live Re-audit — только после отдельного разрешения владельца** |
| Отдельная S-series без live | **S9 — demo target doctor catalog завершён и независимо проверен; product path не подключён** |
| Ближайший рабочий фокус без live | **Следующий шаг S-series определить отдельным governance TASK; service-context builder, product wiring и authority не разрешены** |
| Что сейчас отвечает в локальном demo | Текущий legacy product path; новая patient-scope ось остаётся shadow-only |
| Patient-scope authority | **Forbidden** |
| Новый live/LLM run | Только после отдельного разрешения владельца |

## Быстрый список A1–A9

- [x] **A1 — минимальный TurnFrame**
- [x] **A2 — TurnFrame в shadow-наблюдении**
- [x] **A3 — первый аудит TurnFrame**
- [x] **A4 — темы из конфигурации клиента**
- [x] **A5 — native topic в shadow**
- [x] **A6 — измерение качества topic** — checkpoint завершён, sample показал техническую неполноту
- [x] **A7 — независимая валидация полей и повторный topic-аудит**
- [x] **A8 — service/follow-up/clarification в shadow**
- [ ] **A9 — composable patient scope** — инфраструктура построена, native positive quality ещё не готова

Отдельно начата S-series для materialization target schema без подключения к ответам:

- [x] **S1 — schema models/validators** — изолированный offline contract и
  детерминированные unit-тесты независимо проверены. Runtime, client data, session и
  authority не подключены.
- [x] **S2 — offline target-pack loader** — explicit-path loader и synthetic IO/error
  tests независимо проверены. `clients/**`, current loaders и product path не
  подключены.
- [x] **S3 — external source-ref integrity** — pure in-memory проверка `kb:`/`doctor:`
  refs и synthetic tests независимо проверены. Source index builders и product path не
  подключены.
- [x] **S4 — offline KB source-index builder** — exact `kb:` refs строятся только из
  explicit target Markdown root; synthetic tests независимо проверены. `clients/**`,
  legacy loaders и product path не подключены.
- [x] **S5 — minimal doctor data contract** — только имя/ID, должность, стаж,
  service links и exact MD profile ref; synthetic tests независимо проверены. Doctor
  loader/index и product path не подключены.
- [x] **S6 — doctor cross-reference integrity** — pure проверка service/profile refs и
  сборка exact `doctor:<id>` refs независимо проверены. Demo data и product path не
  подключены.
- [x] **S7 — demo doctor template hardening** — approved service links/profile copy и
  overview очищены; real demo S4→S5→S6 acceptance и completion review прошли.
  Runtime code и target wiring не менялись.
- [x] **S8 — strict doctor catalog loader** — explicit JSON→S5 boundary реализован и
  независимо проверен; demo target catalog не создан, runtime/product path не
  подключены.
- [x] **S9 — demo target doctor catalog materialization** — final-wire JSON для шести
  demo-врачей создан, offline проходит S4/S5/S6/S8 и независимо проверен; product path
  не подключён.

## Какой roadmap актуален

Этот файл — единственный актуальный roadmap **A-series**. Он описывает безопасную пошаговую замену внутреннего «мозга» понимания вопроса.

Старый накопительный [FULLCONTEXT_ROADMAP.md](archive/FULLCONTEXT_ROADMAP.md) перенесён в archive: он сохраняет историю composer/clarify/marketing работ, но больше не задаёт текущий порядок checkpoint-ов.

A1–A9 не были целиком придуманы заранее как неизменяемый master-plan. Макронаправление задано [ARCH_TARGET_DESIGN.md](ARCH_TARGET_DESIGN.md), а следующий маленький checkpoint выбирается по результатам предыдущего аудита. Но он не придумывается во время написания кода: сначала появляется `TASK.md`, затем независимый checker-review, и только после этого начинается работа.

После A9 пока **не утверждены** ни A10, ни отдельный B-series roadmap. Следующий этап определяется только отдельным architecture/governance решением, а не из этого файла.

---

## Подробно по этапам

### A1 — минимальный TurnFrame

**Статус:** завершён (`631abc1` → `0761213`).

**Authority:** отсутствует; contract foundation only.

**Что сделали:** создали первую единую карточку понимания сообщения и адаптер от старой структуры.

**Как это сказалось на логике и маркетинге:** прямого изменения ответов не было. Появился фундамент, на котором можно постепенно объединять разрозненные классификаторы и в будущем лучше удерживать тему, намерение и контекст.

**Что увидел пациент:** ничего нового — бот продолжил отвечать старым путём.

### A2 — TurnFrame в shadow-наблюдении

**Статус:** завершён (`5e8b63c` → `3746d77`).

**Authority:** shadow-only.

**Что сделали:** TurnFrame начал строиться параллельно на реальных planner-turn и попадать в техническое наблюдение.

**Как это сказалось на логике и маркетинге:** мы получили возможность измерять новое понимание вопроса без риска для продаж, цен и текста ответа.

**Что увидел пациент:** ответ не изменился; shadow-frame не участвовал в решениях.

### A3 — первый аудит TurnFrame

**Статус:** завершён (`0486e87`, audit `0cb8ca3`).

**Authority:** forbidden.

**Что сделали:** проверили, насколько новая карточка действительно заполняется на живом pipeline. Planner-success coverage был `5/5`, но topic отсутствовал в `4/5` scoreable frames.

**Как это сказалось на логике и маркетинге:** вместо преждевременного включения мы обнаружили, что бот ещё не умеет надёжно записывать тему в новый contract. Это защитило ответы от ошибочного переключения.

**Что увидел пациент:** никаких изменений. Результат этапа — честная диагностика, а не новый ответ.

Подробнее: [TURN_FRAME_SHADOW_AUDIT_A3.md](evidence/a_series/TURN_FRAME_SHADOW_AUDIT_A3.md).

### A4 — темы из конфигурации клиента

**Статус:** завершён (`de66ebc` → `2757cae`).

**Authority:** contract/shadow preparation only.

**Что сделали:** разрешённые темы стали браться из настроек клиентского пакета, а не из жёстко зашитого общего списка.

**Как это сказалось на логике и маркетинге:** архитектура стала лучше готова к разным клиентам и направлениям: набор тем можно определять контентом клиента. Это уменьшает риск, что логика одного бизнеса случайно попадёт в другой.

**Что увидел пациент:** пока ничего нового — product routing не переключался на native topic.

### A5 — native topic в shadow

**Статус:** завершён (`cfc438b` → `8662300`).

**Authority:** shadow-only.

**Что сделали:** существующий planner начал возвращать и валидировать native topic в том же вызове. Product downstream продолжил использовать legacy `DecisionFrame.service_topic`.

**Как это сказалось на логике и маркетинге:** появилась более чистая тематическая ось для будущего выбора релевантного контента и защиты от тематических протечек. Сначала её только измеряли.

**Что увидел пациент:** прежние ответы и маршруты; native topic ещё ничего не выбирал.

### A6 — измерение качества topic

**Статус:** checkpoint завершён (`3f205f4` … audit `4a6c867`), но результат не был quality-green.

**Authority:** forbidden.

**Что сделали:** заранее заморозили 33 ожидания, создали harness и выполнили один контролируемый live run. Получили `26/33` scoreable cases; семь topic-наблюдений потерялись, потому что unrelated поле `aspects=[]` делало весь strict plan недоступным.

**Как это сказалось на логике и маркетинге:** обнаружили техническую причину потери полезного понимания. Качество topic в семи unavailable cases не было измерено, поэтому мы не объявляли, что модель поняла или не поняла их.

**Что увидел пациент:** product не переключался. Аудит измерял внутреннюю ось, а не качество текста ответа.

Подробнее: [TOPIC_SHADOW_AUDIT_A6.md](evidence/a_series/TOPIC_SHADOW_AUDIT_A6.md).

### A7 — field-level planner outcome и topic re-audit

**Статус:** завершён; final audit `596e809`.

**Authority:** shadow topic измерен, но product authority не передана.

**Что сделали:** один planner JSON разделили на две независимые ветви:

- partial shadow-frame сохраняет валидные поля, даже если соседнее поле ошибочно;
- strict legacy plan по-прежнему определяет текущий product path и его fail-open.

Повторный frozen audit получил topic scoreability `33/33` на этой выборке.

**Как это сказалось на логике и маркетинге:** ошибка одного технического поля больше не прячет остальные понятные сигналы. Это делает измерения честнее и подготавливает более устойчивую будущую логику ответов.

**Что увидел пациент:** прежний безопасный fallback и прежняя продуктовая логика. `33/33` — результат shadow measurement, а не доказательство точности всех ответов бота.

Подробнее: [FIELD_LEVEL_PLANNER_OUTCOME_A7.md](evidence/a_series/FIELD_LEVEL_PLANNER_OUTCOME_A7.md) и [TOPIC_SHADOW_REAUDIT_A7.md](evidence/a_series/TOPIC_SHADOW_REAUDIT_A7.md).

### A8 — service/follow-up/clarification в shadow

**Статус:** завершён (`3a3b445` → `38d29f3`).

**Authority:** shadow-only.

**Что сделали:** добавили независимую проверку service id, признака продолжения диалога и необходимости уточнения.

**Как это сказалось на логике и маркетинге:** стало проще видеть, какая именно часть понимания сломалась: тема, услуга, продолжение контекста или clarify. Это снижает риск чинить не тот слой.

**Что увидел пациент:** prompt, routing, цена, текст и UI не менялись.

### A9 — composable patient scope

**Статус:** этап открыт.

**Authority:** **forbidden**.

**Product firewall:** сохранён.

**Зачем нужен этап:** бот должен независимо понимать немедицинские признаки ситуации пациента:

- один зуб, несколько зубов или вся дуга/челюсть;
- верхняя, нижняя или обе челюсти;
- удаление обсуждается или имплант уже установлен;
- пациент явно сообщил, что врач говорил о нехватке кости.

Это не диагноз и не автоматический выбор All-on-4, All-on-6, синус-лифтинга или другой услуги.

#### Чекбоксы A9

- [x] Original patient-scope design (`9ee8c34`)
- [x] Nested contract (`2a34b6c`)
- [x] Scalar compatibility bridge (`0cc9042`)
- [x] Shadow wiring и product-firewall proof (`33966e4`)
- [x] Frozen quality matrix (`15d2ae7`)
- [x] Quality harness (`3f11857`)
- [x] One-run audit (`10b4739`)
- [x] Native extraction design (`16ced47`)
- [x] Native container metadata contract (governance `375ac13`, contract/tests reviewed)
- [x] Native raw contract и prompt spec (governance `405a6ac`, frozen fixture/tests reviewed)
- [x] Native extraction implementation (governance `e46a428`, implementation/tests reviewed)
- [x] Native shadow wiring/firewall proof (governance `4162111`, runtime/tests reviewed)
- [x] Manual-contact `not_applicable` taxonomy (governance `083bdcd`, revision `0eb8566`, helper/tests reviewed)
- [x] Frozen matrix/harness v2 review (governance `71aa405`, matrix/harness/tests independently reviewed)
- [ ] One-run live re-audit — только после отдельного разрешения владельца
- [ ] Authority decision
- [ ] Legacy retirement — только после принятой authority architecture

#### Что доказано сейчас

- инфраструктура и первый raw признаны целыми;
- deterministic scalar bridge прошёл `10/10`;
- в первом immutable v1 raw live-positive exact = `0` для `extent`, `jaw`, `stage`, `modifiers`;
- исторический v1 aggregate composite exact = `0/9` (7 live + 2 deterministic rows); нового live-результата ещё нет;
- current product path не читает новый nested scope;
- реальные тексты ответов, цены и UI этим harness не оценивались;
- authority запрещена;
- frozen v2 matrix сохранила все 30 live-вопросов и исходные ожидания без подгонки под первый raw;
- v2 harness отделяет 30 live-наблюдений от 14 локальных deterministic fixtures: positive denominators `13/9/4/3`, live composite total `7`;
- manual-contact остаётся в полном total как `not_applicable`, но не притворяется ошибкой распознавания; transport, runtime и malformed-frame ошибки остаются видимыми отдельно;
- offline fake-run и privacy/contract проверки зелёные (`68 passed`), но новый live/LLM run не выполнялся;

**Как это сказалось на логике и маркетинге:** мы построили безопасную измерительную инфраструктуру и увидели, что на первом frozen live sample measured shadow не материализовал ни одного exact positive axis. Следовательно, включать его в реальные ответы рано.

**Что увидел пациент:** ничего нового от A9 scope. Ответ по-прежнему формирует действующий legacy path.

После будущего подтверждения качества эта ось сможет помогать делать ответ релевантнее масштабу ситуации, но только через отдельное product/authority решение. Она не должна сама ставить диагноз или назначать лечение.

Подробнее: [PATIENT_SCOPE_DESIGN_A9.md](PATIENT_SCOPE_DESIGN_A9.md), [PATIENT_SCOPE_SHADOW_AUDIT_A9.md](evidence/a9/PATIENT_SCOPE_SHADOW_AUDIT_A9.md), [PATIENT_SCOPE_NATIVE_EXTRACTION_DESIGN_A9.md](PATIENT_SCOPE_NATIVE_EXTRACTION_DESIGN_A9.md) и [PATIENT_SCOPE_NATIVE_RAW_CONTRACT_A9.md](PATIENT_SCOPE_NATIVE_RAW_CONTRACT_A9.md).

## Следующий технический checkpoint A9 — требуется отдельное разрешение

### A9 One-run Live Re-audit

Frozen matrix/harness v2 подготовлены и независимо проверены **до** live. Первый A9 raw, v1 matrix/harness/summary и исторический audit не переписаны. Product path и ответы бота не менялись; patient-scope authority остаётся запрещённой.

Следующий A9 шаг — один контролируемый live/LLM re-audit по 30 frozen turns, один attempt без retry, с новым raw `eval_patient_scope_a9_v2_last.txt`. Он не запускается автоматически и требует:

1. отдельного явного разрешения владельца на live/LLM;
2. нового `TASK.md`;
3. governance checker-review до запуска;
4. сохранения raw без повторного прогона или «улучшения» результата.

**Как это скажется на боте:** пока никак — мы лишь сделали будущую проверку честной. Когда владелец разрешит один live-run, отчёт отдельно покажет, распознаёт ли новая архитектура реальные положительные признаки пациента, а не смешает их с локальными fixtures или передачей обращения администратору.

До такого разрешения A9 стоит на паузе. Карта вопросов,
[target-архитектура услуг и цен](PRICE_SERVICE_ARCHITECTURE.md) и
[target-архитектура маркетинговых сценариев](MARKETING_SCENARIO_ARCHITECTURE.md) уже
документированы.

### Product/schema checkpoints вне A-series

- [x] Маркетинговая карта вопросов и базовые правила ответа.
- [x] Product/UI composition: лимит 3/2, content/price slots и стабильная CTA.
- [x] **Response Data Schema Governance** — единый target-канон услуг, применимости,
  брендов, prices, client strategy, marketing refs и session/UI state материализован и
  независимо проверен checker-ом; runtime/client data не менялись.

Три product/UI решения перед schema/runtime закрыты: composition первого marketing-concern
ответа, content/price navigation slots и стабильная CTA по смысловому контексту. Для
schema design создан отдельный governance TASK `dbf2c46`; runtime и client data заранее
не меняются.

## Как поддерживать чекбоксы

1. Новый checkbox сначала добавляется в governance `TASK.md`.
2. `[x]` ставится только в completion commit соответствующего checkpoint после checker `✅`.
3. Если аудит завершён, но показал красное качество, checkbox закрывается, а красный результат остаётся написан рядом.
4. Завершённый design не закрывает implementation или parent stage.
5. Live checkbox не закрывается без immutable raw, audit и отдельного разрешения владельца.
6. Authority меняется только отдельным продуктовым решением.
7. Подробный текущий статус A-series обновляется здесь; [ARCH_TARGET_DESIGN.md](ARCH_TARGET_DESIGN.md) только ссылается на этот канон, чтобы снова не устареть.
