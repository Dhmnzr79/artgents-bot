# D2 demo — текущее состояние

## НикаДент — техническое подключение, 2026-10-15

Текущий этап: Interface §65 / codex/nikadent-technical-onboarding, baseline e93cb12.
Owner разрешил подготовку, выкладку и тестирование; контент/новые цены отложены.
Актуальная demo handoff-документация отдельно в fc84066, PR #30 пока открыт.
Этот раздел заменяет старые сведения о текущей ветке/релизе ниже: demo ранее
развёрнут на e93cb12, PR #27–29 merged, Inter 400–600. Старый срез ниже исторический.

Локально: Nikadent snapshot загружается после заполнения существующего обязательного
microfact_text; назначен временный получатель gothica@mail.ru. Убран универсальный
demo dispatcher: действующий lead/effect путь использует прежний tenant delivery
service. Accepted PII живёт только в private session/request closure; terminal text
и effect receipt сохраняются вместе, без автоматического resend. Demo остаётся stub.
Панель получает конфигурацию выбранной клиники с API; SID и teaser keys разделены
по клиентам. Nikadent41.ru и локальная панель разрешены exact-origin настройками;
аватар временный SVG, MD и суммы не редактировались.

Проверки на момент записи: 32 targeted offline PASS (actual JSON/SSE + mocked
SMTP, replay, tenant/contact/doctor grounding, phone modes, existing SMTP unit
tests), panel Node harness PASS. Первые ошибки новых tests относились к использованию
historical JSON helper и неверной метке boundary; tests исправлены под current
text protocol. Ни одного live/provider/SMTP вызова. Full CI и Checker впереди;
Независимый Checker PASS, собственные 13 onboarding tests PASS. Full release
selection выполняется отдельно. Публичные health/config demo и nikadent вернули
200 при корректном Origin: hostname/registry уже подключены. SMTP на VPS,
получение письма и установка на сайт клиента ещё не подтверждены.

Срез 2026-10-13. Здесь только актуальные факты и незакрытые задачи.
Датированные записи прежних веток, экспериментов и checkpoint сохранены целиком
в [архиве состояния](../archive/pre-d2/tasks/DEMO_D2_CURRENT_STATUS.md).
Они описывают момент записи, а не разрешают возвращать удалённые механизмы.

## Развёрнутая версия и локальные изменения

- Demo работает на VPS по подтверждению владельца. Последний подтверждённый
  GitHub release — `8888fdd`, PR #26; CI, Publish image и Deploy production успешны.
  Новый SSH-аудит контейнера не выполнялся. Реальные production-пользовательские
  диалоги и требования миграции не заявлены.
