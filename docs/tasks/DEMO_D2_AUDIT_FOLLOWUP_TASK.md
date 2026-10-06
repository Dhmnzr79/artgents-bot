# D2-AUDIT-PLAN — документальная сверка после REC-4-P2

## D2-SIM-DOC — действующий документальный checkpoint, 2026-10-01

Owner GO: проверить документы/коммиты/ветки/push, обновить план реализации и
закрепить правила; три продуктовых решения согласованы в чате. Это продолжение
существующей задачи, не новая ветка и не разрешение runtime/live/merge/deploy.
Папка `C:\Cursor Projects\artgents-bot-active`, branch `codex/d2-stage1-contract`.
Baseline HEAD/origin branch после fetch: `0691217b888b92b49ba2c288452ed8a053f31206`;
main/merge-base `141ce91fb1731cd990fcf8391550150016c73e7f`. Tracking 0/0;
main 101/0. Staging пуст. Девять прежних правок правил сохранены; foreign
`data/`, `docs/MARKETING_ANSWER_SCENARIOS.md` исключены.

Точный write allowlist (15 файлов):

```text
AGENTS.md
docs/WORKFLOW_CHECKER.md
.cursor/agents/checker.md
.cursor/rules/00-guardrails.mdc
docs/tasks/DEMO_D2_AUDIT_FOLLOWUP_TASK.md
docs/tasks/DEMO_D2_CURRENT_STATUS.md
docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md
docs/tasks/DEMO_D2_TARGET_CONTRACT.md
docs/tasks/DEMO_D2_PRODUCT_DECISIONS.md
docs/tasks/DEMO_D2_ACCEPTANCE.md
docs/tasks/DEMO_D2_EXECUTION_LOCK.md
docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md
docs/tasks/DEMO_D2_CODEX_EXECUTOR_PROMPT.md
docs/tasks/DEMO_D2_CURSOR_CHECKER_PROMPT.md
docs/tasks/DEMO_D2_STAGE_TASK_MINI_PROMPT.md
```

ACCEPTANCE: единый текущий статус; D2-107–109 и C03 без старого финансового
допуска; Roadmap содержит правила, порядок, owner/removal/dialogue evidence;
исторические карточки не дают нового GO; незаданные продуктовые детали
явно ограничивают зависимый этап вместо придуманных правил. Мини-промпт,
Codex/Checker/Cursor согласованы с действующим планом. Astra даёт совет,
не продуктовый GO. Runtime-упрощение не заявляется.

Дополнение по прямому запросу владельца «Сделай это»: закрепить пять уточнений
SIM-1–4 и проверки каждого этапа. В этой итерации меняются только Roadmap,
Target Contract, Acceptance, Codex Executor Prompt, Stage Task Mini Prompt,
WORKFLOW_CHECKER, эта карточка и Ledger (внутри прежнего allowlist).
Прежний PASS документального diff не покрывает это дополнение автоматически;
нужен сфокусированный независимый review уточнений и их согласованности.
Не вводятся новые продуктовые правила или runtime GO; C03 уже пересогласован.

Проверки: Git refs/ancestry/status, diff --check, локальные Markdown-ссылки
из изменённых документов, независимый read-only Checker; затем Cursor.
Pytest, бот, provider, SMTP не запускать. Не stage/commit/push до review и
явного разрешения. D2 ROUTE / LEGACY IMPACT: документация, код неизменён.
FUTURE SCOPE: SIM-0–5/REC-5, технические карточки на принятом SHA.

## Историческая карточка — 2026-09-29

Нижеследующие baseline, allowlist и запреты записи относятся к прежнему
checkpoint. Они не ограничивают явно разрешённую текущую синхронизацию.

Дата: 2026-09-29. **Разрешена подготовка плана и синхронизация документации;
реализация исправлений не разрешена этой карточкой.** Основание — прямой запрос
владельца проверить документацию, остатки старых решений, commit/push и обновить
действующий roadmap. Цитата из переписки или предложение ассистента не являются
owner decision. Это продолжение существующей D2-задачи в active-репозитории,
не новая ветка от main и не разрешение переносить старую архитектуру.

