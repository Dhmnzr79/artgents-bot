# D2-REC-3 — память точной услуги и продолжения

Дата: 2026-09-26. Статус: **REC-3 в работе; владелец дал GO на реализацию**.
Это REC-3 текущего порядка восстановления, а не исторический «этап 3 — цены и объём».
Критерии ниже задают проверяемый результат по действующим D2-094, T4, Target Contract
§5/§8, Acceptance A06/A08/A10/A14/A15, B07/B08/B11, C04/C05/C07/C09/C10.

## Preflight и baseline карточки

- Единственная рабочая папка и Git root: `C:\Cursor Projects\artgents-bot-active`.
- Ветка `codex/d2-stage1-contract`; HEAD и `origin/codex/d2-stage1-contract`:
  `279b21c3504b1c2ae999575e1f44eb85567d3ac7`.
- `origin/main` и merge-base: `141ce91fb1731cd990fcf8391550150016c73e7f`.
  Это локально проверенные refs; свежий fetch в этом документальном шаге не выполнялся.
- Tracked diff и staging пусты до карточки. Чужой untracked `data/` не открывать,
  не менять и не stage. Зарегистрированный detached worktree
  `.kilo/worktrees/tulip-crawdad` на `141ce91` не трогать. Старые репозиторий,
  worktree `27e1`, checkpoint `b8b28d3` и backup — только исторические источники.
  Git предупредил о недоступности `.pytest_cache/` и global ignore; полнота
  untracked-обзора этих мест не подтверждена.
- Единственный write allowlist **подготовки этой карточки**:
  `docs/tasks/DEMO_D2_RECOVERY_MEMORY_TASK.md`. Код, Roadmap, Ledger,
  tenant data и тесты сейчас read-only. Перед реализацией повторить preflight.

## Цель и граница REC-3

**ACCEPTANCE.** Через общий D2 turn доказать: если в одном ходе однозначно
выбрана точная услуга текущего tenant, она попадает в сохранённый ordinary
state и следующий короткий вопрос использует именно её, в том числе когда
модель дала `service_id` без `topic_id`. `service_id` не означает диагноз,
подтверждённую потребность пациента или право подставить цену другой услуги.
После составного запроса фокус сохраняется только при одной однозначной
услуге; при нескольких кандидатах короткое продолжение вызывает одно
уточнение. Не выбирать последний request, первую цену или видимую кнопку
как произвольный фокус.
Сохранённый фокус должен соответствовать проверенному итоговому плану,
а не заново вычисляться из первой части `requests`. Отсутствие нового
service/topic в нейтральной policy/contact части не создаёт новую неоднозначность.

Проверенный документный follow-up и typed service/volume click передают
серверные refs и исходную задачу следующему ходу. CLARIFY сохраняет исходный
ценовой вопрос, а выбор услуги отвечает на него ценой либо честным пробелом,
не одним описанием услуги. «Не знаю» не повторяет то же уточнение и не запускает
заявку. При смене услуги прежний фокус меняется; явно названные факты ситуации
сохраняются только при разрешённой связи с тем же человеком/ситуацией.
Исправление заменяет факт, гипотеза не заменяет. Чужой человек и новая ситуация
не наследуют старые факты.

Обычный контекст живёт 30 минут бездействия по tenant policy и внедрённым
часам. На границе TTL неоднозначное продолжение уточняется, явный новый вопрос
остаётся отвечаемым. TTL не удаляет активную заявку, контакты, frozen replay
или историю неповтора UI/акций. Новая сессия не импортирует старую ordinary
memory. Сохранённые ordered offer refs остаются ID, без записи ценового free text.
Проверить два последовательных хода после истечения: просроченный ordinary
focus не должен снова стать свежим при обновлении активности первым из них.

**D2 ROUTE:** реальные offline `/ask` и `/ask/stream` → один текущий prompt и
production parser → captured tenant snapshot и проверенное UI action →
session binding/один frozen response plan → тот же store/replay. Код не
угадывает смысл по тексту, label кнопки или порядку multipart частей.

**LEGACY IMPACT:** старый Composer/sales_fast, legacy semantic selectors и
старая ordinary memory не становятся fallback или вторым owner состояния.
Внешний JSON/SSE wire, tenant ownership, lead/privacy и effect не меняются.

**OWNER DECISION:** утверждённые D2-002/003/005/007/094, T4 и Target Contract
задают видимое поведение. Владелец дал GO на REC-3, затем отдельно разрешил
добавить `core/response_plan_materialization.py` в allowlist для согласования
фокуса двух ценовых частей. Read-only разбор с Astra не нашёл противоречия
owner decisions:
действующая schema уже допускает service-only focus, поэтому topic inference
не является требованием REC-3. Если обнаружится необходимость новой связи
service→topic, нового strict gate, иного порядка уточнения либо другого
заметного поведения, остановиться и предъявить владельцу варианты до правки.

**FUTURE SCOPE:** REC-4 цены/подписи/нейтральная CTA D2-099, REC-5 полная
приёмка, старые read-only падения REC-2, live, merge и deploy. REC-3 не
переписывает коммерческий рендерер ради прохождения сценариев памяти.

