# TASK — Lead-flow Cancel and Date/Time Safety

**Ветка:** `codex/stage-a`

**Baseline:** `5f18801 docs: note startup price quiz idea`

**Режим:** узкий code/runtime checkpoint без live/LLM.

## Причина

Read-only аудит lead-flow и узкий offline pytest выявили regression:

- `Я передумал` / `Не, я передумал` при включённом booking-date defer могут ошибочно
  классифицироваться как изменение даты вместо отмены;
- текущий internal parser сохраняет из составного пожелания вроде `завтра в 18:00`
  только первый фрагмент;
- пользовательская формулировка про дату должна ещё жёстче исключать впечатление, что
  бот принял или подтвердил запись.

Baseline evidence: `90 passed, 2 failed`; оба падения в
`tests/test_lead_turn_classifier.py` относятся к conversational cancel.

## Verification incident

Во время первых focused pytest запусков runner не зафиксировал LLM flags в `OFF`.
`test_invalid_name_is_unclear_not_slot_first` четыре раза вызвал `lead_turn_gray` для
синтетической строки `12345` (`qwen3.6-flash`, суммарная оценка `$0.0004812`). Это
нарушение режима checkpoint, поэтому оно не скрывается:

- вызовы не относились к A9/patient-scope и не изменили A9 raw/evidence;
- это не были ответы пациенту или widget session;
- после обнаружения все проверки запускаются с явными offline flags;
- финальный checker должен проверить incident statement и отсутствие последующих
  `lead_turn_gray` вызовов.

## Product contract

1. Явное `Я передумал` / `Не, я передумал` детерминированно отменяет lead-flow без LLM.
2. Составная фраза с новой датой, например `Передумал, а можно на 11-е?`, остаётся
   пожеланием изменить дату, а не отменой всей записи.
3. Любая дата/время — только пожелание для администратора.
4. Бот никогда не сообщает и не подразумевает, что дата/время приняты, забронированы,
   доступны, согласованы или подтверждены.
5. Patient-facing ответ остаётся мягким: пожелание по дате передадим, а удобные дату и
   время администратор уточнит при звонке. Бот не произносит техническое предупреждение
   о собственных ограничениях.
6. Полное распознанное пожелание даты и времени сохраняется для handoff; оно не
   показывается как подтверждённый слот.

## Scope

- сделать conversational cancel детерминированным и приоритетным;
- отделить голое `передумал` от реального изменения даты;
- не терять время в составной фразе дата + время;
- усилить нейтральный booking-date copy в default config и demo override;
- синхронизировать owner/technical docs;
- добавить/обновить узкие offline tests.

## Allowlist

- `TASK.md`;
- `lead_interrupt.py`;
- `core/booking_date_defer.py`;
- `core/client_config_loader.py`;
- `clients/demo/tone.yaml`;
- `tests/test_lead_turn_classifier.py`;
- `tests/test_lead_interrupt.py`;
- `tests/test_booking_date_defer.py`;
- `docs/MARKETING_QUESTION_FOUNDATION.md`;
- `docs/MARKETING_QUESTION_TECH.md`.

## Protected / вне scope

- CTA-context и состав заявки;
- `Рассказать о ситуации` и hard-stop precedence;
- видимая кнопка выхода из первого lead-экрана;
- email/CRM/n8n delivery;
- остальные lead-flow состояния и UI;
- Pricebook, service catalog и marketing schema;
- A9 design/raw/harness/evidence;
- live/LLM, authority, merge и `main`.

## Verification

1. Governance checker `✅` до code changes.
2. Focused pytest для cancel/date и соседнего lead-flow набора с явными
   `LEAD_TURN_LLM_CLASSIFY=0`, `BOOKING_INTENT_LLM_ON=0`, `PRICE_INTENT_LLM_ON=0`.
   Unit-test booking-intent cache запускается отдельно с monkeypatch classifier-а.
3. Новые тесты доказывают:
   - `Я передумал` и `Не, я передумал` → `meta_cancel` без gray LLM;
   - `передумал, а на 11?` → `booking_date`;
   - `завтра в 18:00` сохраняет оба фрагмента;
   - patient-facing copy мягко передаёт пожелание администратору и не содержит обещания
     или намёка на согласованный слот.
4. `git diff --check`.
5. Verification incident зафиксирован; A9 raw/evidence не затронуты.
6. Финальный независимый checker `✅` до commit/push.

## Definition of Done

- два исходных failing tests исправлены правильным runtime behavior;
- focused offline suite green;
- все проверки после обнаруженного incident принудительно offline; incident сохранён в
  checkpoint без ложного заявления «live не было»;
- commit/push только в `origin/codex/stage-a`;
- рабочее дерево чистое.
