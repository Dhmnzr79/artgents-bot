# D2 Execution Lock — постоянный договор исполнения

Дата фиксации: 2026-09-20. Ветка: `codex/demo-d2-service-volume`, baseline `8e7a3b6`.
Статус: **действующий lock**. Меняется только по явному решению владельца
отдельным checkpoint. Это не roadmap, не архитектурный аудит и не план работ;
факты выполнения ведутся в [DEMO_D2_CHECKPOINT_LEDGER.md](DEMO_D2_CHECKPOINT_LEDGER.md).

## 1. Реальность развёртывания

- В production **нет бота и нет пользователей**.
- Текущий локальный `/ask`, `/ask/stream` и виджет — одноразовая база для
  сравнения. Старый local runtime **не является compatibility target**:
  его допустимо заменять и временно ломать.
- Сохраняются только явно названные границы: tenant isolation,
  lead/privacy, заявки, typed UI action ownership, transport-защиты.

## 2. Неснимаемая цель

В конечном дереве остаётся **один основной D2 runtime ответа**.
Старый Composer/sales_fast semantic runtime, legacy semantic selectors
(regex/словари темы, услуги, объёма, аспекта, политики) и старая ordinary
memory **не достижимы из normal answer path**. Достижимость проверяется
на реальных `/ask` и `/ask/stream` (sentinel + dependency check), а не
одним grep и не отдельными unit-тестами.

## 3. Запреты (FORBIDDEN, без исключений до решения владельца)

1. Запрещён fallback «D2 не справился → вызвать старый runtime» — в любом
   виде: per-request, per-scenario, try/except, флаг, выбор обработчика по
   виду вопроса. Неподдержанный сценарий отвечает fail closed утверждённым
   сообщением и фиксируется как незакрытый, а не маскируется старым путём.
2. Запрещён второй параллельный semantic prompt, второй parser модели,
   второй state-контракт, второй tenant-data контракт и второй wire contract.
3. Запрещены временные compatibility fields «на переходный период»
   и второй owner ordinary state (двойная запись обычной памяти).
4. Запрещено объявлять сценарий собранным на основании unit/seam-тестов:
   собранным считается только сценарий, проходящий через общий D2 route,
   после подключения HTTP — через реальные endpoint-тесты.

## 4. Границы самостоятельности исполнителя

- Новый пользовательский сценарий, новый strict refusal/gate или правило,
  способное скрыть или сломать нормальный ответ, **нельзя добавлять без
  решения владельца**.
- Если утверждённые D2 contract, acceptance или decision log уже задают
  поведение — исполнитель принимает техническое решение сам и фиксирует
  ссылку на пункт в отчёте checkpoint. Переспрашивать владельца не нужно.
- Owner decision требуется только при: конфликте документов; новом
  пользовательском правиле; двух допустимых реализациях с заметно разным
  видимым поведением.

## 5. Обязательная форма checkpoint

Каждый checkpoint обязан явно указывать:

| Поле | Содержание |
|---|---|
| ACCEPTANCE | какие ID приёмки (A/B/C) и каким уровнем доказательства закрываются |
| D2 ROUTE | через какой общий D2-вход реально проходит новый код |
| LEGACY IMPACT | что перестаёт вызываться/становится недостижимым из normal path |
| OWNER DECISION | требуется/не требуется, и по какому пункту раздела 4 |
| FUTURE SCOPE | что осознанно оставлено следующим checkpoint |
| Allowlist | точный перечень файлов записи |
| Test isolation | временные БД/логи/tenant pack; сеть и provider запрещены offline |
| Cursor verdict | результат независимого Checker |

Значимый checkpoint **не commitится до независимого Cursor PASS**
(master prompt: [DEMO_D2_CURSOR_CHECKER_PROMPT.md](DEMO_D2_CURSOR_CHECKER_PROMPT.md)).

## 6. Приоритет документов

```text
AGENTS.md
→ D2 Execution Lock (этот файл)
→ утверждённые D2 contract / acceptance / decision log
→ текущий checkpoint prompt
```

Если checkpoint prompt слабее lock — действует lock. Молчание prompt
не отменяет ни один запрет раздела 3.
