# D2 S2-C6: результат каждой части и независимый отказ цены

Статус: архитектурное предложение для следующего задания, реализация не начата.
Проверенная база: `391c5ad4fe8c8789c5dfbef4f7dff2dfa6b114b8`.
Папка/Git root: `C:\Cursor Projects\artgents-bot`.
Ветка: `codex/demo-d2-service-volume`.
Локальный `origin/main` и merge-base: `141ce91fb1731cd990fcf8391550150016c73e7f`.
Сеть/fetch, тесты, provider/SMTP calls и изменения кода при подготовке не выполнялись.

## Основание и выбор

Приоритет: `DEMO_D2_TARGET_CONTRACT.md` §§5–7 (результат части назначает код,
независимые проверенные части сохраняются), `DEMO_D2_ACCEPTANCE.md` C02/C04/C09,
журнал D2-042/065/072 и границы `DEMO_D2_S3_ARCHITECTURE_GATE.md`.
C5 принят; повторного аудита C5 нет. Рассмотрена только граница результата части.

На этой базе `D2ResolvedRequestPart.status` допускает только `answered`.
`resolve_d2_envelope_response` строит цену до информационных блоков; отсутствие
безопасных ценовых кандидатов выбрасывает исключение и не оставляет готового ответа
на независимый информационный вопрос. Строгий отказ цены правилен, потеря всего
составного ответа не является конечной архитектурой D2.

Цель C6: сохранить результаты частей в одном frozen plan, когда цена не может
быть безопасно показана. Пример: «Цена виниров и больно ли лечиться?» — вместо
обрыва дать утверждённое сообщение о недоступности цены и проверенный ответ о боли.
Это общий механизм результата частей, впервые проверенный на существующей price
части. Политики и маркетинг затем используют этот договор, без собственных catches
и запасных сборщиков.

## Ограниченная область

Сохранить текущие D1R ANSWER + максимум одну price part + content parts.
Не добавлять новые виды запросов, свободную прозу/T3, политики, маркетинговые блоки,
сессии, адаптер данных клиники, HTTP/SSE, widget, prompts, provider или legacy runtime.
Полная обработка всех видов частичных ошибок не объявляется завершённой C6.

Смысл по-прежнему поступает только из `RequestUnderstanding.requests`.
Нельзя перебирать слова вопроса, выбирать похожую услугу или исправлять ссылки.
Нельзя запускать старый путь/второй LLM при ошибке.

## Граница отказов

1. Проверить tenant, формат и все ссылки всех частей до recoverable materialization.
   Поздняя чужая ссылка не может затеряться за ранним recoverable отказом цены.
2. Только два ожидаемых результата подбора цены допустимы для локального отказа:
   `d2_no_complete_price_candidates` и `d2_no_scope_price_candidates`.
   Лучше возвращать из внутренней price materialization типизированный результат
   ready/unavailable. Если сохраняется исключение — обрабатывать только эти точные
   коды в этой границе. Общий `except Exception/ValueError` запрещён.
3. C4 отбор не меняется: известный объём требует явной applicability, фильтрация
   до ranking/cap, нет умножения на зубы/челюсти и подстановки несовместимой цены.
   Отказ strict selection теперь фиксируется в части, а не теряет соседний ответ.
4. Malformed D1R, чужой tenant, неизвестный/неразрешённый ID, несовместимые refs,
   повреждённый snapshot, неизвестный режим и ошибки программы остаются fatal.
   C6 не превращает их в «нет цены» или «услуга не оказывается».
5. `no_public_price` с утверждённым текстом — штатный ответ `answered`, не ошибка.
   Не менять правила выбора/лимита предложений и существующее исключение отдельных
   offers с неподтверждёнными обязательными условиями.

## Данные и plan

Развить C5 `D2ResolvedRequestPart`: `status=answered|unavailable`, а для unavailable
обязателен typed reason из двух кодов выше. Модель не возвращает этот результат.
Список частей и его порядок сохраняются полностью, без удаления неуспешной части.

Добавить отдельный маленький frozen `D2PartFailureBlock`: request_id,
source_client_id, message_id, reason, display_text. Это видимый результат отказа,
не InformationSourceBlock и не фиктивная цена. У каждой unavailable части ровно
один такой блок; у answered нет failure block. У unavailable price нет price rows,
выбранных offer IDs или price-scope choices. Обязательная связь request→block
валидируется в frozen plan, дубли/потерянные/лишние блоки запрещены.

Нужен один tenant-owned authority утверждённых сообщений в
`ResponsePlanMaterializationSources`: стабильный message_id, reason, точный текст.
Без собственной классификации и без нового контентного реестра в runtime.
Для C6 это validated fixture, существующие clinic files не редактируются.
Пример текста только для fixture: «Сейчас не могу назвать стоимость по имеющимся
данным клиники». Это не утверждение отсутствия услуги или непубличности цены.
Если нужного авторизованного сообщения нет — явный readiness/contract error,
не выдуманный текст, не прежняя цена. Наличие authority не включает альтернативный
алгоритм отбора; она нужна исключительно для отображения уже установленного отказа.

В итоговом D2 plan — агрегат `complete|degraded|failed`: все answered / часть
unavailable / все unavailable соответственно. Он выводится кодом из parts,
противоречащее значение валидатор отвергает. Для legacy plans без D2 parts значение
отсутствует. `failed` результат одиночной цены имеет видимый failure block, но
не помечается успешным. Fatal ошибки вообще не создают обычного D2 plan.