## Точный write allowlist реализации

GO владельца получен; preflight повторён на `279b21c` перед кодовыми правками.
Файлы перечислены по текущим точкам чтения/записи state и целевым тестам;
наличие в списке не требует менять каждый файл.

```text
core/d2_session_context.py
core/d2_dialogue.py
core/response_plan_materialization.py
tests/test_d2_rec3_memory_http.py
tests/test_d2_session_context.py
tests/test_d2_multipart_scenarios.py
docs/tasks/DEMO_D2_RECOVERY_MEMORY_TASK.md
docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md
```

Parser/envelope schema, prompt, DB schema/store, HTTP adapter, иные файлы
materializer, tenant pack, widget, lead/privacy owner и остальные файлы read-only.
Если проверка
покажет необходимость другого файла, остановиться, назвать причину и получить
решение владельца до записи. Не переносить старую архитектуру или старый WIP.

## Проверка и ворота

- До кодовой правки зафиксировать узкий offline baseline на `279b21c`, не
  выдавая исторические тестовые числа за новый прогон. Известный старый
  `test_other_with_prose_gets_authored_help_not_price_gate` падал в REC-2 на
  `d2_experiment_content_not_resolved`; не скрывать и не менять его ради PASS.
- Fake provider, заблокированная сеть, временные DB/BOT_LOG_DIR/tenant fixtures
  вне рабочего `data/`; реальный provider budget = 0. Не запускать порт 9001.
- Сквозные цепочки: точная услуга без topic → сохранение → короткая цена и
  вопрос о враче; multipart с одной/несколькими услугами → однозначное
  продолжение/CLARIFY; проверенный follow-up и ценовой typed click → ответ,
  UI, state и replay; CLARIFY → выбор услуги; «Не знаю»; смена услуги,
  same/other person, коррекция/гипотеза, TTL до/на/после границы и два хода
  после истечения, новая сессия. Для service click проверить услугу без
  однозначного topic на отдельном synthetic catalog fixture.
  Проверять tenant isolation, stale/forged UI, lead/privacy, ordered price refs,
  одинаковый frozen результат JSON/SSE и один provider call на новый ход.
- Тесты не подгонять и критерии не ослаблять. Сравнить новые failures с
  baseline. Только затронутый offline набор, не полный CI до merge.
- До checkpoint commit: в том же diff внести Ledger Draft с доказанными
  фактами, получить независимый Checker PASS и отдельный Cursor review
  рубежа 3. После PASS — только exact staging, staged names/stat/diff/check,
  commit/push согласованной ветки и отчёт; Ledger после review не дописывать.
  PASS карточки не является implementation PASS или разрешением live/merge/deploy.

## Evidence текущего implementation diff до review

- Baseline выбранного offline-набора на `279b21c`: 70 passed / 1 failed;
  прежний тест истории `test_stage2_bounds_live_prose_pairs_and_expires_them_with_context`
  получает `spam_closed` на повторном вводе, история пуста. Тест не менялся.
- Новый HTTP-набор проходит для точной услуги без topic, двух разных/одинаковых
  ценовых частей, CLARIFY service click, смены услуги, гипотезы, TTL и replay.
  Первый совместный прогон нового и трёх соседних файлов: 84 passed / 1 failed,
  единственное падение — тот же тест истории. Выборочные проверки tenant,
  stale/forged UI, document follow-up, lead и запрета legacy: 37 passed /
  46 deselected. Более широкий промежуточный прогон до последних узких
  уточнений: 114 passed / 1 failed, тот же исторический тест.
- Первый независимый Checker review дал REJECT по двум P1: короткий price без
  повторного service ID уходил в CLARIFY; no-topic service click с CLARIFY
  переносил прежнюю ситуацию и снимок вариантов. Оба случая воспроизведены
  целевыми красными HTTP-тестами до исправления. Узкий binding теперь берёт
  только свежий активный service из текущего tenant catalog для одной ценовой
  части; topic/situation/brand не копирует. При смене услуги без topic старые
  situation/options удаляются. После исправления REC-3 + session-context:
  **73 passed**; REC-3 + session-context + multipart + R1:
  **91 passed / 1 failed** (старый `other`). Ожидается focused Checker recheck.
- Отдельный старый R1-тест для `other` остаётся красным на
  `d2_experiment_content_not_resolved` (19 passed / 1 failed в наборе с REC-3);
  не исправлялся и не ослаблялся.
- Вопрос «А кто это делает?» проверен как текущая `model_prose` с явно
  сохранённой `classic`, фактом врача из утверждённой карточки и replay.
  Старый `authored` directory path отвергается до проверки памяти; это
  отдельный baseline-gap, а не доказательство детерминированного справочника
  врачей в REC-3. Doctor source UI/CTA этим тестом не подтверждаются.
- Fake provider и временные DB/logs; реальных provider/live/SMTP вызовов 0.
  Staging, commit, push отсутствуют. Focused Checker recheck и Cursor review
  implementation diff ещё требуются.