- Локальная чистка — ветка `codex/docs-tests-cleanup`, baseline `origin/main=8888fdd`.
  Изменения идут в draft [PR #27](https://github.com/Dhmnzr79/artgents-bot/pull/27).
  Push этой ветки сам по себе VPS не обновляет; merge/deploy ещё не выполнялись.
- Roboto400/500/600, интервалы0 и замены14.5→15 сохранены исходным checkpoint
  `9f8c8f7`, тегом `checkpoint/pre-cleanup-2026-10-13` и перенесены в `58c1afa`.
  На VPS эта версия оформления ещё не выкладывалась.
- Прежние14 MD отличались только EOL: исходные байты сохранены локально в ignored
  `logs/pre-cleanup-md-eol-20261013/`; содержимое не менялось. Prototypes удалены
  по решению владельца. `.env`, raw logs, локальные БД не публикуются.

## Нынешний ответ бота

- Рабочая модель — DeepSeek Flash: `DEFAULT_LLM_MODEL=deepseek-flash`,
  `CHAT_BASE_URL=https://api.deepseek.com`, `CHAT_API_KEY`.
  Чистая конфигурация без env имеет Qwen default; это не fallback при ошибке DeepSeek.
- Обычный ответ — свободная prose с optional `<D2_META>` для действий/источников.
  Уточнение и вопрос о составе не требуют отдельной команды. Обязательный
  JSON-envelope, model ordinary price_detail/clarify_content и doctor_catalog удалены.
- Цена — native `show_price`: модель выбирает запрос/аргументы, код собирает
  фактическую карточку, затем второй provider response пишет окончательный текст.
  Оба вызова используют настроенную модель и расходуют quota. Strict и отдельный
  классификатор не выбраны. Карточка без tool не гарантируется; полезная prose
  сохраняется, риск модельных финансовых неточностей принят владельцем.
- Full context содержит approved MD, completed history и показанную карточку.
  Canonical публичные контакты — `clinic_policies.yaml -> contact`; мост в обычный
  model context включён в release (`0a9b1ce`). Readiness для DeepSeek — `33c1f55`.
- Verified UI clicks, tenant isolation, lead/privacy, transactional commit/error
  и replay сохраняются. Situation intake выключен. Demo-заявка учебная.
- Demo quota:30 model calls/session,400/day. Это число provider calls,
  не пользовательских сообщений; price второй вызов тоже считается.

Подробности и sole responsibility table:
[текущая архитектура](../CURRENT_ARCHITECTURE.md),
[Target Contract §3](DEMO_D2_TARGET_CONTRACT.md).
Позднейшие явные решения владельца заменяют противоречащие старые записи.

## Что подтверждено в чистке

| Checkpoint | Результат |
|---|---|
| §60 | Contact model context regression включён в PR/publish gate; списки защищены G2/G3 |
| §60.1 | Current docs entry и architecture/test index; situation suite18PASS, возвращён в gate |
| §60.2 | Quota fixtures мигрированы на native price и30calls;12PASS, возвращены в gate |
| §60.3 | Policy/text_ref38cases и contacts20cases; проверки tenant/data/missing/replay сохранены, оба suite в gate |
| §60.4 | Удалены15 obsolete cases; text protocol27cases усилен и в gate; три старых документа архивированы |
| §60.5 | Старую хронику статуса вынесли в архив; этот путь оставлен актуальным кратким статусом |
| §60.6 | PR и Publish используют shared release selections; прежние проверки сохранены, добавлен selection contract |
| §60.7 | Новый owner behavior entry;19 старых планов/аудитов перенесены в архив с явной исторической пометкой |
| §60.8 | 50 старых task cards/prompts и полные Interface/Roadmap snapshots архивированы; current очередь и process pointers очищены |
| §60.9 | Старые reference-bound документы явно помечены историческими; июльский backlog архивирован, current debt pointer обновлён |
| §60.10 | Ещё3 отменённых ONE_CALL wiring assertions удалены; current native model consistency guards усилены |

Последний локальный прогон точного publish offline selection (50 файлов, §60.6):
**821 passed,5 skipped,0 failed**. Все5 skips — ограничения symlink на Windows/POSIX.
Все49 прежних файлов сохранены; добавлен только selection contract. Targeted
selection/G2–G8:271PASS5SKIP, independent selection/G2/G3:65PASS и Checker PASS.
Targeted text/native-price/G2/G3:120PASS; independent Checker §60.4 — PASS.
Два trailing-whitespace места архива исправлены в `2cbbd15`, focused Checker PASS.
Это offline evidence, не повторная проверка Docker/PG/deploy и не полный historical suite.
GitHubCI checkpoint `f8c1700`: все5jobs SUCCESS, включая PostgreSQL и secret scan.
Publish image/deploy этого PR не запускались. Новых live/provider/SMTP calls в чистке:0. Runtime и client KB не менялись.

## Что осталось

1. Закончить карту historical tests: полезные guards мигрировать, доказанные дубли
   и assertions удалённых механизмов убрать. Не удалять тест только потому, что он красный.
2. Архивировать остальные устаревшие планы/аудиты, выделив действующие invariants.
   Прежние Interface/Roadmap sections архивированы; оставшиеся rootdocs/evidence
   и historical-reader bindings ещё классифицируются, весь корпус не очищен.
3. Завершить сверку SIM/REC evidence: «выполнено / заменено / отменено / отложено».
   Общая whole-bot acceptance не закрыта; offline fixtures не доказывают live model quality.
4. Temporary demo gate пока ограничен. Постоянный набор утвердить по законченной
   карте полезных проверок; Secret scan, PostgreSQL и Docker/deploy защиты не ослаблять.
5. Client KB cleanup и экономия full-context tokens — следующий отдельный этап.
   Optional doctor/case UI — будущая идея. Итоговая совместная выкладка требует
   отдельного разрешения; текущий VPS demo не менять в чистке.

Порядок работ — [верх Roadmap](DEMO_D2_DELIVERY_ROADMAP.md),
карточка/доказательства — [Interface §60](DEMO_D2_INTERFACE_TASK.md#60-cleanup-checkpoint--2026-10-13),
проверки — [Test index](../TEST_SUITE_ARCHITECTURE.md).
Процесс — [AGENTS](../../AGENTS.md), [Execution Lock](DEMO_D2_EXECUTION_LOCK.md),
[Git/запуск](../WORKFLOW_GIT.md), [Checker](../WORKFLOW_CHECKER.md).


Prompt§61 (ownerGO): clinic facts grounded, general dental knowledge permitted;
mild redundancy reduction without paragraph/word caps. Version47 guidance shared
ordinary/known/nativecompletion. Offline delivery checks don't prove livecompliance;
no live agentcalls/China MD changes. Runtime mechanics unchanged.

Prompt§62/version48: generalquestion→#korotko ifpresent with necessary relevant
microfacts; specificquestion→matchingsections, clickedfollowup→selectedsection.
No full-documentdump or conditions withheld for followup. UI/code unchanged,
no new calls; offline delivery evidence does not prove live compliance.
