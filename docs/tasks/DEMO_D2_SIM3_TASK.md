# SIM-3 — завершённый результат и единый контекст разговора

Дата: 2026-10-02. Статус: реализация разрешена владельцем «Переходим к этапу 3»;
уточнение длительности обсуждаемого объёма принято «Принимаю».
Тип: архитектурное упрощение памяти. Согласованный объём SIM-3 закрыт
владельцем «Делаем» после independent Checker и Cursor PASS, 2026-10-02.
Закрытие относится к проверенному offline механизму, не к качеству живой модели
или полному CI. Владелец «Давай комит и пуш» отдельно разрешил публикацию
checkpoint в codex/d2-stage1-contract. Live/merge/deploy не разрешены;
запреты Git ниже — история до этого согласования.

## Baseline и allowlist

Root: C:\Cursor Projects\artgents-bot-active; branch codex/d2-stage1-contract.
HEAD / origin branch: 5cb58d5629bb78b07736246e12d951844bbe6c55.
origin/main / merge-base: 141ce91fb1731cd990fcf8391550150016c73e7f.
Staging пуст. Foreign data/, docs/MARKETING_ANSWER_SCENARIOS.md и отдельный
docs/tasks/DEMO_D2_SIM0_TASK.md не входят в checkpoint.

Точные разрешённые файлы:

- contracts/d2_dialogue.py
- contracts/d2_session_context.py
- contracts/response_plan_session.py
- contracts/response_plan.py (добавлен после выявления пробела provenance: brand ID
  завершённой exact-service price части и policy IDs точного блока правил,
  без изменения подбора/публикации)
- core/d2_dialogue.py
- core/d2_dialogue_store.py
- core/d2_session_context.py
- core/d2_completion_context.py (новый)
- core/one_call_prompt_contract.py
- tests/test_d2_sim3_completion_context.py (новый)
- tests/test_d2_af1a_price_task_http.py
- tests/test_d2_sim1_known_actions_http.py
- tests/test_d2_sim2_dialogues.py
- tests/test_d2_continuation_scenarios.py
- tests/test_d2_document_click_task_http.py
- tests/test_d2_price_presentation_http.py
- tests/test_d2_lead_interrupt_http.py
- docs/tasks/DEMO_D2_SIM3_TASK.md
- docs/tasks/DEMO_D2_CURRENT_STATUS.md
- docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md
- docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md
- docs/tasks/DEMO_D2_TARGET_CONTRACT.md
- docs/tasks/DEMO_D2_ACCEPTANCE.md
- docs/tasks/DEMO_D2_PRODUCT_DECISIONS.md

## До → после → удаляется

До: _d2_live_prose_for_history / _next_d2_dialogue_pairs пропускают code-only
результаты. Объём отдельно копируется из последнего completion.recent_price_scope
и исчезает после следующего ответа.

После: существующие dialogue_pairs индексируют завершённые результаты через
request_id, безопасный вопрос либо проверенный UI ref и номер хода. Существующая
TTL projection читает response.resolved соответствующих completion и передаёт
ограниченное представление трёх последних ходов. Повтор результата не создаёт
новую запись. completion.context никогда не включается в историю рекурсивно.

Удаляются prose-only eligibility, дублирование assistant_text в D2 state,
D2RecentPriceScope, оба поля recent_price_scope, их validator, аргумент writer,
selected-volume-only создание scope и read-latest инъекция в provider context.
Исторические не-D2 consumers SessionDialoguePair не переводятся на новый runtime.
Активный D2 не читает их как запасную память; локальная схема меняется без миграции.

Один владелец по [Contract §3](DEMO_D2_TARGET_CONTRACT.md): существующий D2 store
атомарно сохраняет результат и ссылки памяти; projection только читает разрешённые
поля. Смысл текущего свободного вопроса определяет модель. Цена и UI остаются у кода.

## Продолжительный контекст — согласование владельца