## 1. Baseline и точный allowlist

- Папка и Git root: `C:\Cursor Projects\artgents-bot-active`.
- Ветка: `codex/d2-stage1-contract`.
- HEAD, локальный origin branch и GitHub branch через read-only `ls-remote`:
  `f4a08ea75b284cb51291fd7fe6ca64d842d8e2d0`.
- `origin/main`, GitHub main и merge-base:
  `141ce91fb1731cd990fcf8391550150016c73e7f`.
- До правок tracked diff и staging пусты. Чужие untracked: `data/` и
  `docs/MARKETING_ANSWER_SCENARIOS.md`. Они не редактируются и не stage.
- Git предупреждает о недоступных user ignore и `.pytest_cache/`; это ограничение
  просмотра ignored-окружения, не обнаруженный tracked diff. Настройки не менялись.
- Write allowlist (только эти шесть файлов):

```text
docs/tasks/DEMO_D2_AUDIT_FOLLOWUP_TASK.md
docs/tasks/DEMO_D2_CURRENT_STATUS.md
docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md
docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md
docs/tasks/DEMO_D2_TARGET_CONTRACT.md
docs/tasks/DEMO_D2_PRODUCT_DECISIONS.md
```

Runtime, tests, tenant data, AGENTS/Execution Lock, исторические карточки,
Acceptance и Reconciliation Inventory — read-only. Старая папка `artgents-bot`,
worktree 27e1 и backup не открываются для работы/переноса/очистки. БД, `.env`,
сырые разговоры не включаются в документы. Бот/pytest/provider/SMTP не запускаются.
Remote-проверка читает refs, не делает fetch/prune, push или deploy.

## 2. Что подтверждено и что документы должны говорить

Цепочка принятых checkpoint в ancestry HEAD: `6c4a963` (opt-in журнал),
`279b21c` (REC-2 correction), `28ff60a` (REC-3), `cebd09b` (envelope/подпись цены),
`b02db8e` (REC-4), `a930ed7` (REC-4-P1), `e246f1e` (DOC-CLICK),
`71d7467` (LEAD-INTERRUPT), `abcb8ee` (карточка P2), `f4a08ea` (P2).
GitHub совпадает с HEAD; эти commits сохранены в опубликованной ветке.
Наличие commit не подменяет доказательство review: результаты Checker/Cursor
взяты из переданных владельцем отчётов и прежней истории checkpoint.

REC-4-P2 принят в своих границах. Последний Cursor отчёт: P2 HTTP 20 passed /
1 browser deselected; browser отдельно 1 passed; четыре назначенных файла
65 passed / 15 прежних failed; широкий адресный набор 118 passed /
1 deselected. Это **не новый запуск** и не полный REC-5. Авторский CDP timeout
в историческом Ledger остаётся фактом того прогона; поздний Cursor browser PASS
не доказывает новый visual sweep 360/768 или качество живой модели.

Старые падения не скрывать, не объявлять текущими регрессиями или автоматически
закрытыми. Список 15 и baseline-сравнение остаются в P2 Ledger; в частности,
устаревшее ожидание prompt v19 и потеря «Материал терапии.» — разные классы
проблем. Для нового кода нужен повторяемый baseline, исправление теста требует
основания в контракте, а не желания получить зелёный прогон.

Процессное отклонение `6c4a963`: по передаче владельца после Cursor PASS
изменились статусные строки Full Audit Task и Ledger; runtime после review не
менялся. Владелец ранее принял checkpoint с явно отмеченным исключением.
Это запись о принятом исключении, не новый оправдывающий review; прошлые строки
и Git history не исправляются задним числом. Запрет правок после PASS действует.

## 3. Реестр находок аудита (не новый продуктовый договор)

Основание: read-only аудит active baseline `f4a08ea`, прежние разрешённые
widget-логи владельца и read-only архитектурная сверка Astra. Trace prefixes
даны только как локальные указатели; сырые payload/ПД не копируются.
«Подтверждено логом» не означает устойчивое воспроизведение каждым запросом.