`ComposerResult` здесь уже внутренний транспорт к общему resolver, а не второй
вызов модели. Разрешить перенос типизированных failure blocks в эту существующую
связку и её validation; нельзя подставлять failure в patient_text или объявлять
visible_price_block=true при отсутствии цены ради прохождения старых инвариантов.

## Renderer, UI и память

Один проход D2 renderer по parts: answered → связанный price/content block;
unavailable → связанный failure block. Каждый ровно один раз в исходном порядке.
Renderer не ловит ошибки, не читает каталог и не создаёт сообщения от себя.

`is_price_answer` сохраняет смысл наличия видимой цены. Отдельное правило запрета
обычных follow-up/video проверяет наличие price request, даже когда её результат
unavailable (D2-072). Иначе отказ цены случайно включит кнопки другого материала.
У unavailable price нет volume choices. Допустимая независимая CTA использует
нынешнюю проверенную authority; новый автоматический призыв/сбор lead не добавлять.
При полном failed результате весь UI пуст. Успешные C1–C5 UI не меняются.

Существующий C5 scope описывает все проверенные части, включая unavailable:
при mixed отказ одной части не переключает фокус автоматически на выжившую.
Ошибочная цена не попадает в finalized/shown IDs. Situation остаётся turn-local,
`situation_delta=keep`; физической записи сессии в C6 нет. После freeze изменение
authority/snapshot не меняет ни текст, ни статусы, ни UI.

## Exact allowlist будущей реализации

```text
contracts/response_plan.py
contracts/response_plan_materialization.py
core/response_plan_materialization.py
core/response_plan_resolver.py
core/response_text_renderer.py
tests/test_d2_part_failure.py                         NEW
tests/test_d2_price_modes.py
tests/test_d2_single_request.py
tests/test_d2_price_scope_selection.py
tests/test_d2_independent_request_parts.py
docs/tasks/DEMO_D2_S2_C6_TERRA_TASK.md                 NEW
```

Четыре существующих test files разрешены только для перехода проверок ожидаемых
двух исключений на проверку unavailable/degraded/failed и отсутствия unsafe price.
Проверки успешных результатов/strict applicability не ослаблять. Отдельно оставить
fatal proof при отсутствии failure authority. Новый gate остаётся read-only.
D1R/parser, response_ui_projection.py, clinic data, session, HTTP и legacy read-only.

## Девять групп offline-доказательств

Каждый positive сценарий: валидированный snapshot и raw D1R JSON → настоящий
parser → resolver → frozen plan → renderer/UI. Не подменять материализатор.

1. Цена без полных условий + корректный content: unavailable + answered,
   aggregate degraded, оба блока ровно раз, опасных сумм и offer IDs нет.
2. Обратный порядок тех же requests: оба блока сохраняют порядок и собственные refs.
3. Known scope без применимых цен + content другой услуги: C4 strict selection
   сохранён, соседний content выжил; no multiplication/substitution.
4. Одиночная недоступная цена: failed и один failure block, UI пуст; отдельный
   no_public_price fixture остаётся answered/complete.
5. Здоровые price/content ответы остаются complete; content-only с двумя источниками
   сохраняет правило первого UI. Необязательный отсутствующий UI не делает основной
   ответ unavailable (использовать существующее поведение, новый механизм не добавлять).
6. В degraded ответе с price request не появляются source follow-up/video или volume
   choices; допустимая CTA проверена отдельно; finalized IDs не содержат отказ цены.
7. Foreign tenant/source, неверные refs и неизвестное внутреннее исключение fatal,
   в том числе foreign content после recoverable price failure. Missing/foreign
   failure authority не позволяет выдавать обычный безопасный текст из кода.
8. Инъекции в frozen plan: удалённый/дублированный failure block, ответ answered
   без цены, unavailable с ценой, ложный aggregate — всё отклоняется. Snapshot
   mutation после freeze не меняет повторный render/UI; mixed фокус сохраняет C5.
9. Sentinels запрещают Composer parser/executor, legacy semantic entry points и
   сеть на реальном поддержанном D2 пути; счётчик реальных provider calls = 0.

Разработка: запускать только затронутые nodes. На готовом checkpoint один набор:
точная C1–C5 команда из C5 task + `tests/test_d2_part_failure.py`.
После этого независимый Checker по C6 diff и матрице; после REJECT только targeted
recheck. Не повторять весь набор после каждого добавленного теста; повтор нужен
после последующих существенных изменений перед финальным commit.

## Условия выхода и остановки

Выход: все группы имеют конкретные tests, общий набор прошёл, Checker PASS,
один проверенный commit/push в текущую ветку. Отчёт явно различает offline proof
и работающий бот. S3 остаётся закрыт; live tests не выполняются.

Остановиться и сформулировать два варианта решения, если нужны второй parser,
словесные эвристики, broad catch, изменение выбора цен C4, подделка Composer input,
семантический fallback, расширение error taxonomy на политики/прозу, clinic/runtime
wiring или файл вне allowlist. Не расширять C6 по ходу.

После двух содержательных неудачных попыток одной реализации передать Sol ровно
проблемный участок. Отчёт «ещё не сделал» не повод запускать общий regression снова.
Матрицу покрытия показать до Checker, чтобы не повторять неполные передачи C5.

## Состояние подготовки

Этот gate — единственный новый файл данной подготовки. Пять прежних untracked
файлов audit/latency/S3/script сохранены. Staging пуст; commit/push не выполнялись.
Нужен отдельный исполняемый C6 task по этому gate; автоматического начала кода нет.