Текстовые детали ограничены тремя ходами и существующим text cap. Услуга и объём
переживают больше трёх контактных отвлечений до явной смены темы/услуги либо TTL.
В существующем active_topic хранится discussion_request_id — ссылка на источник,
не новый owner/история. scope для provider выводится из d2_price_scope_decision
этого completion либо единственной завершённой price part для точной услуги:
topic из tenant service metadata, brand из принятой операции, extent из уже
связанной treatment situation. Смысл текста повторно не определяется.
Новый scope (в том числе overview/unknown) заменяет старый;
старый объём не переносится на другую услугу. Клик не создаёт медицинский факт.
TTL 30 минут, history caps, ситуация пациента и lead/privacy не изменяются.
Основание: D2-109 и явное уточнение владельца в этом checkpoint; Astra consulted.

## Сохранённые поля → projection → input

- d2_request_parts: порядок, вид, status, scope, service/topic/content refs.
- information_blocks/patient_text: ограниченная безопасная поясняющая prose.
- d2_price_scope_decision: topic/service/brand/applied_extent как обсуждение.
- price/detail rows: ordered offer/service IDs и detail aspect, без сумм и payment text.
- contact blocks: публичный ответ клиники, включая порядок филиалов.
- policy/commercial facts: утверждённые IDs, без финансовой display prose.
- clarification/failure/deferred: существующие ссылки/status/reason, без очереди.
- exact text: нельзя безусловно копировать display_text; учитывать конкретные
  структурированные источники. Не извлекать смысл из текста regex/моделью.

Request refs проверяются по tenant/session/revision/turn. ПД пациента не читаются
из lead или из исходного HTTP payload. Полный прошлый rendered_text не копируется.
Историческая сумма не становится источником новой цены. shown offer refs остаются:
у них отдельная задача подлинности и порядка detail-кликов.

## Приёмка и пределы

S03/D2-109: price → volume → duration → address → parking → hours → duration;
свежий прямой extent; contact-only/fact-only/detail/clarify → continuation;
две услуги/новая тема/новая услуга, unknown scope, TTL, два филиала.
Оба endpoint, provider input, replay, stale/forged/foreign и lead/privacy.
Актуальные assertions заменяют зависимость от удалённых storage полей, не ослабляют
семантические требования. Offline fake model не подтверждает живое понимание.

Фокус: новый SIM3 test, AF1a, SIM1 known actions, SIM2 dialogues, continuation,
document click, price presentation, lead interrupt; затем независимый Checker.
Общий незелёный CI — прежний документированный долг до merge, не закрывается этим
этапом. SIM-0/4/5 и REC-5 вне scope. Live/provider/SMTP: 0; прежний бюджет исчерпан.
Новые вызовы, commit/push, merge/deploy и cleanup этим checkpoint не разрешены.

## Выполненные проверки — 2026-10-02

SIM3/SIM1/SIM2/session context: 176 PASS / 174.20 s, offline.
Independent Checker: новый SIM3 набор 11 PASS / 28.04 s, trace удаления
подтверждён. Первый REJECT относился к отсутствующему доказательству двух
филиалов на следующем ходе и Draft Ledger. Оба дополнения внесены;
independent focused recheck PASS, 2 PASS / 3.79 s.
Итоговый SIM3/continuation/document/AF1a: 56 PASS / 129.30 s.
Локальные Markdown-ссылки: 87 проверено, отсутствующих нет; diff --check чистый.
Реализация, independent Checker и Cursor gate завершены.
Cursor PASS предоставлен владельцем: собственные прогоны reviewer — SIM3 13 PASS,
continuation/session context 66 PASS, AF1a/document/SIM1/SIM2 142 PASS;
итого 221 PASS, 0 FAIL. Это отдельные запуски Cursor, не новые запуски исполнителя.
Cursor подтвердил фактическое удаление зависимостей, оба endpoint и отсутствие
новой смысловой классификации. Согласованный offline объём этапа закрыт владельцем.

Price presentation/lead interrupt не редактировались: на clean 5cb58d5
27 FAIL / 1 PASS, те же 27 failure IDs в текущем checkout. Старые envelope
fixtures — подтверждённый baseline debt; их перевод не является этой задачей.