| ID | Уровень evidence и проблема | Где смотреть / граница решения |
|---|---|---|
| AF-01 | Log `a07cab18`: после ценового обзора проверенный «Один зуб» дал описание без цены; provider получил UI ref, но исходная price task не была закреплена | `core/d2_dialogue.py`, `core/d2_snapshot_sources.py`; D2-094, A01/A14. Передать известную задачу, не угадывать смысл по label. «Не знаю», гипотеза и другой человек не становятся диагнозом/согласием |
| AF-02 | Log `633b106d`: вопрос о местонахождении + информационная часть дал телефон; код maps `contacts` в phone и использует phone при пустом результате выбранных полей | `core/d2_contacts_cta.py`; точные tenant facts сохраняются. Состав generic contacts и поведение при отсутствующем конкретном поле требуют явного решения перед кодом |
| AF-03 | Static: история обычных пар пропускает fact-only turn вместе с вопросом, если нет model prose; точные refs/state и replay при этом существуют | `_d2_live_prose_for_history` / `_next_d2_dialogue_pairs`; D2-094, T4. Следующий provider input проверить отдельно. Причинная доля в ошибках модели — гипотеза. Не копировать старые суммы/ПД и не менять 3 пары/1000 символов/TTL без решения |
| AF-04 | Static reachable: availability/unresolved/brand policy могут заменить весь составной ответ; whitelist отвергает contact+policy и две detail-части | `core/d2_dialogue.py`, `core/response_plan_materialization.py`; D2-095/C02. Проверить обе очередности частей. ADMIN/текущая личная боль и B14 сохраняются; не дробить каждое обычное объяснение механически |
| AF-05 | Static: общие и per-request поля повторно задают связанный смысл; корректность схемы не гарантирует выполнение вопроса | `contracts/one_call_envelope.py`, production parser. Упрощение контракта — кандидат после узких результатов, не разрешение ослаблять checks или добавлять второй normalizer |
| AF-06 | Explicit authored намеренно сохраняется после D2-105; ordinary default уже model_prose | `core/d2_content_realization.py`, Contract §5. Удаление authored не назначено обязательным исправлением. Сначала evidence необходимости; source/UI и prose различать |
| AF-07 | Screenshot/логи: заголовки, отступы, повторные кнопки и marketing tail ухудшают компактность. Часть текста добавляет code-owned commercial plan | Renderer/widget и `core/d2_commercial_plan.py`. Оформление, частота рекламы, hiding повторной кнопки и CTA — отдельные proposed решения, не silent runtime cleanup |
| AF-08 | Static: существующие ранние meta/defer ветки lead могут поглотить независимый вопрос; обычный pending→answer→resume уже исправлен и принят | Lead classifier/bridge. Сначала синтетические комбинированные случаи и privacy. Не возвращать старый answer runtime и не менять согласованный UX автоматически |
| AF-09 | Known static reliability limit: `inflight` reservation без lease после hard-crash может удерживать session | `core/d2_dialogue_store.py`; C05/C06. Это отдельный механизм надёжности, не причина контактов/живости; не объявлять закрытым на основании replay-тестов |
| AF-10 | Качество source/doctor ответа: существование ref не доказывает смысловую опору каждого утверждения; в рассмотренном doctor ответе имена есть в полном corpus | Source/prose + A10/A15/B09. Галлюцинация этим примером не доказана; отдельный doctor router и новый blocking semantic gate не назначаются |

Точные будущие implementation allowlists отсутствуют: это не карточка кодовой
правки AF-01–10. Последовательность proposed checkpoint — только в
[Delivery Roadmap](DEMO_D2_DELIVERY_ROADMAP.md), без второго roadmap здесь.

## 4. Сверка документов и старых остатков

- `CURRENT_STATUS` и верх Roadmap устарели до P2: обновить указатель на `f4a08ea`,
  старые dated разделы явно оставить историей. Не переписывать прежний Ledger.
- Contract header всё ещё на `a930ed7`; обновить. Синхронизировать уже принятое
  D2-106 с §8, без нового lead поведения.
- Фразу Contract §6 о «резервной цитате T3» ограничить поздним D2-092:
  она не разрешает заменять пригодную prose. Explicit authored по D2-105
  сохраняется; полного отказа от него владелец не утверждал.
- Product Decisions: добавить ссылку на актуальный снимок и пояснение
  исторических implementation statuses. Не менять принятые строки/создавать
  новый принятый D2-ID для предложений ассистента.
- `MARKETING_ANSWER_SCENARIOS.md` — foreign untracked памятка, не authority.
  Её общий cap 3 (строки 72/84) расходится с D2-100 для точной услуги;
  действует позднее утверждённое D2-100. Памятку не исправлять/не stage
  без отдельного allowlist; до сверки она не является текущей спецификацией.
- Старый `DEMO_D2_REBUILD_ROADMAP.md` уже маркирован историческим.
  Reconciliation Inventory/Full Audit Task относятся к своим датам и baseline,
  не доказывают сегодняшнюю полноту реализации или состояние opt-in logger.
- Старые `sales_fast*`/one_call helpers и исторические тесты остаются в дереве.
  Статически `app.py` → `d2_http_adapter` → D2; наличие старого файла не равно
  вызову. Полная транзитивная недостижимость не доказана этим doc-checkpoint:
  C08 sentinel/dependency coverage остаётся обязательной в REC-5. Ничего не удалять.

## 5. Приёмка и review этого checkpoint

**ACCEPTANCE:** документальные ссылки, точный status/SHA, разделение evidence /
proposed / owner-approved, отсутствие нового runtime GO. A/B/C не закрываются.
**D2 ROUTE / LEGACY IMPACT:** не меняются. **OWNER DECISION:** разрешена эта
документальная сверка; принятие нового порядка кодовых работ и visible решений
впереди по Lock §4. **FUTURE SCOPE:** согласование плана, отдельные кодовые
карточки, REC-5 и отдельно разрешённые live проверки с бюджетом.

Проверить local links, Git ancestry, allowlist, `git diff --check`; content diff
Contract/Decisions ограничен синхронизацией уже принятых правил. Pytest не нужен:
код/тесты/data не меняются. Независимый Checker read-only и отдельный Cursor
review обязательны до сохранения. Ledger Draft заполнить до review; после
PASS только exact staging/commit/push по отдельному разрешению владельца.

### Prompt для Cursor

Read-only review D2-AUDIT-PLAN. Начать с AGENTS.md и Execution Lock.
Папка `C:\Cursor Projects\artgents-bot-active`, ветка `codex/d2-stage1-contract`,
baseline HEAD `f4a08ea75b284cb51291fd7fe6ca64d842d8e2d0`, main/merge-base
`141ce91fb1731cd990fcf8391550150016c73e7f`. Проверить только шесть файлов
allowlist §1 этой карточки. Foreign `data/` и маркетинговую памятку не менять
и не stage; DB/raw logs не открывать. Runtime/pytest/provider/live/SMTP/commit/
push/merge/deploy запрещены. Сверить P2 commit и переданный владельцем PASS,
историчность Draft, нормативные D2-092/094/095/099/100/102/105/106, отсутствие
самовольного GO/новых CTA/authored/MD-only правил. Проверить links, allowlist и
diff --check. Выдать PASS или REJECT с P0/P1 и границами доказанного;
не переписывать Ledger после review.

## 6. Передача в новый чат

После принятия этого документального checkpoint можно продолжить в новом чате
с тем же репозиторием и веткой. Сначала новый preflight; прочитать
CURRENT_STATUS → Lock → Delivery Roadmap → эту карточку → Contract/Decisions/
Acceptance/Ledger. Передать фактический SHA нового doc commit после отдельного
разрешения commit/push, без редактирования reviewed Ledger ради self-SHA.
Если передачи до сохранения не избежать, явно назвать шесть незакоммиченных
файлов и их review status; это не безопасно сохранённый checkpoint и не GO на код.
До нового GO реализацию не начинать. Не копировать ПД/сырые логи в handoff.
