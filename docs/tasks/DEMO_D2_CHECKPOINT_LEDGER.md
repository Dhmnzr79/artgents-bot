# D2 Checkpoint Ledger — таблица подтверждённых фактов

## Составные ответы §24 — 2026-10-06

Owner GO: ordered details вместо singular field; полный ответ перед existing
lead result. Baseline9179cbb + WIP§23; bug fixes/contract replacement.
Financial ownership/UI authenticity/medical/lead privacy сохранены.
Executor90PASS/123.66s _yjedewx; Independent Checker19PASS/27.39s, REJECT
единственный P1: коммерческие addons после name prompt. Исправлено renderer
порядком существующих exact clinic tail parts, новые JSON/SSE price+booking
fixtures; focused Checker PASS10/12.88s xcv1ucp7.
Финальный executor48PASS/75.92s uxsljsme (compound21 + source_followup27). Provider/live/SMTP0, isolated DB/socket block.
Baseline legacy price_details_http18FAIL/3PASS/21.47s owiluild на clean9179cbb.
Old receipts несовместимы без изменения DB/заявок; migration/reset/adapter0.
Staging пуст; implementation commit/push/merge/deploy0; foreign data/SIM0
сохранён. SIM4/5/REC5 и live/widget не аттестованы. Числа прогонов не суммировать.

## Кодовые ответы §23 — 2026-10-06

Checkpoint до правок:9179cbb, локальный commit21files с §18–22; push0.
Runtime bug fixes/presentation, не simplification: compact price/unit rows,
no extra CTA footer при bookingbutton, off_topic UI, effective policy IDs
в существующей completion, booking unclear без pediatric fallback,
strict ordinal. Нет новых model calls/fields/states/schema version/adapters.
Executor49PASS/53.93s 0vh_6gg3 + guidance36PASS/55.29s 813k4cts;
после первого прогона добавлена только punctuation кодовых условий;
финальный независимый copy/new-path34PASS/31.59s 0up1l3nv. Socket blocked, isolated
DB; provider/live/SMTP0. Legacy lead scenarios7FAIL подтверждены на чистом
9179cbb:7FAIL/2PASS/17.40s k6e6prxm, старый envelope format, не регрессия.
Multiple details и booking+sibling НЕ закрыты: отдельные owner decisions
о frozen representation и порядке lead intake. Widget/live не аттестованы.
Foreign data/SIM0 на месте; staging пуст, новых runtime commits/push нет.

Independent Checker PASS bug fixes/presentation, P0/P1 нет. P2 недостаток
booking prohibition coverage закрыт четырьмя child/OMS JSON/SSE fixtures:
executor4PASS/5.50s 2fi43peu; focused Checker4PASS/5.11s 709rnsug.
Проверены authored policy, отсутствие false pediatric/lead mutation и replay.
Числа отдельных прогонов не являются уникальным общим числом tests.

## Явные дубли demo price data — 2026-10-06

Interface §18 owner GO, baseline e19fd5e, codex/d2-stage1-contract.
В 14 offer JSON удалён повторный caveat из package.label; единица/состав
объекта цены и обязательные условия сохранены. Implant-supported полный
caveat с КТ остаётся; sinus-lift условие объёма костного материала и доступа
сохранено. 3 one_stage не унифицировались: различаются «по показаниям».
Проверка всех полей 33 offers against HEAD: PASS, только 14 labels отличаются.
Загрузка snapshot/bundle/model_view: PASS,33 offers. Runtime/schema unchanged;
provider/live/SMTP0. Дополнительный offline/review выполняются; widget
line-break defect не исправлен. Model experiment не создавался/не запускался.
Executor:52PASS/63.28s h5zp3brp/results.xml, network-blocked runner,
guidance36+copy16. Independent Checker: PASS, P0/P1 нет. diff --check чист.
Независимые16PASS/8.71s kaokna0z; all33JSON и сохранность caveats подтверждены.
Новый tenant fingerprint несовместим с новым ходом старого SID по прежнему
валидатору; stored replay/lead rows сохранены. Нового recovery/migration нет.
Staging пуст, commit/push нет; foreign data/SIM0 сохранены.

## Owner widget findings / checkpoint publication — 2026-10-06

После offline/Checker §17 owner выявил неудовлетворительную текстовую подачу:
price bullet продолжения становятся отдельными абзацами в текущем widget;
package label и required conditions дублируют исключение разным регистром и
пунктуацией. Виджет НЕ прошёл приёмку. Не считать §17 общим quality PASS.
Изменений для устранения этих findings в этом checkpoint нет.
Owner разрешил commit/push накопленного SIM4/§14–17; baseline4d4b027,
ветка codex/d2-stage1-contract. Foreign data/SIM0 исключены, секреты/логи/БД
не публикуются. Следующий модельный experiment только обсуждён, не реализован
и не запущен. Модель и hard budget ещё не согласованы. Merge/deploy не входят.

## Редактура кодовых цен и деталей — 2026-10-06

Owner GO на таблицу текстов, Interface §17. Presentation bug fix, не
архитектурное упрощение. Убраны повторные заголовки price_detail и цепочки
условий через точку с запятой; добавлены согласованные подписи общего состава,
различий, исключений и оплаты. Snapshot/runtime baseline перед этой правкой:
%TEMP%/d2-price-copy-baseline-20261006. Прежний §15 diff не относится к §17.
Суммы, scope/units, approved no_public_price, пункты packages, timing и
выбор offers сохранены. В demo меняются только introduction_text с сохранением
их смысловых условий. Model/UI/session/lead/medical механизм не меняется.
Executor: 82 PASS/5 baseline FAIL,135.85s moz7_83i; focused4 modes PASS/1.83s
st61nm01. Old price_modes fixture content_realization отклоняется до renderer;
cleanHEAD те же5FAIL/2.43s y_x040ua. Старый тест не мигрировался.
Independent Checker:16uniquePASS (12/8.92s99_z7tq9 +4/1.61st12_sog9),
snapshot scope и baseline/current XML failures проверены. Финальный PASS§17,
P0/P1 нет; live/widget/Cursor§17 не аттестованы. Provider/live/SMTP0,
staging пуст, commit/push/merge/deploy нет. Foreign/прежний WIP сохранены.

## Передача заданных параметров в D2 prompt — 2026-10-06

Owner GO Interface Task §16; prompt-only bug fix, не simplification.
Prompt v39: общее правило сохраняет явно заданные brand/volume/payment
в существующих полях операции; один нейтральный пример price_detail.
Убрана отдельная краткая инструкция brand ID, объединена с общим правилом.
Schema, серверный подбор, память, provider settings и число вызовов не менялись.
Executor: 18 PASS /41.19s, изолированный runner, сеть заблокирована;
%TEMP%/d2-interface-offline-y9vm5dbg/results.xml. Проверены production prompt,
clarification/click/replay/следующий input и соседний admin path.
Это не доказательство live извлечения бренда. Owner передал Cursor PASS§16,
47PASS/1baselineFAIL,15.67s8eyvfyjb; затем сообщил «вроде всё окей» в widget.
Raw live trace в этом checkpoint повторно не анализировался.
Checker выявил новую тестовую несовместимость: helper ожидал пять примеров.
Узкое расширение allowlist test_d2_sim2_contract.py объявлено до правки;
сохранены прежние parser assertions и добавлена проверка шестого примера.
Targeted executor: 7 PASS /4.67s, 9wcu020b/results.xml.
Independent Checker PASS v39, P1 helper закрыт; focused 7 PASS /4.69s,
378a272v/results.xml. P0/P1 нет; live/widget не аттестованы.
Provider/live/SMTP0; branch codex/d2-stage1-contract, HEAD4d4b027,
staging пуст, commit/push/merge/deploy нет. Прежний WIP и foreign сохранены.

## Demo audit fixes: policy action и brand details — 2026-10-06

Owner GO после read-only Astra; bug fixes Interface Task§15, не simplification.
Baseline4d4b027 плюс сохранённый SIM4/§14 WIP. Политика запрещает booking CTA
доfinalUI, details передают brand/extent существующему price owner; verified
click сохраняет offers, явный selector conflict остаётся strict, пустой набор
публикует gap. Model/state/wire поля и model calls не добавлены.
До исправления два адресных новых теста на чистом HEAD:2FAIL/4.39s b6d1gj8u,
именно CTA после child refusal и3brands вместоNobel. ApprovedbrandID=nobel_biocare,
label Nobel; данные реального tenant не меняются. Executor60PASS/105.84s
dic2tpmj; extent2PASS/4.26s e5u9ev54; финальный ref forged-click уточнён в тесте,
Checker PASS bug-fix§15, P0/P1нет.22uniquePASS:20/43.32s o2bhrwwj и
2/4.03s r6etvt5b; повтор6child/default_consult PASS14.99s ahi2taso не суммировать.
Cursor и widget pending; новый runtime не менялся после проверки.
No live/provider/SMTP0; staging пуст, commit/push/merge/deploy нет.
Medical paused UI/contact action/hard-crash внеscope; previousWIP иforeign сохранены.

## Public demo: квоты и ручная новая беседа — 2026-10-06

Baseline 4d4b027 плюс существующий SIM4 WIP, codex/d2-stage1-contract.
Owner GO Interface Task §14: 10 attempts/SID, 200 rolling24h, 40/60sec peer;
demo_stub не менять. Одна техническая SQLite таблица и callback перед transport;
HTTP429/SSE error, friendly client copy, существующий resetSession по клику.
Semantics/§3/lead/tenant protections не заменялись; это bug fix, не simplification.
Executor:48 PASS/94.94s __2jjas8 +3 targeted PASS/8.43s ssjhdaw9; JS PASS.
Дополнительный compatibility набор28 PASS/11 FAIL46.36s mh00wnny; чистый HEAD
те же28 PASS/11 FAIL49.36s gqhn37bi. Старые diagnostic fixtures не менялись,
baseline debt не закрывается. Полные результаты и exact allowlist — Interface§14.
Independent Checker PASS, P0/P1 нет:12 unique cases PASS (9m01b_zr9/16.74s;
vd1cfm2e3/7.68s), JS PASS. XML comparison подтверждает одинаковые11baselineFAIL.
Cursor/browser/live не проведены. Calls0,
staging пуст, commit/push/merge/deploy нет; SIM4 WIP и foreign data/SIM0 сохранены.
До публикации проверить trusted proxy/IP: remote_addr за прокси может быть общим.
Суточный предел защищает общий demo файл независимо от смены SID/IP; раздельные
БД не делят счётчик. Квота не гарантирует точную сумму расходов.

Cursor PASS текущего checkpoint:12 PASS/21.42s (jkbkakgi), JS PASS, calls0.
P2 test_d2_full_audit factory исправлен для kwargs/admission; exact allowlist
расширен только этим тестом и текущими report docs, runtime не менялся.
Focused22cases:12 PASS/10 FAIL14.96s (`accrzrk9`);
чистый HEAD:12 PASS/те же10FAIL16.07s `624a6mm5`. Старый full-audit debt остаётся,
полный PASS этого файла не заявляется. SIM4 snapshot Cursor недоступен для
чтения; отделение SIM4 выполнено по diff, не побайтово.

## SIM-4 — актуализация приёмки, 2026-10-03

Baseline 4d4b027, codex/d2-stage1-contract. Owner GO на продолжение;
админка/оптимизация базы вне scope. Exact allowlist и трассировка — верх SIM4 Task.
Устаревший overview test импортировал удалённый _situation и останавливал
collection на исходном HEAD. Fixture заменён прямым volume; assertions требуют
отсутствия patient state и проверяют текущий scope.volume. Старую структуру
не возвращали. Runtime и tenant data неизменны, нового упрощения не заявляем.
Executor: 92 PASS /133.00s (44 overview +36 guidance +12 clarification);
изолированный runner t41z8gih. Baseline collection failure: fma5zyty.
Astra подтвердила current configured-only price path. Independent Checker PASS
текущего checkpoint: 48 PASS /73.54s (44 overview +4 unknown/detail),
258y7xh8/results.xml; P0/P1 нет. Повторы executor/Checker не суммируются.
Старые CI debts, Cursor и live/widget не закрыты. Calls0, staging пуст,
commit/push/merge/deploy нет. Foreign data/ и SIM0 сохранены.

## UI отмены записи и подготовка публикации — 2026-10-03

Interface Task §12: отмена только при телефоне, включая его паузу; оба пути
запроса имени без отмены. Independent Checker PASS, новые 6 offline cases PASS.
Старый phone-pause тест: 1 PASS / 1 FAIL на случайном 999 в timestamp,
не на утечке телефона; точные результаты в §12. Live/widget не аттестованы.

Владелец разрешил commit/push совокупного checkpoint D2-119/120/§12.
Текущие заголовки документов сверены с результатами; нижние DOC/implementation
отчёты сохраняют исторические HEAD и состояние Git на момент проверки.
Публикация не означает merge/deploy или завершение SIM-4/SIM-5/REC-5.

## Runtime D2-120 — medical continuation / error display, 2026-10-03

Owner GO, baseline и exact 16-file allowlist — Interface Task §11.
Bug fixes: medical завершает ход, не весь SID; прежняя history получает
medical вопрос/ответ для следующего модельного вызова. Medical current-turn
защиты и spam_closed сохранены. Widget/JSON client показывают нейтральную
фразу при сбое, серверные ошибки/логи/lead receipts не превращаются в успех.
Новых classifier/state/model calls/retries/recovery нет. Prompt v38.

Executor: 33 offline PASS (16 новых + 15 D2-119 + 2 lead pause), node client
fault tests PASS. Browser harness не проверил DOM: CDP Runtime.enable timeout
одинаков на текущем коде и snapshot baseline. Live/widget/full CI не аттестованы.
Проверена post-commit demo_stub заявка: ошибка выдачи ответа не стирает её,
same-ID replay возвращает прежний receipt без нового эффекта. Pre-commit сбой
логируется без успешного completion. Точные артефакты — Task §11.1.
Independent Checker: 18 уникальных HTTP PASS и node error-copy PASS.
1615 файлов вне allowlist неизменны.
В первом review найден P1: medical→одно spam warning→medical блокировал
правильный admin. Guard исправлен; spam_closed сохранён. Executor focused
4 PASS, включая две новые проверки: теперь 35 уникальных HTTP cases,
без суммирования повторов. Independent focused recheck 4 PASS, P1 закрыта;
полный review повторно не запускался. Окончательный вердикт: **PASS D2-120**,
P0/P1 нет. Это PASS bug fixes, не аттестация упрощения всей архитектуры.
HEAD `36105d7`, branch `codex/d2-stage1-contract`, staging пуст; commit/push/
PR/merge/deploy нет; provider/live/SMTP 0. Foreign data/SIM0 сохранены.

## Runtime D2-119 — 2026-10-03

Текущий runtime результат и точные проверки: Interface Task §10.6–10.7.
Baseline/HEAD `36105d784dc672228a693e30ee3948c95bc43dcc`, branch
`codex/d2-stage1-contract`; main/merge-base `141ce91fb1731cd990fcf8391550150016c73e7f`.
Ordinary authored/fallback удалены из active input, known parser, realizer
и publication contracts. Unknown публикует согласованную фразу/CTA без модели
и прайса, сохраняет topic/volume в completion. Price buttons скрывают нажатое
по услуге в existing memory; source follow-ups продолжают скрывать показанное.
Prompt v37 уточняет medical/admin и точные policy IDs в прежнем вызове.

Executor: 178/183 PASS в первом наборе; исправлены test expectations и
адресно перепроверены. С дополнительными old-authored/lead probes — 185
уникальных cases с успешным последним результатом; это не один полный rerun.
Независимый Checker: **PASS**, P0/P1 нет; 48 уникальных cases с успешной
последней проверкой, без суммирования reruns. Active schema/AST проверены,
diff --check чист, 1615 tracked файлов вне allowlist неизменны.
Live качество выбора admin/policy и
source refs требует пользовательского widget; provider/live/SMTP агентом: 0.
Не закрыты общая архитектура, strict provider, SIM-4/SIM-5/REC-5 и полный CI.
Старые несовместимые receipts/pending отклоняются без recovery; сохранность
lead/state/request rows проверена, подробная граница и replay в Task §10.7.
14 файлов exact allowlist, staging пуст; новый commit/push/PR/merge/deploy нет.
Foreign `data/`, `docs/tasks/DEMO_D2_SIM0_TASK.md` не читались и не менялись.
Ниже сохранена история предыдущих checkpoint, включая прежний DOC-only статус.

## D2-119 — согласование правил и плана, 2026-10-02 (DOC)

Действующие правила — Product Decisions D2-119, план — Interface Task §10.
Это изменение документации, не новый runtime PASS. Пункты 1–11 владельцем
согласованы. Ordinary authored подлежит удалению; unknown получает утверждённую
фразу/CTA; price-details скрывают **нажатое**, новая услуга допускает свои кнопки;
medical/admin сохраняет существующую фразу/телефон. Patient-state и stage-меню
не возвращаются. Content/video скрывают показанное по прежнему правилу.

| Область | Согласовано | Реализовано / offline | Widget |
|---|---|---|---|
| Clarification и D2-117 контекст | Да | Прежние scoped PASS, не повторять замену | Частичные наблюдения, не общий PASS |
| D2-118 source binding/UI | Да | Прежний scoped PASS | Кнопки появляются; ordinary authored дефект открыт |
| D2-119 prose-only, unknown, detail неповтор | Да | Новые исправления не выполнены | Подтверждены исходные проблемы |
| Medical / возраст | Да, существующие правила | Исправления текущих дефектов впереди | Ordinary вместо admin и один malformed child payload |
| DOC согласование | Да | Семь документов обновлены | Не является runtime проверкой |

Baseline `%TEMP%/d2-rules-doc-baseline-xza1b8ng`, текущий WIP на a53e6b4;
branch codex/d2-stage1-contract, origin/main/merge-base 141ce91.
Exact allowlist и неизменяемые пути — Task §10.1. Исторические отчёты ниже
относятся к своему времени: их «widget не выполнен» не описывает нынешний статус.
Журнал пользователя найден в BOT_LOG_DIR `%TEMP%/d2-widget-20261002-192344`;
44 хода анализируемого отрезка не являются агентским live-прогоном. Raw не добавлен.
Текущий агентский DOC шаг: provider/live/SMTP/tests 0, staging пуст,
commit/push/PR/merge/deploy нет. Независимый DOC Checker: **PASS**, P0/P1 и открытых P2 нет.
Сверены 1 621 файл вне allowlist (хэши совпали), 105 локальных ссылок (missing 0),
§3 идентичен baseline, diff --check чист. P2 указатель Acceptance исправлен
на Task §10 и перепроверен. Это PASS правил/плана, не исправлений runtime.

## Runtime D2-118 — документные кнопки, 2026-10-02

Owner GO после обсуждения правил: исправить и затем Cursor → widget.
**Bug fix**, не архитектурное упрощение. Prompt v36 требует existing ref
использованного документа вместе с объяснением; пример duration согласован.
Две content-части одного валидированного источника сохраняют его source UI.
Два разных/неустановленных источника не заимствуют UI первого. Не изменены
приоритет видео/follow-up, лимиты, неповтор, CTA, price/choice/detail запреты,
маркетинговые правила, tenant/revision/medical/lead/privacy.
Known document click сохраняет совпадающие параметры source-parts. Проверка
всех групп кнопок дополнительно воспроизвела и исправила потерю объёма/бренда
при price→includes→stages: используется descriptor уже показанного detail.
Разные объёмы не выбираются по позиции. Новых полей/классификаторов/calls нет.

Пригодная prose с пропущенным ref сохраняется без выдуманных кнопок; retry,
refusal и выбор материала сервером не добавлены. Фактический выбор источника
моделью ещё требует live проверки. [Отчёт, Cursor prompt и widget сценарии —
Interface Task §9](DEMO_D2_INTERFACE_TASK.md#9-d2-118--источник-ответа-и-показ-продолжений-2026-10-02).

Root/Git top C:\Cursor Projects\artgents-bot-active, branch codex/d2-stage1-contract,
HEAD a53e6b4f37e1d35474f6e8c8c41bcdcb0767bddf,
origin/main/merge-base 141ce91fb1731cd990fcf8391550150016c73e7f.
Baseline этого шага: snapshot `d2-followup-baseline-70ysjbqa` = HEAD + 50 файлов
предыдущего WIP. Exact allowlist §9: 10 файлов (3 runtime, 2 tests, 5 docs).
Staging пуст, commit/push/PR/merge/deploy нет; foreign data/, marketing/SIM0 docs
не читались и не менялись. Предыдущая замена D2-117 сохраняется.

Исполнитель: source UI/новые HTTP **37 PASS**; новые probes на baseline
4 PASS/7 FAIL (потеря UI у одного документа с двумя частями + prompt).
Regression **131 PASS/19 FAIL**; все 19 fail IDs/сообщения совпали с baseline
3 PASS/19 FAIL (old price-details raw fixtures + прежнее menu-copy ожидание).
Новая detail-chain: до fix 2 FAIL, после fix и known-detail recheck **5 PASS**.
Артефакты и времена в Task §9.1; числа не суммировать. Полный CI не зелёный.
Independent Checker: первый набор 41 PASS; найдена P1, когда source-part без
scope исключалась до проверки одинаковости и click заимствовал чужой объём.
Исправлено, добавлены оба порядка JSON/SSE с replay/next; focused recheck
6 PASS, P1 закрыта. Всего независимых 59 уникальных cases / 61 executions
(41 + 14 + 6; два повторных detail-chain), failures 0. Исполнительский
полный повтор нового HTTP-файла: 27 PASS, 54.06 с. AST 45 корректны,
103 локальные ссылки/missing0, diff --check чист. Окончательный verdict:
**PASS — D2-118**, P0/P1 нет; bug fix, без live/widget аттестации.
Provider/live/SMTP **0**. Cursor и
ручной widget проход с лимитом 40 действий подготовлены, ещё не выполнены.

## Runtime D2-117 — единый контекст обсуждения, 2026-10-02

После «Делаем» реализована архитектурная замена: operation.volume → прямой
price extent → DiscussionScope в завершённой части → одна receipt projection
следующего input. Из активного D2 удалены subject/situation, patient state/focus,
current/same/cross carry, bind/seed и старый envelope materialization adapter.
Обсуждение не превращается в медицинскую запись. Возрастные/payment правила
используют прямые age_group/context; прежние medical/price/UI/lead защиты
сохранены. Единственные владельцы — Target Contract §3.

Трасса, удаления, добавления, точные allowlist/файлы, Astra consult и риски:
[Interface Task §8.7](DEMO_D2_INTERFACE_TASK.md#87-runtime-d2-117--результат-и-границы-evidence-2026-10-02).
Новый state/schema5 отклоняет старые schema4 SID/completion, включая replay,
без migration/reset/recovery. SQLite state/request/lead rows byte-equal после
отказа; активное имя и сохранённый submitted receipt не удалены. Новый SID
контактов не наследует. Это локальный baseline, не production deployment.

Отдельно исправлен known document click после recovered authored fallback:
он сохраняет показанные target/volume/brand, как после answered. Независимая P1
воспроизведена и закрыта focused recheck. **D2-118 целиком не закрыт:** первичный
source-free ответ без content_ref может остаться без follow-up, согласованный
исход его отсутствия открыт в §8.4. Виджет не менялся; source fallback и новый
call не вводились.

Исполнитель: общий offline **447 PASS / 96 FAIL**, 511.70 с; 32 ошибки миграции
tests исправлены, targeted повтор **57 PASS / 0 FAIL**, 88.11 с. Оставшиеся
64 fail cases сопоставлены с baseline HEAD + 21-file WIP; разбивка и особый
diagnostics/materialize случай приведены в §8.7. Отдельный новый context/scope
набор 47 PASS. Прогоны пересекаются, числа не суммировать; полный CI не зелёный.
Checker: **PASS**, P0/P1 нет; собственные 77 уникальных PASS, P1 закрыта;
stage report, удаление зависимостей и 45 файлов сверены независимо.
Diff --check чист, AST 44 Python корректен, 102 ссылки/missing 0.
Provider/live/SMTP 0; fixtures не доказывают живое
понимание, strict provider, widget или архитектуру всего бота.

Root/Git top `C:\Cursor Projects\artgents-bot-active`; branch
`codex/d2-stage1-contract`, HEAD `a53e6b4f37e1d35474f6e8c8c41bcdcb0767bddf`,
origin/main/merge-base `141ce91fb1731cd990fcf8391550150016c73e7f`.
Этот этап: 13 runtime + 28 existing tests + новый test + 3 existing docs = 45
файлов относительно сохранённого baseline. Накопленный diff к HEAD: 49 tracked
modified + новый test. Staging пуст, commit/push/PR/merge/deploy не выполнялись.
Foreign data/, MARKETING_ANSWER_SCENARIOS.md, DEMO_D2_SIM0_TASK.md сохранены и
не читались. Предыдущие checkpoint ниже — история, их PASS не заменяет текущий.

## DOC — единый контекст и follow-up, 2026-10-02

Владелец выбрал один discussion context без отдельной личной ситуации и
потребовал учесть исправление тематических follow-up. Зафиксированы D2-117/118,
конкретный план замены в Interface Task §8 и приёмка. Новых правил workflow
и новых документов нет; изменены шесть existing task docs. Runtime не изменён
этим шагом; ниже сохранена история его 17-file checkpoint.

Branch `codex/d2-stage1-contract`, HEAD `a53e6b4f37e1d35474f6e8c8c41bcdcb0767bddf`,
origin/main и merge-base `141ce91fb1731cd990fcf8391550150016c73e7f`.
Baseline: этот HEAD + прежний 17-file WIP; staging пуст, commit/push/PR нет.
Foreign data/, MARKETING_ANSWER_SCENARIOS.md и DEMO_D2_SIM0_TASK.md не читались
и не менялись. AGENTS/WORKFLOW_CHECKER остаются прежними.

Продуктовое решение принято; volume/age_group/замещающий state — конкретное
техническое предложение до реализации. Удаления patient mechanism описаны как
будущие, не объявлены сделанными. Поведение старой schema/replay нужно проверить
на новой форме; прежний PASS не переносится автоматически.

Read-only Astra consult: разделять existing known-click source и первичный
ответ без source ref. Source выбирает существующий вызов модели; code/renderer
не выбирает pain/duration материал по общему topic. Исход пригодной prose без
ref пока требует конкретизации, не закрывается словом «follow-up исправлен».
Follow-up включён в карту и приёмку, но не реализован этим DOC-шагом.

Наблюдения ручного widget-теста владельца отделены от agent calls: повтор
price3 → duration давал treatment_same_requires_subject; pain/duration без
content_ref давали пустой quick_replies. Это найденные live-проблемы, не PASS
качества. Агент не вызывал provider/SMTP. Raw логи/разговоры в Git не добавлены.
Проверки исполнителя: 101 локальная файловая ссылка, missing 0; git diff --check
чистый. Хэши 70 runtime/test файлов совпали со snapshot до DOC-шага; bot/provider
тесты не запускались. Independent DOC Checker: **PASS**, P0/P1/P2 нет;
те же 101 ссылки и 70 хэшей проверены независимо. Это согласованность документов,
не runtime/source-UI PASS; исход первичного missing-ref остаётся открытым.

## Runtime — одна операция с локальным уточнением, 2026-10-02

Владелец явно разрешил реализацию exact allowlist17files Interface Task §3.3,
offline, без live/commit/push/расширения. Branch `codex/d2-stage1-contract`,
HEAD/baseline `a53e6b4f37e1d35474f6e8c8c41bcdcb0767bddf`; main/merge-base
`141ce91fb1731cd990fcf8391550150016c73e7f`. Staging пуст; публикация отсутствует.
Foreign data/, marketing, SIM0 Task сохранены и не читались.

**Архитектурное сокращение:** wrapper+nested operation → одна операция/один rN ID
с локальным clarification → удалены repeated ID check, два unwrap, все старые
clarification wrapper types/adapter и PersistedClarifyTask. State/context/click
читают ту же runtime-операцию. Pending_question заменяет seed content_text как
для service clarification, так и document known_task. Ready/pending закрытые
альтернативы generated schema; никакого нового-to-old converter/phase/handler.
Sole owners Target Contract §3, B14/D2-112, price/source/UI/medical/lead/privacy
сохранены. Price/detail click без модели; content один existing explanation-only
call, adverse answers отклоняются без retry/публикации seed.

Schema3→4 без migration/reset/recovery. Старый SID новый ход отклоняет прежним
JSON/SSE error; ordinarypayload/requestrows/leadrow остаются byte-equal.
Активная заявка сохранна; completed demo_stub receipt сохраняется и replay
возвращает его без новой заявки. Явный новый SID независим, ПД не наследует.
External delivery/store не редактировались и live не проверены.

Evidence/actual line trace/подробности — [Interface Task §7](DEMO_D2_INTERFACE_TASK.md#7-runtime-checkpoint--фактическая-реализация-2026-10-02).
106PASS/4baselineFAIL первого набора; assembled176PASS/22FAIL, из них21baseline,
одна собственная promptошибка исправлена; final contract/session/known/document
143PASS/1baselineFAIL; scope8PASS; oldschema/detailclick8PASS; receipt-replay2PASS.
Selected old detail9FAIL воспроизведены baseline9FAIL. Пересечения не суммировать.
Всего34 уникальных baselinefailIDs подтверждены чистым archivea53e6b4; полныйCI
не объявлен зелёным. Independent Checker **PASS**, P0/P1нет, собственные32PASS/0FAIL;
actualpath/removal/tests/финальныйотчёт проверены. Diff--check чистый,
AST15pyvalid,40localdoclinks/missing0. Cursor independent review **PASS** передан
владельцем 2026-10-02: P0/P1 нет, собственные **164 PASS / 1 baseline FAIL**,
115.22 с; extent-menu-copy тот же. Числа не суммируются с другими прогонами.
P2 reviewer: исторический DOC-only/e6756ee в верхе Roadmap (вне allowlist,
не менялся); schema допускает pending без clarification, ordinary parser
отвергает, server known_task допускает — согласованная граница §3.1.
Provider/live/network/SMTP0; live/strictmode/widget evidence и следующие этапы
карты не выполнены. Narrow PASS не разрешает commit/push или следующий этап.

## История DOC — конкретное предложение интерфейса, 2026-10-02

Только подготовка по передаче владельца, runtime GO отсутствует. Root/Git top
`C:\Cursor Projects\artgents-bot-active`; branch `codex/d2-stage1-contract`.
HEAD/tracking/удалённая ветка `a53e6b4f37e1d35474f6e8c8c41bcdcb0767bddf`;
main/merge-base `141ce91fb1731cd990fcf8391550150016c73e7f`, remote сверён
read-only ls-remote. До DOC tracked diff/staging пусты; checkpoint опубликован.
Исторический WIP/неисполненное разрешение ниже не являются текущим Git status.

Allowlist записи: Interface Task и этот Ledger. Трассировка schema/prompt →
parser → executor → pending → click → publication → completion → next input
показана в [Interface Task §3](DEMO_D2_INTERFACE_TASK.md).
Будущая форма — одна операция + optional clarification, content_text XOR
pending_question. Найден второй consumer двойного смысла: document known_task
использует section_title в content_text; предложение включает его замену.
Astra read-only консультация поддержала форму, шесть runtime-файлов и прежних
владельцев; это не Checker PASS/owner GO. Ordinary/known_task context boundary
остаётся в существующем parser; provider strict mode отдельно, live не проверен.

Документированы будущие удаления, добавления и их основания, exact runtime/test
allowlist, полные offline диалоги и неопределённости. Runtime/prompt/tests/data
не менялись; фактического архитектурного сокращения/изменения поведения пока нет.
Исторические 13 baseline failures D2-116 и общий CI-долг не перезапускались;
старые PASS не объявлены свежими, число пересекающихся прогонов не суммируется.
Проверка текущего DOC: diff --check; independent DOC Checker verdict и link
validation указываются в отчёте текущего чата после review. Bot pytest не нужен
для этой документации и не запускался. Новых provider/live/SMTP0;
stage/commit/push/PR/merge/deploy0. Foreign data/, marketing и SIM0 Task
сохранены, не читались. Следующий шаг — обсуждение конкретного runtime GO.

## Разрешение checkpoint — 2026-10-02

Владелец разрешил commit/push накопленного WIP и документов под именем
`chore(d2): checkpoint sim4 and audit handoff`. SHA/успех push подтверждаются
Git и отчётом публикации. Ниже DOC WIP описывает состояние до этого разрешения.
Дополнение правил: независимый DOC Checker PASS по четырём файлам; замечание
о разграничении DOC allowlist исправлено. Новый runtime/live не разрешён.

## DOC WIP — подготовка передачи после аудита, 2026-10-02

Владелец согласовал подготовку документов и исходного состояния перед новым
чатом. Baseline e6756ee + существующий SIM4/D2-116/prompt33 WIP, ветка прежняя.
Read-only аудит и ручные наблюдения не являются общим runtime PASS.
Текущий факт ручного prompt33: 7 запросов, 1 malformed JSON, 6 ответов;
finish_reason отсутствует, таймаутом ошибка не отмечена. Агент provider0.
Документальный scope и handoff — [карточка](DEMO_D2_INTERFACE_TASK.md).
Независимый DOC Checker PASS для семи документов: 110 локальных ссылок,
git diff --check чист. Runtime WIP повторно не аттестован.
Git checkpoint не создан/не опубликован;
для commit/push требуется отдельное разрешение, передача пока не завершена.

## WIP — prompt33, 2026-10-02

Владелец разрешил исправление найденного примера. Известное направление с
объёмом показано direct price; genuine unknown-service clarification сохранён.
Baseline e6756ee + прежний WIP. Runtime и схема не меняются; гипотеза влияния
примера на модель требует live-проверки с отдельно разрешённым бюджетом.
Offline: 15 PASS /24.53s + 2 PASS /5.51s. Independent Checker PASS,
его отдельный запуск: 5 PASS /3.51s. Provider/live/commit/push0, staging пуст.
Подробности — [SIM4 Task](DEMO_D2_SIM4_TASK.md).

## WIP — D2-116 три ценовых ответа, 2026-10-02

Владелец согласовал общий механизм и дал GO реализации. [SIM4 Task](DEMO_D2_SIM4_TASK.md)
содержит точный scope; [D2-116](DEMO_D2_PRODUCT_DECISIONS.md) заменяет прежний
few_teeth gap и узкий prosthetics pool. Baseline e6756ee, ветка прежняя,
staging пуст. Прежние SIM4/prompt31 PASS ниже не подтверждают этот новый diff.
Provider/live/SMTP0; foreign WIP сохранён. Основной offline: 92 PASS /118.70s;
соседний: 49 PASS, 3 FAIL /78.19s; availability/recovery: 10 FAIL /21.38s.
Те же 13 failure IDs воспроизведены на чистом HEAD e6756ee: 13 FAIL, 1 PASS
/24.30s. Полный CI не заявлен. Независимый Checker D2-116 PASS, собственный
прогон 36 PASS /55.68s; widget ещё не проверен. Это не закрытие SIM4;
Cursor gate остаётся. Подробности и ограничения — SIM4 Task.

## WIP — сохранение объёма при уточнении услуги, 2026-10-02

GO владельца после ручного диалога с потерей явно указанного объёма.
Тип bug fix prompt31, не архитектурное упрощение; pending/click runtime прежний.
Scope и allowlist — [SIM4 Task](DEMO_D2_SIM4_TASK.md). Astra read-only consult:
поля уже сохраняются, причина в omission модели; новые поля/owner/retry не нужны.
Offline проверяет корректно сформированную задачу и отдельно честно показывает
предел adverse omission. Качество живой модели не подтверждено. Checker PASS;
provider/live/SMTP0, staging пуст, commit/push нет. Foreign WIP сохранён.
Targeted offline: scope HTTP + SIM2 contract + SIM1 known actions —
70 PASS / 67.59 s, temporary DB/logs и socket block. Предыдущие fixture/setup
ошибки и исправления записаны в карточке; runtime проверки не ослаблялись.
Independent read-only Checker: 12 PASS / 26.09 s; traced pending → click →
price → completion → next context. PASS только bug fix и границ ответственности,
не live-model и не закрытие SIM4. Cursor остаётся следующим gate.

## Checkpoint — SIM-4 explicit overview, 2026-10-02

Owner делегировал выбор правдоподобного демо-набора из demo pricebook.
D2-115 фиксирует фактические offers и порядок, D2-114 сохраняет свободную prose.
Baseline HEAD/origin e6756ee, main/merge-base141ce91, branch codex/d2-stage1-contract.
Root C:\Cursor Projects\artgents-bot-active; точный allowlist в SIM4 Task.
Свой DOC WIP D2-114 включён; foreign data/, marketing и SIM0 Task сохранены.

Заявленное упрощение: catalogue fallback + brand expansion/ranking/scales +
implicit overview projection → explicit direction pool + общий brand/extent
filter + one offer/service + cap3. Exact-service ветка, цены и applicability
не меняются. Добавлено правило представителя методики, без новых управляющих
полей/моделей/памяти/verifier. Astra консультация поддержала существующий формат.
Targeted offline: 126 PASS соседних AF1a/SIM1/SIM2; новый исправленный набор
43 PASS / 48.65 s + focused 1 PASS / 3.54 s (четвёртый exact-service offer),
все 44 актуальных cases. Первый прогон имел 14 fixture failures, разобраны
в SIM4 Task; проверки данных не ослаблялись. Independent Checker PASS:
собственные 44 PASS / 48.51 s, оба endpoint и removal trace подтверждены.
98 локальных ссылок разрешаются, diff --check чистый. Cursor gate ещё впереди;
runtime checkpoint не закрыт, полный CI и widget/live не аттестованы.
Provider/live/SMTP0; commit/push/merge/deploy не разрешены.

## DOC checkpoint — SIM-4/D2-114, документальное решение, 2026-10-02

Owner принял приоритет свободного разговора и риск финансовой ошибки prose;
попросил записать решение и идею будущей админки. Astra read-only consultation
подтвердила: произвольная prose без смыслового verifier не даёт строгой гарантии
T3 для всего ответа. Новый owner decision D2-114 заменяет эту часть D2-108.
Точность кодовых цен/условий и tenant/UI/medical/lead/privacy не ослаблены.

Root C:\Cursor Projects\artgents-bot-active; branch codex/d2-stage1-contract;
HEAD/origin branch e6756ee59df4f186e499c29ae41cda0e993d80fe;
origin/main и merge-base 141ce91fb1731cd990fcf8391550150016c73e7f.
Staging пуст; foreign data/, маркетинговый файл и SIM0 Task не открывались.
Allowlist (только документация): Product Decisions, Target Contract, Acceptance,
Delivery Roadmap, Current Status, Execution Lock, этот Ledger и
../WORKFLOW_CHECKER.md. Runtime, prompt и тесты не меняются.

Документы согласуют свободную публикацию prose с принятым риском, кодовые
финансовые источники и запрет новых смысловых gates. В Roadmap сохранена
будущая идея админки: сигналы/ручные отметки, выборка, сводка; без реализации
и обещания полного обнаружения. SIM-4 runtime и SIM-0 подбор не закрываются;
before/after/removal карточка реализации ещё требуется.
Independent Checker: PASS только для документов; все восемь файлов согласованы,
не заявлено runtime упрощение или закрытие SIM-4. 94 локальные Markdown-ссылки
разрешаются, git diff --check exit0. Остаточная старая формулировка SIM-2
в Roadmap исправлена и focused перечитана Checker; блокеров нет.
Provider/live/SMTP0, pytest не запускался; Git-публикация не разрешена.

## Closure — SIM-3, 2026-10-02

Владелец «Делаем» согласовал запись результатов Cursor и закрытие проверенного
offline объёма SIM-3. Cursor PASS предоставлен владельцем: собственные прогоны
reviewer 13 + 66 + 142 = 221 PASS, 0 FAIL. Independent Checker PASS после
focused recheck двух замечаний; результаты исполнителя и ограничения — ниже.
Runtime после review не менялся. Исполнитель эти Cursor-запуски не повторял.

Root C:\Cursor Projects\artgents-bot-active, branch codex/d2-stage1-contract,
HEAD/origin branch 5cb58d5629bb78b07736246e12d951844bbe6c55,
origin/main и merge-base 141ce91fb1731cd990fcf8391550150016c73e7f.
Staging пуст. Closure diff: SIM3 Task, Current Status, Roadmap, Ledger,
Product Decisions (статус D2-109). Foreign WIP сохранён.

Удаление prose-only истории и recent_price_scope подтверждено по actual call path
обоих endpoint. Completion остаётся источником результата; store — writer,
projection — reader. Новых модельных вызовов и повторной классификации нет.
Live/provider/SMTP: 0. Browser/live-model и полный CI не аттестованы.
SIM0/4/5/REC5 остаются открыты. Владелец «Давай комит и пуш» отдельно
разрешил публикацию SIM-3 в текущую ветку. Commit/push result подтверждается
после выполнения; merge/deploy и новые live не разрешены.
Нижний checkpoint — история проверки до закрытия.

## Checkpoint — SIM-3 completion context, 2026-10-02

Owner «ПРинимаю» согласовал продолжительный контекст услуги/объёма через
контактные отвлечения до явной смены темы/услуги либо существующего TTL.
Root C:\Cursor Projects\artgents-bot-active, branch codex/d2-stage1-contract,
HEAD/origin branch 5cb58d5629bb78b07736246e12d951844bbe6c55,
origin/main и merge-base 141ce91fb1731cd990fcf8391550150016c73e7f.
Allowlist: [SIM-3 Task](DEMO_D2_SIM3_TASK.md); staging пуст; foreign WIP не изменён.

Архитектурное упрощение: завершённый completion → существующая projection →
следующий ход. dialogue_pairs хранит ссылки, не вторую копию assistant prose.
Удалены prose-only eligibility и recent_price_scope. В existing active_topic
сохраняется ссылка на завершённый ценовой результат; объём не медицинский факт.
Schema 3 без миграции тестовых SID; правила lead/privacy и TTL сохранены.

Offline: 176 PASS / 174.20 s (SIM3, SIM1, SIM2, session context).
Independent Checker: новый SIM3 набор 11 PASS / 28.04 s; removal trace обоих
endpoint подтверждён. Первый verdict REJECT: недостающий тест «оба филиала →
следующий input» и отсутствующий Draft Ledger; runtime blocker не найден.
Добавлен пропорциональный JSON/SSE тест. Independent focused recheck: PASS,
2 PASS / 3.79 s; оба замечания устранены. Финальный набор
SIM3/continuation/document/AF1a: 56 PASS / 129.30 s на актуальном коде.
Markdown: 87 локальных ссылок разрешаются; git diff --check exit0.

Старые price presentation/lead interrupt fixtures: 27 FAIL / 1 PASS на clean
5cb58d5, те же 27 failure IDs в текущем checkout; это прежний долг, не регрессия
SIM3. Полный CI, живое понимание модели, browser/widget не аттестованы.
Provider/live/SMTP: 0. Commit/push, merge/deploy не разрешены.
Реализация и independent Checker завершены; Cursor gate и закрытие SIM3 впереди;
SIM0/4/5/REC5 этим checkpoint не закрываются.

## Closure — SIM-1/2, 2026-10-02

Owner «Давай, потом комит и пуш» согласовал закрытие проверенного checkpoint,
учёт известных ошибок CI как отдельного долга и публикацию текущей ветки.
Root C:\Cursor Projects\artgents-bot-active, branchcodex/d2-stage1-contract,
baselineHEAD4d24043, main/merge-base141ce91, staging до подготовки пуст.
Evidence: актуальный Cursor142 PASS/202.88s, independent Checker,
widget3 PASS и узкий live4/4 PASS (клик0calls). Код после этих проверок не меняется.

CI debt принят отдельно:672/149/5 в49 offline файлах, сравнение с clean HEAD
имеет148 совпавших failure IDs и две описанные environmental разницы.
Полный CI не аттестован; до merge нужен актуальный gate без ослабления тестов
или возврата старого runtime. SIM-0/3/4/5/REC-5 не закрыты.

Для closure изменены пять документов из SIM2 Task; commit scope38 файлов
согласованного накопленного SIM-1/2 diff. Foreign data/ и маркетинговый файл,
отдельный SIM0 Task не включаются. Commit/push разрешены; новый live,
merge/deploy и cleanup нет. Git SHA/push result подтверждаются после публикации;
эта строка фиксирует разрешение и closure, не преждевременный Git-факт.

## Live — готовое объяснение prompt29, 2026-10-02

Owner «Делай» согласовал максимум4 вызова, без retries и stop-on-first-error.
Выполнено4/4 transport attempts, все успешны; SDK max_retries=0 и общий
счётчик ограничен4 до транспорта. Prompt29, observed model qwen3.8-flash.
Repo C:\Cursor Projects\artgents-bot-active, branchcodex/d2-stage1-contract,
HEAD4d24043, origin/main и merge-base141ce91; staging пуст. Runtime не менялся.
Allowlist отчёта: SIM2 Task, Current Status, этот Ledger. Копии demo/nikadent,
dialogue/lead базы и логи временные; сервер9001 и foreign WIP не изменялись.

JSON /ask в свежем SID: «Сколько времени занимает классическая имплантация
одного зуба?» → content/service classic, готовое объяснение20–30 минут установки
и3–6 месяцев приживления до постоянной коронки. Эти сроки присутствуют в
implantation__faq__duration.md текущего корпуса. Код добавил две разрешённые
promo из данных; это не независимая финансовая проза модели.

SSE /ask/stream в другом новом SID: «Я боюсь боли» → content;
«Сколько стоит имплантация?» → прямая price/topic implantation, прежний обзор
и три volume кнопки. Проверенный one_tooth click → три classic цены,0 model
calls. «А сколько времени это займёт?» → готовый content/topic implantation
с20–30 минут и3–6 месяцев. В каждом SSE: status/typing/ui/done, без error.
Все5 HTTP ходов200; lead_effect=not_requested, SMTP0, retries0.

Узкий live-критерий объяснения из корпуса: PASS в этих двух диалогах.
Независимый read-only Checker evidence/бюджета/отчёта: PASS; подтвердил
4 attempts, SDK0 retries,5HTTP200, volume0calls и готовые сроки из корпуса.
Checker дополнительных вызовов и тестов не выполнял.
Не доказана общая надёжность модели, полный CI, визуальный widget или SIM-3/4.
Обзор SIM-0 не изменён. Бюджет исчерпан, дополнительных вызовов нет.
Evidence вне Git: C:/Users/denis/AppData/Local/Temp/d2-live29-6ce570e2ef64450f8540594c3110cc2f/
report.json, provider-results.json, probe.py. Только синтетические вопросы.
Commit/push/merge/deploy отсутствуют. Для закрытия SIM-1/2 остаётся решение
владельца об учёте известного незелёного CI; live PASS его не устраняет.

## Cursor PASS актуального SIM-1/2, 2026-10-02

Владелец передал независимый read-only review: PASS актуальному diff,
блокирующих дефектов нет. Baseline4d24043, branchcodex/d2-stage1-contract,
main/merge-base141ce91, staging пуст. Reviewer подтвердил удаление повторной
классификации кнопки, прямой D2 parser/materializer, единый price owner,
prompt29, D2-112, B11/D2-012 и операцию врачей. Последняя редакционная фраза
также проверена. Foreign data/ и маркетинговый файл вне review; SIM0 отдельно.

Cursor запустил contract/dialogues/B12/continuation:142 PASS,202.88s,exit0,
с блокировкой сети/provider и временными базой/логами. Codex не повторял запуск.
Session58/widget3 и общий CI672/149/5 этим review не повторены; полный CI
не зелёный. Fake-результаты не доказывают живое понимание модели.
SIM-1/2 не закрыты: остаются живой критерий объяснения из корпуса и решение
владельца об учёте известного CI baseline. Live-budget не согласован;
commit/push/live/merge/deploy не разрешены.

Owner «Ок» разрешил только текущую синхронизацию трёх документов (allowlist
в SIM2 Task). Старые записи о запрете/отсутствии doctors помечены историческими;
нового runtime, продуктового правила или тестового запуска здесь нет.

## WIP — согласованная операция врачей для услуги, 2026-10-02

Owner «Давай делаем» разрешил doctors operation с service target и существующий
catalog renderer. Branch codex/d2-stage1-contract, HEAD4d24043,
main/merge-base141ce91; baseline предыдущий SIM-1/2 WIP, staging пуст.
Allowlist и точная схема — верх SIM2 Task. Тип: bug fix D2-035/D2-055/B12,
не новое доказательство упрощения всего бота. Prompt29, session schema2.

Модель определяет операцию/услугу один раз. Код проверяет active tenant ID,
прямо вызывает существующий каталог, публикует его точный текст и scoped
reference part. Старый classify wrapper не вызывается. Directory CTA передана
общему selector после document source CTA и до default; телефон независим.
Scoped exact parts участвуют в общем scope: same service остаётся service,
разные услуги дают mixed; отдельно state не исправляется.
Добавлены узкий вариант операции, validation, executor branch, внутренний
directory_cta argument; нет новых model calls/памяти/retries/fallback/regex.

Первый offline запуск:12 PASS/4 FAIL (ошибка API чтения completion в новых
mixed-тестах, не ответа runtime); чтение исправлено без изменения assertions.
Набор contract/dialogues/B12:128 PASS/2 FAIL,136.62s. Оба отказа — новые
same-service тесты с не scoped prose: по прежним правилам это mixed, а не
service. Тесты теперь отдельно проверяют scoped и unscoped prose; runtime
не менялся. Focused recheck всех8 сочетаний:8 PASS,12.30s. Не объявлять
единый повторный130 PASS: полный набор после тестовой коррекции не повторён.
Старый B12 doctors отказ устранён без ослабления free/expired assertion.
Независимый read-only Checker по новой операции: PASS; pytest не повторял.
Условия lead-pause и document-source приоритета подтверждены call path,
отдельный doctors-combination тест на них не добавлен. Focused Checker
последней коррекции scoped/unscoped теста: PASS, assertions не ослаблены.
Прежний docs/widget PASS и
64 PASS/1 FAIL ниже исторические. Актуальный Cursor review получен, см. верх.
Provider/live/SMTP0; commit/push/merge/deploy не выполнялись. Foreign data/
и маркетинговый файл вне scope. SIM-3/4, полный CI и SIM-1/2 closure не заявлены.

## WIP — fixtures/widget и B11/D2-012, 2026-10-02

Owner разрешил «Делаем»: актуальные документы, оставшиеся проверки и Cursor
handoff. Branch codex/d2-stage1-contract, HEAD4d24043, main/merge-base141ce91.
Точный allowlist — текущий верх SIM2 Task. Тип: сопровождение тестов/документов
и bug fixes B11/D2-012. Это не новое архитектурное упрощение и не закрытие SIM-1/2.

Документы указывают prompt28. Сообщение владельца «Работает» записано как
ручное подтверждение одного диалога о сроках, без самостоятельного live-gate.
Устаревшие HTTP fixtures переведены на native operations. Сохранены цены,
JSON/SSE, replay, failure rollback, privacy/lead и запрет старого runtime.
Historical parser unit consumers проверяются отдельно; active runtime не
получил старого конвертера/fallback. Session context58 PASS, widget3 PASS,
включая headless browser и реальные тестовые HTTP payloads. Runtime.enable
timeout не повторился в этом запуске; прежняя причина не установлена.

Offline CI49 файлов:672 PASS,149 FAIL,5 skipped. Clean HEAD archive:
672 PASS,149 FAIL,5 skipped;148 одинаковых failure IDs. Local dotenv-test
и executable-mode test без Git index объясняют несовпавшие IDs; это не полная
эквивалентность среды CI. Старые sales/D1R HTTP harnesses не подменяют D2.
CI не зелёный; Linux lint/secret/dependency и PostgreSQL jobs не запускались.

Astra подтвердила B11 regression: новая self-only проверка не сохраняла явно
reported ситуацию другого человека с новым owner. Проверка удалена; сохранение
reported/correction возвращено к прежнему правилу, no-carry и hypothetical/
unknown защищены прежними механизмами. Новых полей/памяти/вызовов нет.

D2-012 восстановлен в существующем UI selector: для только clarification/
price_clarification/deferred частей общая CTA подавлена; независимый ответ
сохраняет CTA, точная телефонная кнопка добавляется отдельно. Новый внутренний
аргумент request_parts и одно условие; wire-поля/память/вызовы не добавлены.
Фокусный recheck:9 PASS,1 FAIL. Итог шести обновлённых файлов:64 PASS,1 FAIL,
143.43s; единственный отказ — сохранённая проверка врачей.

Исторический blocker до следующего согласованного checkpoint (снят):
каталог врачей для услуги с прежней fact-window CTA.
Native target=topic doctors теряет service; target=service теряет действие.
Путь тогда не вызывал прежний directory renderer. B12 assertion был сохранён.
Предложенная операция тогда не была реализована и требовала согласования.
Затем владелец согласовал её, каталог подключён, B12 прошёл; это историческая
запись, не действующий запрет.
Независимый Checker fixtures/widget/B11/D2-012: PASS по read-only коду и
предоставленным результатам, без повторного pytest. Это узкий checkpoint,
не закрытие SIM-1/2: doctors blocker и общий незелёный CI сохранены.
Актуальный Cursor review получен; результаты в начале Ledger.
Staging пуст; commit/push/PR и новых provider/live/SMTP0. Foreign data/ и
маркетинговый документ вне scope; raw provider/log evidence в Git не копируется.

## WIP — prompt28 готовое объяснение, 2026-10-02

Тип: исправление ошибки инструкции, не архитектурное упрощение. Owner разрешил
«Делай» после разбора реального ответа. Branch codex/d2-stage1-contract,
HEAD4d240430c2ce056dc306c50e215dbb09843c6b8f, main/merge-base141ce91.
Allowlist: core/one_call_prompt_contract.py, tests/test_d2_sim2_contract.py,
docs/tasks/DEMO_D2_SIM2_TASK.md, docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md.

Материалы со сроками, тема implantation и one_tooth вошли в запрос модели;
она вернула описание задания в прямом content_text, опубликованном без
изменения. Причина выбора моделью не доказана. Подтверждённая неоднозначность
инструкции устранена: pending question только в clarification.operation,
прямой content содержит завершённый ответ. Добавлен структурный пример с
placeholder сроков из текущего tenant, без чисел по умолчанию. Prompt28,
schema/runtime/память не меняются; новых вызовов, веток и полей нет.

Offline SIM2 contract/dialogues: sandbox-прогон 31 passed, 76 setup errors;
focused recheck подтвердил WinError5 доступа к временной папке pytest.
Повтор вне sandbox: 107 passed за 116.87 с; независимый Checker prompt28 PASS,
read-only, тесты повторно не запускал.
Примеры actual prompt совместимы с parser, fake-диалоги сохраняют прежние
пути и контекст, но не доказывают сроки в реальном ответе модели. Live-quality этим
checkpoint не подтверждается; новых provider/SMTP0. Staging пуст,
commit/push/PR нет. Прежний own WIP сохранён; foreign data/ и маркетинговый
документ не открывались. Общий CI и SIM-3/4 остаются вне scope.

## WIP — D2-113 единый владелец ценового ответа, 2026-10-02

Owner согласовал изменение механизма и «Делай». Branch codex/d2-stage1-contract,
HEAD4d240430c2ce056dc306c50e215dbb09843c6b8f, main/merge-base141ce91.
Точный allowlist — верх SIM2 Task. Тип: архитектурное упрощение.
Прежний WIP сохранён; foreign data/ и маркетинговый документ не открывались.

Модельный price+extent/jaw/stage clarification удалён из допустимого union;
price внутри service/term ограничен неизвестным target. Известный service/topic
исполняется прямой price через прежний механизм. Информация/details сохраняют
параметрическое уточнение. Память использует те же ограничения через общий
TypeAdapter: старый price-parameter pending отвергается, не исправляется.
Service click создаёт обычную операцию с проверенным target, без повторного
понимания. Prompt27, schema session2; новых wire/state fields, retry/вызовов,
семантических regex и изменений offers нет. Astra согласовала подход.

Добавленная сложность: два task-типа ограничений, два производных варианта
clarification и узкий тип неизвестной price; общий адаптер проверки pending.
Это разделение разрешённых форм, не новые сценарные решения. Ответственные:
модель — смысл/предмет; existing price materializer — данные/обзор/пробел/UI;
сервер — известные кнопки. SIM-0 состав предложений не аттестуется.

Три целевых файла (SIM2 contract/dialogues, SIM1 known actions): 125 PASS
за 138.18 с, один прогон. Независимый Checker D2-113: PASS, read-only, тесты повторно не запускал.
Дополнительный test_d2_session_context.py не собрался: legacy fixture с
axis/request_ids/request_kinds/topic_ids/service_ids/requested_extents вместо
missing/operation. Файл этим checkpoint не менялся; общий CI не PASS.
Новых live/provider/SMTP0; прежний live-gate остановлен, не возобновлялся.
Staging пуст, commit/push/PR нет. Документы не разрешают live/merge/deploy.

## LIVE — prompt26 semantic gate FAIL, 2026-10-01

Owner разрешил ≤8 calls, no retries, stop-on-failure. Baseline codex/d2-stage1-contract
4d240430c2ce056dc306c50e215dbb09843c6b8f поверх существующего WIP.
4 live provider calls; 1 дополнительная sandbox-blocked попытка до сети
учтена консервативно: 5/8. SDK max_retries0, SMTP0, gate stopped.
Изолированные копии tenant и временные DB/logs, отдельный процесс prompt26;
работающий виджет не перезапускался. Foreign data/ не открывалась.

Общий price/topic обзор → volume one_tooth (0 calls) → сроки прошёл.
Страх боли → общая цена: модель вернула корректную clarification.operation
price/topic implantation, missing extent. Ответ: только уточнение, без цен
и quick_replies. Это провал согласованного обзорного поведения при успешном
HTTP, не malformed JSON. Дальнейшие сценарии остановлены; повторов не было.
Полное evidence/путь временного стенда — верх SIM2 Task. Предыдущие79offline
и CheckerPASS остаются evidence инструкции, не live-quality PASS.
Код не менялся; обновлены Task/Current Status/Roadmap/Ledger. Staging пуст,
commit/push/PR нет; browser/full CI и SIM-3/4 открыты.

## WIP — инструкция уточнения prompt 26, 2026-10-01

Owner разрешил узкое исправление после ручного live-сбоя. Baseline 4d24043,
branch codex/d2-stage1-contract, main/merge-base 141ce91; прежний WIP сохранён.
Allowlist и критерии — верх SIM2 Task. Это bug fix, не новый архитектурный этап.
Инструкция различает operation(kind/request_id) и target(type/id); добавлены
валидные структурные примеры price/content/overview с tenant placeholders.
Общий вопрос сохраняет topic; код не исправляет решение модели. Prompt 26,
schema 2. Два источника текста меню синхронизированы с D2-110; prices/offer IDs
и few_teeth в свободной речи не менялись. Astra: подход допустим как bug fix.

Предыдущий внешний Cursor PASS предоставлен владельцем: 161 тест одним
запуском на prompt 25, без browser/live. Последующий ручной live-сбой означает,
что надёжность генерации не доказана. Документация strict mode исследована;
автопереключения, retry, новых полей/памяти нет. Подробнее — SIM2 Task.
Текущая offline-проверка: два SIM2 файла, 79 PASS одним прогоном за 88.91 с.
13 новых кейсов проверяют реальные prompt examples/parser, JSON/SSE,
продолжение/replay и сохранение state при malformed operation без retry.
Независимый Checker текущего исправления PASS (read-only, тесты не повторял). Агентских provider/live/SMTP 0;
staging пуст; commit/push нет.
Foreign data/ и маркетинговый документ не открывались/не изменялись.

## WIP — D2-112 runtime и последствия schema 1, 2026-10-01

Разрешение владельца: «Давай». Branch codex/d2-stage1-contract, HEAD
4d240430c2ce056dc306c50e215dbb09843c6b8f; main/merge-base
141ce91fb1731cd990fcf8391550150016c73e7f. Allowlist — SIM2 Task §1.
Предшествующий own WIP сохранён; foreign data/ и маркетинговый документ
не открывались.

Понятные части публикуются; первое уточнение получает pending/UI, остальные
явно deferred без очереди. B14 и проверки скрытых choices сохранены. Deferred
первая цена допустима только после более раннего active clarification;
price block у deferred/unavailable запрещён. Dead authored service-menu
ветка удалена: действующие producers её не создают, availability answered.
Astra согласовала reuse deferred и удаление недостижимой ветки. Prompt 25,
schema 2; новых model fields/calls или параллельной памяти нет.

161 непересекающийся offline PASS: dialogue 53 полным прогоном, остальные
contract/action/resolver/renderer 107; новый shape guard отдельно 1. Всего
54 dialogue cases; единый полный прогон всех 54 не заявляется. Первые падения
и исправления описаны в SIM2 Task. Focused независимый Checker: PASS по коду,
сам pytest не запускал. Status/docs обновлены после его P2 о stale формулировках.

Synthetic schema-1 fixtures (JSON/SSE, с active lead/без) подтверждают
d2_invalid_turn без provider, без изменения dialogue/lead и без оставшегося
inflight request. Новый SID работает отдельно; старую заявку не переносит.
Migration/reset не реализованы; реальная data/ не читалась.

Cursor, общий CI, browser acceptance остаются открытыми. Старый CDP timeout
не стал browser PASS. Provider/live/SMTP 0; staging пуст, commit/push/PR нет.

## Исторический DOC — правило D2-112 до реализации, 2026-10-01

Владелец: «Ок. Фикисруем». Принято: понятные части сразу, первое необходимое
уточнение по порядку, остальные явно отложены без очереди; клик исполняет
только сохранённую операцию. Правило внесено в Product Decisions, Target
Contract, Acceptance, Roadmap, SIM2 Task и Current Status.
Текущий отказ при втором корректном уточнении ещё не исправлен; прежние
185 offline PASS и Checker PASS не доказывают D2-112. Новых pytest/live нет.

Baseline — существующий WIP на branch codex/d2-stage1-contract, HEAD
4d240430c2ce056dc306c50e215dbb09843c6b8f; main/merge-base
141ce91fb1731cd990fcf8391550150016c73e7f. Allowlist этого шага — семь
перечисленных документов, включая Ledger. Runtime/test WIP сохранён.
Foreign data/ и docs/MARKETING_ANSWER_SCENARIOS.md не открывались.
Commit/push/PR нет; provider/live/SMTP 0. Локальные ссылки и git diff --check:
PASS. Независимый Checker: PASS документальной фиксации D2-112; runtime
не проверялся и этим PASS не аттестован.

## WIP — combined SIM-1 + ядро SIM-2, 2026-10-01

Владелец согласовал изменение границы checkpoint и реализацию («Да»).
Branch codex/d2-stage1-contract, HEAD 4d240430c2ce056dc306c50e215dbb09843c6b8f;
origin/main и merge-base 141ce91fb1731cd990fcf8391550150016c73e7f.
Точный активный allowlist и удаления — [SIM2 Task §1/10](DEMO_D2_SIM2_TASK.md).
Предшествующий own WIP сохранён, foreign data/ и
docs/MARKETING_ANSWER_SCENARIOS.md не открывались.

Новый D2 protocol → direct operations; saved service task без повторного
route/kind; локальный clarification + независимая prose; B14 и T4.
Reported/correction сохраняются независимо от цены. Цена кнопки не создаёт
медицинский факт; исходный явно сообщённый факт не стирается.
Одна session schema 2, prompt 24; миграция старой local data не выполнялась.

Astra дала замечания, исправлены: seed вместо пояснения, подмена исходной
situation, потеря deferred target, конфликт pending UI и unknown brand.
Checker сначала REJECT: старые offer refs при смене темы и HTTP400 для
неопределённых details; исправлены. Focused recheck: **PASS** общего checkpoint
в проверенных границах; reviewer pytest не перезапускал, проверил код и tests.
Commercial explicit facts сохраняют provenance и не запускают второе auto promo.

Offline: combined contract/dialogue/known-action набор — 62 passed до последних
дополнений; последний расширенный dialogue набор — 41 passed.
Числа перекрываются, не складывать. Финальный domain/contracts/actions набор:
140 passed / 4 failed из-за старого raw envelope в commercial fixtures.
После перевода только helper на новый формат все четыре прошли; assertions
цен, packages, акций и dedup сохранены. Это checkpoint fixture incompatibility,
не названо baseline failure. Итого актуальных непересекающихся PASS: **185**
(41 dialogues + 140 domain/contracts/actions + 4 commercial).
Команда domain-набора: test_d2_sim2_contract.py, test_d2_sim1_known_actions_http.py,
test_d2_price_scope_selection.py, test_d2_commercial_plan.py,
test_response_plan_fact_policy.py, test_response_plan_resolver.py,
test_response_text_renderer.py; pytest -q -p no:cacheprovider, изолированные tmp.
Allowlist расширен tests/test_d2_commercial_plan.py, до редактирования объяснено.
Widget: 2 passed, 1 failed на CDP timeout Runtime.enable; browser PASS отсутствует.
Это не live-оценка понимания, не полный CI и не закрытие SIM-1/2.
SIM-3/4/5 и отдельный Cursor остаются открытыми. Live/provider/SMTP 0.
Staging пуст; новых commit/push/PR нет.


## DOC — зависимость SIM-1 от ядра SIM-2, 2026-10-01

Branch `codex/d2-stage1-contract`, HEAD `4d24043`, main/merge-base `141ce91`.
После разрешения продолжить проверены оба endpoint, producer/parser,
service-click, запись ситуации и конкретные shared-потребители. Astra
подтвердила: реализация D2-111 и прямого service-click затрагивает ядро SIM-2.
Подготовлено конкретное предложение общего checkpoint в SIM2 Task §9;
порядок Roadmap без согласования не изменён, runtime не редактировался.
Уточнены unresolved target и необязательная situation у owning блока;
обнаружена зависимость записи reported/correction от ценового applied_extent.
Полная транзитивная недостижимость legacy не заявляется.

Allowlist: SIM2 Task, SIM1 Task, Roadmap, Current Status, Ledger.
Прежний runtime/test/doc WIP сохранён. Foreign `data/` и
`docs/MARKETING_ANSWER_SCENARIOS.md` не открывались. Pytest/provider/live/SMTP 0;
staging пуст; новых commit/push/PR нет. Локальные ссылки пяти документов и
git diff --check: PASS. Независимый Checker: PASS документального уточнения
зависимости и предложения общего checkpoint; runtime не аттестован.

## DOC — технический проект SIM-1/2/3, 2026-10-01

Ветка `codex/d2-stage1-contract`, HEAD `4d24043`, main/merge-base `141ce91`.
По разрешению владельца подготовлена [карточка SIM-2](DEMO_D2_SIM2_TASK.md):
локальное уточнение одной операции, независимое объяснение, D2-111/B14,
производители и потребители, перечень удалений и общая граница памяти.
Astra участвовала read-only. Проект не разрешает runtime и не закрывает SIM-1.
Явные пробелы: разрез реализации SIM-1/2, привязка ситуации, shared consumers,
финансовая публикация соответствующего этапа. Пример неверных денег показан,
защита от них новым форматом не доказана.

Allowlist: SIM2 Task (новый), SIM1 Task, Roadmap, Current Status, Ledger.
Существующий runtime/test/doc WIP сохранён; foreign `data/` и
`docs/MARKETING_ANSWER_SCENARIOS.md` не открывались. Pytest/provider/live/SMTP 0.
Локальные ссылки пяти документов и git diff --check: PASS. Независимый
Checker: PASS технического проекта, не готовности к реализации. Его P2 о
соседних полях response/context/focus в D2CompletedTurn исправлен. Staging пуст;
новых commit/push/PR нет. Это документация, не свидетельство упрощения runtime.

## DOC — D2-111: независимый ответ сразу, уточнение цены в том же сообщении

2026-10-01, branch codex/d2-stage1-contract, HEAD 4d24043,
main/merge-base 141ce91. Владелец выбрал «Да, первый»: понятная независимая
информационная часть публикуется сразу вместе с уточнением ценовой задачи;
проверенный клик продолжает сохранённую цену. D2-111 принят, не реализован.
Следующий шаг — общий технический контракт SIM-1/SIM-2 с удалениями.
Дополнительный model call, новая память и изменение D2-080/B14 не разрешены.

Allowlist: Product Decisions, Target Contract, Acceptance, SIM1 Task,
Roadmap, Current Status, Ledger (docs/tasks). Это фиксация UX-решения;
runtime/test WIP сохранён. Pytest/provider/live/SMTP 0. Локальные ссылки и
git diff --check: PASS. Независимый Checker: PASS документальной фиксации
D2-111; runtime не перепроверялся. Staging пуст, commit/push/PR нет.
Foreign data/ и docs/MARKETING_ANSWER_SCENARIOS.md не открывались.
Ниже — история проектирования и прежней частичной реализации.

## DOC WIP — согласован совместный проект service clarification SIM-1/SIM-2

2026-10-01, та же ветка codex/d2-stage1-contract и HEAD 4d24043,
main/merge-base 141ce91. Владелец согласился проектировать компактную задачу
совместно с SIM-2, без универсальной разметки всех частей разговора.
Это согласие на направление проектирования, не новый runtime PASS/GO.

В [карточке SIM-1](DEMO_D2_SIM1_TASK.md) предложена структурная связь
выбора с конкретной операцией/задачей пояснения в существующем owner;
отдельный глобальный target-ID список и полный старый envelope не обязательны.
Предыдущая рекомендация обязательного нового поля уточнена после Astra-разбора.
Добавлены примеры двух цен и информационного уточнения, владельцы по Contract §3,
удаляемые массивы/повторная классификация/post-model override.
Момент независимого информационного ответа оставлен открытым. Две цены
сохраняют D2-080/B14: первая primary, вторая явно deferred. Связь кнопки
с primary задачей не угадывают заново по позиции в разрозненных массивах.

Allowlist: SIM1_TASK, DELIVERY_ROADMAP, CURRENT_STATUS, CHECKPOINT_LEDGER
в docs/tasks. Предшествующий runtime/doc WIP сохранён. В этом дополнении
код и тесты не менялись; pytest/provider/live/SMTP 0. Локальные Markdown-ссылки
и git diff --check: PASS. Независимый документальный Checker: PASS после
уточнения сохранения D2-080/B14; runtime повторно не аттестован.
Staging пуст, commit/push/PR нет.
Foreign data/ и docs/MARKETING_ANSWER_SCENARIOS.md не открывались.
Ниже — evidence предшествующей частичной реализации, не её повторная аттестация.

## WIP — SIM-1 runtime: volume/document; service требует решения владельца

2026-10-01, baseline `4d24043`, branch `codex/d2-stage1-contract`,
main/merge-base `141ce91`. Реализация разрешена владельцем. Volume получает
typed price task до provider (0 calls), document — готовую section task и
только пояснение через существующий decoder; post-model volume repair и
document source rebinding удалены. D2-110: три кнопки, few_teeth free text
сохранён. Details сохраняет прежний прямой путь. SIM-1 НЕ закрыт.

Astra выявила отсутствующую связь service clarification → исходные request IDs.
Сохранение полного understanding само по себе её не создаёт. Черновой service
рефакторинг снят; baseline service-path остаётся до решения владельца.
Нельзя угадать адресата уточнения по пустому service_id/topic/порядку частей.
Scope и вопрос приведены в [карточке](DEMO_D2_SIM1_TASK.md).

Baseline: 130 PASS / 4 FAIL (3 прежних snapshot expectations, widget CDP timeout).
Новые SIM-1 cases: 19 PASS; HTTP/lead/terminal/medical: 30 PASS.
Document/widget/details: 54 PASS / 2 CDP timeout; browser не подтверждён.
Старые дополнительные failures (B12/continuation/prompt v19) воспроизведены
на чистом git archive HEAD. Числа прогонов не суммируются, детали в карточке.
Независимый Checker PASS только частичного checkpoint по коду/assertions,
без повторного pytest. Cursor review runtime ещё не получен.
Live/provider/SMTP 0; staging пуст, runtime commit/push не выполнены.
Foreign `data/`, `docs/MARKETING_ANSWER_SCENARIOS.md` не открывались.
Следующие Draft разделы — история подготовки, не текущий статус runtime.

## Draft — SIM-1: подготовка карточки известного действия

Baseline `4d24043`, branch `codex/d2-stage1-contract`, main/merge-base `141ce91`.
Предшествующий WIP SIM-0/D2-110 сохранён; foreign data/маркетинговая памятка
не открываются. Документальный allowlist: `DEMO_D2_SIM1_TASK.md` и Ledger.
Owner instruction — продолжить Roadmap. Read-only Astra подтвердила:
volume task уже достаточен, details уже обходят модель; service clarify
теряет связи исходных частей, document action ещё зависит от модельного
маршрута. Карточка требует замены producer/consumer пояснения и существующей
записи уточнения, а не override после полной повторной классификации.
ACCEPTANCE — S01/S06 и D2-110 как план доказательств; runtime PASS отсутствует.
LEGACY IMPACT/D2 ROUTE — документальный план прежнего общего входа.
Карточка передаётся независимому Checker; код/тесты/live/provider/SMTP 0,
staging пуст, commit/push не выполнены. FUTURE SCOPE — реализация SIM-1,
продуктовые детали SIM-0 и остальные этапы.

## Draft — SIM-0: подготовка состава обзоров

Дополнение D2-110: владелец согласовал три кнопки объёма и сохранение
нескольких зубов в свободной речи. Обновлены Roadmap, Contract, Acceptance,
Decisions и карточка SIM-0; allowlist дополнения — эти пять файлов и Ledger.
Удаление UI/его отдельного кода запланировано в SIM-1, не выполнено в runtime.
Состав offers не объявлен принятым. Проверка — ссылки/diff и независимый
документальный Checker; тесты/provider 0. Baseline остаётся `4d24043`.

Начало реализации Roadmap по прямому запросу владельца; baseline `4d24043`,
branch `codex/d2-stage1-contract`, main/merge-base `141ce91`.
На старте tracked/staging чисты, foreign `data/` и маркетинговая памятка
сохранены. Allowlist: `DEMO_D2_SIM0_TASK.md` и этот Ledger в `docs/tasks/`.
Тип — документация/подготовка решения; ACCEPTANCE — S04/D2-107 на уровне
инвентаризации данных. Проверены JSON direction/offer demo; предложение
включений и исключений отделено от решения владельца. Продуктовый состав
не утверждён, SIM-0 не закрыт. D2 ROUTE/LEGACY IMPACT: runtime не меняется.
Тесты/бот/provider/live/SMTP: 0. Проверка ссылок/diff и независимый Checker
подготовки — перед передачей. Commit/push не выполнялись, staging пуст.
FUTURE SCOPE: решение состава, SIM-1 карточка и дальнейшие этапы.

## Draft — 2026-10-01: D2-SIM-DOC, актуальная сверка

Дополнение по запросу владельца после первого документального PASS: SIM-1
исключает повторную классификацию; SIM-2 сокращает контракт и не требует
дробления связной речи; SIM-2/3 проектируются совместно через существующий
completion/projection, объём связан с услугой; SIM-4 требует механизма,
поведения неподтверждённой части и оценки сложности; каждый SIM доказывает
свой результат до закрытия. Согласованы Roadmap/Contract/Acceptance и инструкции
исполнителя/Checker; конкретный scope итерации — в текущей карточке.
Baseline неизменён `0691217`; до этой итерации 15 документов уже изменены,
staging пуст. Старый PASS не заявляется проверкой дополнения; независимый
review дополнения выполняется отдельно, внешний Cursor ещё впереди.

Документальный checkpoint по верхнему разделу Audit Followup Task (15 путей).
Baseline `0691217b888b92b49ba2c288452ed8a053f31206`, active branch
`codex/d2-stage1-contract`; fresh fetch origin подтвердил tracking 0/0,
main `141ce91fb1731cd990fcf8391550150016c73e7f`, ahead/behind 101/0.
AF-1a `4e435ce` и AF-1b `0691217` опубликованы; это не новая аттестация runtime.
Девять ранее изменённых правил сохранены в общем diff; staging пуст,
foreign `data/` и маркетинговая памятка не затронуты, worktrees не менялись.

ACCEPTANCE: правила в начале Roadmap; D2-107–109, новый C03/S01–S06;
текущий статус и порядок SIM-0–5/REC-5, явные границы нерешённых деталей.
Astra read-only: подтверждены конфликт старого финансового допуска,
необходимость утверждённых обзорных offers и память контактного отвлечения.
Её рекомендация не является GO. D2 ROUTE/LEGACY IMPACT: только документация;
удаление runtime-зависимостей не заявляется. Tests/live/provider/SMTP: 0;
проверки diff/ссылок и независимый Checker — перед передачей. Cursor pending;
commit/push новых документов не выполнялись. FUTURE SCOPE — runtime карточки.
Исторические Draft ниже читаются на их дату, не как текущее разрешение.

## Draft — 2026-10-01: D2-ARCH-RULES

Baseline HEAD/local origin `0691217b888b92b49ba2c288452ed8a053f31206`,
ветка `codex/d2-stage1-contract`, Git root `C:\Cursor Projects\artgents-bot-active`;
локальные `origin/main`/merge-base `141ce91fb1731cd990fcf8391550150016c73e7f`.
Tracked diff/staging до работы пусты; foreign untracked `data/` и
`docs/MARKETING_ANSWER_SCENARIOS.md` сохранены. Тип изменения — документация.
Owner GO: закрепить согласованные правила упрощения и строгую проверку Cursor.
Точный write allowlist: `AGENTS.md`, `docs/WORKFLOW_CHECKER.md`,
`docs/tasks/DEMO_D2_TARGET_CONTRACT.md`, `docs/tasks/DEMO_D2_EXECUTION_LOCK.md`,
`docs/tasks/DEMO_D2_CODEX_EXECUTOR_PROMPT.md`,
`docs/tasks/DEMO_D2_CURSOR_CHECKER_PROMPT.md`, этот Ledger,
`.cursor/rules/00-guardrails.mdc`, `.cursor/agents/checker.md`.
Allowlist расширен с объяснением до правок двух действующих инструкций Cursor:
alwaysApply guardrails подключает критерий, агент Checker устраняет task-only
ограничение. Схема ответственности в них не копируется.

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-ARCH-RULES | **ACCEPTANCE:** единая схема ответственности в Target Contract §3; архитектурное изменение требует «до → после → удаляется», единственного владельца и доказательств по вызываемому коду и целому диалогу. Bug fix и документация отделены от runtime-упрощения. Checker/Cursor обязаны отклонять сохранённую или перенесённую заявленную зависимость; узкая карточка/FUTURE SCOPE не обходят критерий. **D2 ROUTE / LEGACY IMPACT:** документальные правила; runtime не менялся, удаление его зависимостей не заявляется. **OWNER DECISION:** явный запрос владельца 2026-10-01; схема не требует повторного согласования на каждой малой правке. **Evidence:** сверены действующие AGENTS, Lock, контракт, процесс исполнителя и Cursor prompt; приоритет task-first в общем Checker приведён к Lock §6. Новых документов и review-кругов нет. **Test isolation:** документация; pytest/бот/provider/live/SMTP 0. **FUTURE SCOPE:** реализации по обновлённым правилам после согласования конкретных карточек; этот checkpoint не разрешает runtime-правки и не закрывает AF-1a/1c/2 или REC-5. | Draft до независимого Checker и внешнего Cursor review; проверки ссылок и diff выполняются перед review. Staging пуст; commit/push не выполнялись. |

## Draft — 2026-09-30: реализация D2-AF-1b

Baseline HEAD/local origin `4e435ce8006cc2df07930a40d058f278469a99f6`,
ветка `codex/d2-stage1-contract`, Git root `C:\Cursor Projects\artgents-bot-active`;
локальный `origin/main`/merge-base `141ce91fb1731cd990fcf8391550150016c73e7f`.
Implementation GO и точный 11-file allowlist — в
[карточке AF-1b](DEMO_D2_AF1B_CONTACTS_TASK.md). Foreign `data/` и
`docs/MARKETING_ANSWER_SCENARIOS.md` не открывались и не stage.

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-AF-1b-IMPL | **ACCEPTANCE:** AF-02, узкая B09/D2-095/C02: конкретный typed contact field даёт точное значение текущего tenant, `contacts` — телефон+адрес+часы; absent parking — согласованный честный пробел, без телефона вместо неё. Несколько полей и независимая prose сохраняются. Typed `contact_branch_id` выбирает только названный филиал; без него обе адресные строки снабжены названиями, произвольной кнопки звонка нет. **D2 ROUTE / LEGACY IMPACT:** один `/ask`/`/ask/stream` D1R parser/provider → tenant facts → common materializer/frozen response/store; второго selector/parser/state/fallback нет. **OWNER DECISION:** после принятой карточки дан отдельный GO на AF-1b, но не на live/commit/push/merge/deploy. **Evidence:** новый HTTP набор 19 passed; соседний контактный/branch/mixed 19 passed/80 deselected; baseline и повтор тех же соседних сценариев 9 passed/те же 4 failed/9 deselected. Fake provider, temp DB/tenant/log, network blocked; provider/live/SMTP 0. **FUTURE SCOPE:** живое качество выбора полей, AF-1c/2 и REC-5. | Draft после Checker REJECT P1: пустой contact_fields теперь отклоняется; focused recheck и Cursor review впереди. Staging пуст, commit/push не выполнялись. |

## Draft — 2026-09-30: карточка D2-AF-1b после AF-1a

Git root `C:\Cursor Projects\artgents-bot-active`, ветка
`codex/d2-stage1-contract`, baseline HEAD/local origin
`4e435ce8006cc2df07930a40d058f278469a99f6`; локальный `origin/main` и
merge-base `141ce91fb1731cd990fcf8391550150016c73e7f`.
Перед правками tracked diff/staging пусты; foreign untracked `data/` и
`docs/MARKETING_ANSWER_SCENARIOS.md` оставлены без изменений. Write allowlist:
эта Draft-строка и [карточка AF-1b](DEMO_D2_AF1B_CONTACTS_TASK.md).

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-AF-1b-DOC | **ACCEPTANCE:** узкая B09/D2-095/C02 и AF-02; конкретный вопрос получает соответствующий точный tenant contact, несколько вопросов сохраняются, общий `contacts` — телефон+адрес+часы, WhatsApp/парковка по запросу; контакт не стирает независимую prose. **D2 ROUTE / LEGACY IMPACT:** только план для одного D2 provider/parser/materializer/store, без второго semantic selector/fallback. **OWNER DECISION:** согласованы оба адреса с названиями филиалов на общий вопрос, один адрес при названном филиале и честное «нет информации о парковке» при отсутствии этих сведений; другой контакт не подменяет отсутствующее поле. Implementation GO отсутствует. **Evidence:** read-only сверка AF-02, текущего `contacts → phone`/phone fallback, существующих typed fields и mixed contact+content; реализация, offline tests и live не запускались. **FUTURE SCOPE:** AF-1c/2, REC-5 и live quality. | Draft до focused Checker recheck и Cursor; runtime, commit/push, merge/deploy не разрешены. |

## Draft — 2026-09-30: реализация D2-AF-1a

Владелец уточнил текущий UI: после выбора услуги сразу цена, без кнопок
объёма; плановая цепочка «услуга → объём» неприменима к этому tenant.

Git root `C:\Cursor Projects\artgents-bot-active`, ветка
`codex/d2-stage1-contract`, baseline HEAD/local origin
`8cea81125cfc9ad8898b0e4ab43a6dc42bf15331`; `origin/main` и
merge-base `141ce91fb1731cd990fcf8391550150016c73e7f`.
Перед правками staging/tracked diff пусты. Foreign untracked `data/` и
`docs/MARKETING_ANSWER_SCENARIOS.md` не открывались и не stage.
Точный implementation allowlist и решения владельца — в
[карточке AF-1a](DEMO_D2_AF1A_PRICE_TASK_TASK.md).
После изменения scope отдельный набор context/scope/continuation дал
87 passed / те же 3 baseline failed из continuation; новых отказов нет.

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-AF-1a-IMPL | **ACCEPTANCE:** проверенный volume choice продолжает frozen price task с topic/service/brand; цена берётся из tenant snapshot, при отсутствии подходящего offer — честный пробел. Неверный `content/other` не убирает цену; пригодная prose сохраняется. Кнопка не создаёт личную `situation_state`: выбранный объём хранится в последнем frozen completion и TTL-gated projection следующего хода как контекст разговора, без второй памяти и угадывания по label/ref. **D2 ROUTE / LEGACY IMPACT:** один `/ask`/`/ask/stream` provider/parser/materializer/store; нового semantic selector, fallback или owner нет. **OWNER DECISION:** после read-only Astra владелец отменил self/other/hypothesis-ветвление AF-1a и согласовал расширение allowlist для typed recent scope; live/commit/push/merge/deploy не разрешены. **Evidence:** AF-1a HTTP 19 passed: JSON/SSE, бренд, четыре объёма, wrong kind, цена-gap, следующий provider input, TTL, смена темы, replay/conflict. Соседний набор 53 passed / 1 browser deselected / 1 старый failed: `test_d2_live_provider_offline.py` ожидает prompt v19, хотя HEAD уже v23. Pre-edit baseline 33 passed / 3 failed; после предыдущей правки тот же набор 33 passed / те же 3 failed. Browser harness до этого дважды дал `CDP timeout: Runtime.enable` до DOM assertions; это не browser PASS. Offline fixtures: temporary tenant/SQLite/log, сеть блокирована, provider/live/SMTP 0. **FUTURE SCOPE:** AF-1b/1c/2, полная A/B/C, REC-5 и разрешённое live-качество. | Draft до нового независимого Checker и Cursor review изменённого scope. Staging пуст; commit/push не выполнялись. После PASS reviewed diff не дописывать. |

## Draft — 2026-09-30: карточка D2-AF-1a после D2-AUDIT-PLAN

Git root `C:\Cursor Projects\artgents-bot-active`, ветка
`codex/d2-stage1-contract`, HEAD и локальная origin-ветка до правок
`fb81a9af2e1c4e654d9040013c3c6f528d89b5d4`; `origin/main` и merge-base
`141ce91fb1731cd990fcf8391550150016c73e7f`. Staging/tracked diff до
правок пусты; foreign `data/` и `docs/MARKETING_ANSWER_SCENARIOS.md`
сохранены. Write allowlist — эта строка и
[карточка AF-1a](DEMO_D2_AF1A_PRICE_TASK_TASK.md). Локальный `origin/*`
прочитан без нового fetch/remote-запроса. Историческая Draft
D2-AUDIT-PLAN ниже относится к прежнему `f4a08ea`, не к сегодняшнему HEAD.

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-AF-1a-DOC | **ACCEPTANCE:** подготовлен узкий план D2-094/A14 по AF-01, без закрытия A/B/C. **D2 ROUTE / LEGACY IMPACT:** только read-only сверка проверки UI ref, volume refs и существующего price path; runtime/legacy не менялись. **OWNER DECISION:** владелец разрешил подготовить карточку; implementation GO и точный code allowlist впереди. **Evidence:** прежний log prefix `a07cab18` дал описание без цены; статически на `fb81a9a` service-clarify binding не распространяется на volume-click; удачные fake-provider price tests не покрывают неверный kind. Это не новое воспроизведение живой моделью. **Test isolation:** документация, без pytest/бота/БД/сырых диалогов; provider/live/SMTP 0. **FUTURE SCOPE:** offline baseline, отдельный implementation GO, Checker/Cursor, AF-1b/1c/2 и REC-5. | Draft до независимого Checker и Cursor review карточки. Staging пуст; commit/push не выполнялись. После PASS reviewed diff не дописывать. |

## Draft — 2026-09-29: D2-AUDIT-PLAN после сохранённого REC-4-P2

Git root `C:\Cursor Projects\artgents-bot-active`, ветка
`codex/d2-stage1-contract`, baseline HEAD/local origin/GitHub branch
`f4a08ea75b284cb51291fd7fe6ca64d842d8e2d0`; main/merge-base
`141ce91fb1731cd990fcf8391550150016c73e7f`. GitHub проверен read-only
`ls-remote` в этой сессии; до правок tracked/staging пусты. Write allowlist —
шесть документов [карточки](DEMO_D2_AUDIT_FOLLOWUP_TASK.md). Foreign `data/`
и `docs/MARKETING_ANSWER_SCENARIOS.md` сохранены, не stage. Старая папка,
worktree и backup не менялись. БД/сырые логи не открывались в doc-checkpoint.

Предыдущая Draft P2 ниже относится к `abcb8ee` до review. Позже владелец
передал Cursor PASS: P2 HTTP 20 passed / 1 browser deselected; отдельный
browser 1 passed (26.76 s), четыре назначенных файла 65 passed / 15 прежних
failed; широкий адресный набор 118 passed / 1 deselected. После независимых
Checker/Cursor и разрешения сохранён `f4a08ea`. Это evidence прежних review,
не новый тестовый прогон; авторский CDP timeout не переписывается, visual
360/768, полный REC-5 и live-качество не объявляются закрытыми.

Процессное исключение `6c4a963`, ранее принятое владельцем: по передаче
статусные строки Full Audit Task/Ledger менялись после Cursor PASS, runtime
после review не менялся. История не исправляется задним числом; запрет
после-review правок остаётся. Это не выдача нового PASS тому checkpoint.

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-AUDIT-PLAN | **ACCEPTANCE:** актуальные указатели и links, точный Git baseline, разделение утверждённого поведения / audit findings / proposed scope; A/B/C не закрываются. **D2 ROUTE / LEGACY IMPACT:** без runtime изменений; статический вход D2 и старые файлы сверены, полного C08 proof здесь нет. **OWNER DECISION:** разрешена документальная сверка; proposed порядок AF-1a/b/c → AF-2 → общая приёмка, CTA/оформление/authored и остальные новые правила не утверждены. **Evidence:** read-only GitHub refs и ancestry; stale P2 статусы исправлены, исторические строки сохранены; Astra сверила архитектурные границы и приоритет D2-092/094/095/099/102/105/106. Marketing памятка прочитана для сверки, не изменена: её cap 3 и запрет detail UI не authority против поздних D2-100/102. **Test isolation:** только документация, pytest/бот/provider/live/SMTP 0; проверка local links и diff до review, без БД/сырых payload. **FUTURE SCOPE:** принятие проекта порядка, отдельные implementation cards/GO, REC-5 и разрешённое live-качество. | Draft до независимого Checker и Cursor. Staging пуст; commit/push этого checkpoint не выполнялись. После PASS Ledger не дописывать. |

## Draft — 2026-09-29: реализация REC-4-P2

Git root `C:\Cursor Projects\artgents-bot-active`, ветка
`codex/d2-stage1-contract`, baseline HEAD и origin branch
`abcb8ee2bad72ef5d5be689cb21964e63af8dfbc`; `origin/main` и merge-base
`141ce91fb1731cd990fcf8391550150016c73e7f`. До правок tracked diff и
staging пусты; чужие untracked `data/` и
`docs/MARKETING_ANSWER_SCENARIOS.md` сохранены. Предыдущая Draft карточки
ниже — её исторический снимок до Checker/Cursor PASS и commit/push `abcb8ee`.

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-REC-4-P2-IMPL | **ACCEPTANCE:** адресный A16/B19, затронутые A02/A05/B12/B14/B18/C01/C03–C05/C07/C09/C10, не весь REC-5. **D2 ROUTE:** `/ask`/`/ask/stream` → один parser для свободного вопроса или проверенный 0-call detail click → captured tenant offers → frozen detail block/action map в существующем плане → renderer/UI → store/replay. `price_detail_ids` 0–2 в существующем профиле, demo `classic` с обеими кнопками только при полных данных всех показанных offers; прямой вопрос независимо от настройки читает опубликованные данные даже при выключенном followup и называет реальные пробелы. Состав и платежи из captured offer, одинаковое общее один раз, разные графики отдельно; RUB формат P1. Lead pause вытесняет detail-кнопки. Astra нашла три P1: старый набор offers после смены услуги, потерю независимой prose при неоднозначной detail и потерю exact contact рядом с detail. Checker добавил три границы: переход к другой услуге внутри того же multipart, разные явные услуги в price+detail и неоднозначный короткий вопрос после mixed ответа; исправлены проверкой текущих refs, локальной frozen gap-частью и общим multipart route. **LEGACY IMPACT:** второй parser/model call, semantic regex, старый price_aspect runtime, новый state owner и fallback не добавлялись. **OWNER DECISION:** D2-102, `classic` и code GO даны владельцем; commit/push отдельно. **Test isolation/evidence:** fake provider, временные tenant/DB/log, сеть заблокирована; baseline назначенных четырёх файлов до правок 59 passed / 15 failed, после правок 65 passed / те же 15 failed (6 новых schema-тестов). Адресный P2 HTTP JSON/SSE 20 passed / 1 browser deselected; P2 + lead + multipart + price-scope 76 passed / 1 browser deselected. Отдельный browser harness 1 failed из-за `CDP timeout: Runtime.enable` до проверки widget assertions; локальный Chrome открывает WebSocket, но не отвечает на команду, виджет не объявлен проверенным. Provider/live/SMTP 0, бот не запускался. **FUTURE SCOPE:** независимый Checker, Cursor, browser/widget proof, REC-5 и отдельно разрешённое качество модели/live. | Draft до независимого Checker и Cursor review реализации. Staging пуст; commit/push не выполнялись. После PASS Ledger не дописывать. |

## Draft — 2026-09-29: подготовка карточки REC-4-P2

Git root `C:\Cursor Projects\artgents-bot-active`, ветка
`codex/d2-stage1-contract`, baseline HEAD и origin branch
`71d746793ffbd3ef796ae81cd6d0eae09d8cfd69`; `origin/main` и merge-base
`141ce91fb1731cd990fcf8391550150016c73e7f`. До правок tracked diff и
staging пусты. Чужие untracked `data/` и
`docs/MARKETING_ANSWER_SCENARIOS.md` сохранены. Нижняя Draft реализации
D2-LEAD-INTERRUPT — снимок до её Checker/Cursor PASS и commit/push `71d7467`,
не текущий Git-status.

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-REC-4-P2-DOC | **ACCEPTANCE:** план A16/B19 и затронутых A02/A05/B12/B14/B18/C01/C03–C05/C07/C09/C10; runtime P2 ещё не проверен. **D2 ROUTE:** документально сверены действующие `/ask`/`/ask/stream`, tenant snapshot, один parser/frozen plan/store/replay и typed UI, без изменения runtime. **LEGACY IMPACT:** старый price_aspect selector, semantic regex и fallback не разрешаются. **OWNER DECISION:** D2-102 и варианты нескольких/частичных offers утверждены; владелец выбрал обе кнопки у `classic` при полном наборе данных, остальные услуги выключены; GO на код впереди. **Test isolation/evidence:** read-only Git/код/документы и demo commercial/offer inventory: три `classic.one_tooth.*` имеют includes/stages/followups, runtime captured set ещё не доказан; pytest, бот, provider/live/SMTP 0. **FUTURE SCOPE:** P2 implementation, Checker/Cursor, REC-5 и отдельно разрешённое live-качество. | Draft до независимого Checker и Cursor review карточки. Staging/commit/push не выполнялись; после PASS Ledger не дописывать. |

## Draft — 2026-09-29: реализация D2-LEAD-INTERRUPT

Git root `C:\Cursor Projects\artgents-bot-active`, ветка
`codex/d2-stage1-contract`, baseline HEAD и локальный origin branch
`43c0aba362403ac144e88809e4f8ff5a81e6bc2a`; `origin/main` и merge-base
`141ce91fb1731cd990fcf8391550150016c73e7f`. До правок tracked diff и
staging пусты; чужие untracked `data/` и
`docs/MARKETING_ANSWER_SCENARIOS.md` сохранены. Allowlist и решение владельца —
[карточка](DEMO_D2_LEAD_INTERRUPT_TASK.md). Нижняя Draft карточки — снимок до
её Checker/Cursor PASS и commit/push `43c0aba`, не текущий Git-status.

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-LEAD-INTERRUPT-IMPL | **ACCEPTANCE:** A12/B11/C05–C07 проверяются на D2 HTTP; это не полный REC-5. **D2 ROUTE:** current tenant/revision `lead:pending:answer` берёт сохранённый вопрос только у bound lead owner, существующий privacy scrub идёт до единственного provider/parser, обычный D2 сохраняет ответ и typed resume/cancel в одном completion. После D2 commit lead owner одним row write переходит в paused; replay/следующий запрос согласует post-commit gap только для последнего completion и той же версии pending-вопроса. Старый replay не стирает новый pending. Resume восстанавливает исходный name/phone без provider, cancel чистит ПД. В paused ответах CTA скрыта, выход к записи остаётся в frozen UI. **LEGACY IMPACT:** старый answer→resume runtime не вызывался; semantic regex/второй parser/state owner не добавлены. **OWNER DECISION:** ответ + явный resume и code GO даны владельцем после Cursor PASS карточки; D2-106. **Test isolation/evidence:** fake provider, временные tenant/SQLite/log, сеть заблокирована; адресный HTTP JSON/SSE 15 passed, соседние lead/HTTP 18 passed, документный клик 16 passed. Provider/live/SMTP 0. Рабочие БД/логи не открывались. **FUTURE SCOPE:** общий hard-crash `inflight` без lease/recovery остаётся отдельным ограничением D2; REC-4-P2 и REC-5 впереди. | Draft до независимого Checker и Cursor review реализации. Staging пуст; commit/push не выполнялись. После PASS Ledger не дописывать. |

## Draft — 2026-09-28: карточка D2-LEAD-INTERRUPT

Папка/Git root `C:\Cursor Projects\artgents-bot-active`, ветка
`codex/d2-stage1-contract`, baseline HEAD и локальный origin branch
`b39ed36cdbc57f608da1c199cf45ce938e70b6dc`; `origin/main` и merge-base
`141ce91fb1731cd990fcf8391550150016c73e7f`. До правок tracked diff и
staging пусты. Чужие untracked `data/` и
`docs/MARKETING_ANSWER_SCENARIOS.md` сохранены. Точный документальный
allowlist — [карточка](DEMO_D2_LEAD_INTERRUPT_TASK.md). Нижняя Draft строка
указателя — снимок до его Checker/Cursor PASS и сохранения в `b39ed36`;
Ledger после её review не переписывали.

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-LEAD-INTERRUPT-DOC | **ACCEPTANCE:** план A12/B11/C05–C07; runtime пока не проверен. **D2 ROUTE:** read-only разобраны D2 pre-provider lead bridge, pending/resume, обычный D2, UI revision, HTTP replay и существующая очистка ПД. **LEGACY IMPACT:** старый answer→resume путь только историческая сверка, не fallback. **OWNER DECISION:** требуется выбор поведения после «Ответить» и отдельный GO на код по Execution Lock §4. Astra read-only рекомендовала ответ + typed resume к прежнему name/phone. **Test isolation/evidence:** widget trace `40820dcb` → `96b02f07`; исходный D2 bridge стирает pending и повторяет слот, provider attempts 0. Сырые сообщения и БД не перенесены. Только чтение кода/документов, pytest/бот/live/provider/SMTP 0. **FUTURE SCOPE:** отдельный implementation preflight и allowlist, offline HTTP/PII/replay tests, Checker/Cursor, REC-4-P2, REC-5. | Draft до независимого Checker и Cursor review карточки. Staging пуст; commit/push не выполнялись. После PASS Ledger не дописывать. |

## Draft — 2026-09-28: указатель текущего состояния D2

Папка/Git root `C:\Cursor Projects\artgents-bot-active`, ветка
`codex/d2-stage1-contract`, baseline HEAD и локальный origin branch
`e246f1e7132596e20b8f81db7bc911855678ad8e`; `origin/main` и merge-base
`141ce91fb1731cd990fcf8391550150016c73e7f`. До правок tracked diff и
staging пусты. Чужие untracked `data/` и
`docs/MARKETING_ANSWER_SCENARIOS.md` сохраняются. Точный allowlist и владелец
решения — [карточка](DEMO_D2_CURRENT_STATUS_INDEX_TASK.md). Предыдущая Draft
D2-DOC-CLICK ниже — историческая строка до его Checker/Cursor PASS и commit/push
`e246f1e`, не текущий Git-status; после review её не переписывали.

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-CURRENT-STATUS | **ACCEPTANCE:** корректный указатель и ссылки, без закрытия A/B/C. **D2 ROUTE / LEGACY IMPACT:** код и маршруты не меняются. **OWNER DECISION:** владелец согласовал отдельный порядок в документах; lead-исправление требует отдельной карточки и решения. **Test isolation/evidence:** read-only Git/документы и полный локальный журнал; `40820dcb` фиксирует pending choice, `96b02f07` — клик `lead:pending:answer`, запрос имени и 0 provider calls. `core/d2_lead_bridge.py` явно реализует возврат к слоту. В новый checkpoint не включены сырые сообщения, PII или БД. Документальные ссылки и diff проверить до Checker; runtime pytest не требуется. Provider/live/SMTP 0, бот не запускался. **FUTURE SCOPE:** отдельная карточка lead-прерывания и исправление после согласования, REC-4-P2 после нового preflight/GO, REC-5 и live-качество. | Draft до независимого Checker и Cursor review. Staging пуст, commit/push не выполнялись; после PASS Ledger не дописывать. |

## Draft — 2026-09-28: D2-DOC-CLICK перед возвратом к REC-4-P2

Папка/Git root `C:\Cursor Projects\artgents-bot-active`, ветка
`codex/d2-stage1-contract`; baseline HEAD и локальный origin branch
`a930ed70df9d2d709cc36b9076be55659485c582`. `origin/main` и merge-base
`141ce91fb1731cd990fcf8391550150016c73e7f`. Это принятый Checker/Cursor и
сохранённый с разрешения владельца REC-4-P1; его нижняя Draft-строка — снимок
до review, не нынешний Git-status. До этой коррекции tracked/staging пусты.
Чужие untracked `data/` и `docs/MARKETING_ANSWER_SCENARIOS.md` сохранены;
БД не открывались. Точный allowlist —
[D2-DOC-CLICK](DEMO_D2_DOCUMENT_CLICK_TASK.md). Старые строки не переписываются.

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-DOC-CLICK | **ACCEPTANCE:** срез A03/B12/B15/B20/C01, не полный REC-5. Проверенный документный action с section_title из captured snapshot поступает в единственный provider input/prompt до генерации; текущий вопрос по клику отделён от истории, q остаётся пустым. В production parser omitted mode для непустого content/other становится model_prose; explicit authored/invalid/null и empty other сохраняют прежние правила. **D2 ROUTE:** JSON/SSE → текущий проверенный action → provider prompt → production parser → прежние materializer/source/CTA → store/history/replay. **LEGACY IMPACT:** второго parser/call, semantic regex, замены prose абзацем MD, нового state owner или legacy fallback нет. **OWNER DECISION:** GO на обе коррекции и документы перед возвратом к ценам; Astra read-only подтвердила эту ограниченную архитектуру. **Test isolation/evidence:** fake provider, временные DB/tenant/logs, запрет сети; BOT_LOG_DIR до imports. Чистый baseline до правок: R1/REC2/envelope-correction 54 passed / 1 failed (исторический other). Те же три файла плюс новый HTTP-набор после правок: 71 passed; прежний other тест проходит без изменения. Соседние scope/lead/replay/B14/fullcontext/offtopic/free-dialogue: 20 passed / 3 failed. Все три воспроизведены теми же assertions в чистом tracked архиве a930ed7 во временной папке: test_offtopic_polite_refuse_from_ui_yaml — patient_text_required; test_greeting_prose_is_not_replaced_by_guided_menu — d2_experiment_content_not_resolved (fixture явно задаёт authored); test_available_contact_leaves_an_unavailable_information_part_degraded — нет INFO_GAP. Тесты не ослаблены. Первые два запуска baseline-архива не собрали tests из-за отсутствия локального CHAT_API_KEY; после фиктивного offline key сравнение состоялось, реальные credentials не копировались. Provider/live/SMTP 0, бот не запускался; browser harness не запускался. **FUTURE SCOPE:** качество настоящей генерации и отсутствие смысловых повторов проверять отдельно с GO/бюджетом; fake ответы доказывают передачу задания и сохранение prose, а не качество модели. REC-4-P2 — после принятого checkpoint и отдельного GO. | Draft до независимого Checker и отдельного Cursor review. Staging пуст, commit/push не выполнены и требуют отдельного разрешения. После PASS Ledger не дописывать. |

## Draft — 2026-09-28: REC-4-P1 компактное оформление цен

Рабочая папка/Git root `C:\Cursor Projects\artgents-bot-active`, ветка
`codex/d2-stage1-contract`; baseline HEAD и локальный origin branch
`04657f10e6e01162e9513a602424dbcccb594ac2` (после Checker/Cursor PASS,
разрешённого commit/push документального checkpoint REC-4-P). `origin/main`
и merge-base `141ce91fb1731cd990fcf8391550150016c73e7f`. До P1 tracked
diff/staging чисты; чужие untracked `data/` и
`docs/MARKETING_ANSWER_SCENARIOS.md` не менялись. Git предупреждал о
недоступных global ignore и `.pytest_cache/`. Точный будущий P1 allowlist —
§4 [карточки REC-4-P](DEMO_D2_PRICE_PRESENTATION_DETAILS_TASK.md); новый
`tests/test_d2_price_presentation_http.py` входит в него.

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-REC-4-P1 | **ACCEPTANCE:** срез A02/A05, B18 и регрессий B12/B14, C03–C05/C07/C09/C10; не полный A16/B19/REC-5. У точной услуги проверенные frozen service/variant/price поля дают короткий список, общие точные условия один раз, частные остаются у offer; RUB в формате `20 000 ₽` с NBSP. У overview остаётся один authored факт зависимости от протокола/объёма и choices. `patient_text` для ANSWER с реально разрешённой ценой — 0–1 optional live intro из одного model call, перед ценой; независимые content parts в порядке requests. Ordinary history хранит всю живую prose, не копирует code-owned цену; replay сохраняет итоговый ответ. **D2 ROUTE:** офлайн `/ask`/`/ask/stream` → единый production envelope/parser → captured tenant snapshot → materializer/frozen plan → renderer/UI → store/replay; browser harness с fake D2 payloads и штатным CSS. **LEGACY IMPACT:** второго model call/parser, semantic regex, старого assembler/fallback или нового state owner нет. **OWNER DECISION:** владелец подтвердил Cursor PASS карточки, отдельно разрешил doc commit/push и дал GO на P1; решения D2-101/103 и границы D2-092/B14 действуют. Astra ранее read-only проверила reuse existing `patient_text` и history boundary. **Test isolation/evidence:** на чистом baseline назначенный набор 28 passed; после P1 адресные пять файлов 39 passed, соседние request order/memory/UI 10 passed, B14 оба порядка 3 passed, headless Chrome widget 1 passed, `node --check`/Python compile/diff check clean. Визуально осмотрены временные скриншоты 360/768 px: список/переносы без горизонтального overflow. Первый baseline pytest без явного basetemp дал 9 setup errors из-за прав на стандартную temp-папку; с отдельным temp 28 passed. Исторический `test_price_content_price_preserves_independent_content_and_request_order` по-прежнему падает: отсутствует «Материал терапии.» (0 вместо 1); тест не менялся и не скрыт; прежнее evidence REC-4 уже сравнивало этот ID с чистым HEAD, на чистом `04657f1` отдельно не воспроизводили. Fake provider, временные tenant/DB/log/Chrome profile, локальная сеть браузера, provider/live/SMTP 0. **FUTURE SCOPE:** P2 exact details/buttons только после принятого P1 и отдельного GO, полный A16/B19/REC-5, старый multipart/content разрыв, живость optional intro в реальном widget/live только по отдельному разрешению и бюджету. | Draft до независимого Checker реализации и отдельного Cursor review. Staging/commit/push P1 не выполнены. После PASS Ledger не дописывать. |

## Draft — 2026-09-28: карточка REC-4-P и согласование документов

Папка/Git root `C:\Cursor Projects\artgents-bot-active`, ветка
`codex/d2-stage1-contract`; HEAD и локальный origin branch
`b02db8ee010b3431ab24f6e3ef98e5392a591673`, `origin/main` и merge-base
`141ce91fb1731cd990fcf8391550150016c73e7f`. До правок tracked/staging чисты;
чужие untracked `data/` и `docs/MARKETING_ANSWER_SCENARIOS.md` сохранены.
Git предупреждает о недоступных global ignore/`.pytest_cache/`; свежего fetch
не было. Семь разрешённых doc paths перечислены в §1
[карточки REC-4-P](DEMO_D2_PRICE_PRESENTATION_DETAILS_TASK.md).
Предыдущая строка REC-4 ниже — snapshot **до** его review, не текущий status:
его последующий Checker/Cursor PASS и сохранение относятся к `b02db8e`.
Старые строки, включая процессное исключение `6c4a963`, не переписываются.

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-REC-4-P-DOC | **ACCEPTANCE:** план A16/B18/B19 и регрессий, без runtime PASS. **D2 ROUTE:** read-only изучены текущие materializer/renderer, Markdown widget, service profile, offer details и ordered shown refs; код не изменён. **LEGACY IMPACT:** старый widget-format текст явно отделён от текущего D2; legacy selector/runtime не подключается. **OWNER DECISION:** согласованы D2-101–103; владелец отдельно выбрал детали всех показанных вариантов и скрытие кнопки при неполных данных, сохраняя прямой вопрос. Astra выполнила read-only архитектурный разбор; карточка делит реализацию на P1/P2 с точными allowlists и отдельными GO. Синхронизированы Decisions/Target/Acceptance/Roadmap/Widget Format. **Test isolation/evidence:** только чтение репозитория и документальные проверки, pytest/бот не запускались, provider/live/SMTP 0; БД/логи не открывались. Старые REC-4 75/10 — исторический отчёт Cursor, не новый прогон и не доказательство baseline будущей реализации. **FUTURE SCOPE:** код P1/P2, отдельные reviews, REC-5/A15, ручной/live тест с разрешением. | Draft до независимого Checker и отдельного Cursor review. Staging пуст; commit/push не разрешены и не выполнены. Ledger после PASS не дописывать. |

## Draft — 2026-09-28: REC-4 короткие цены и кнопки

Рабочая папка и Git root `C:\Cursor Projects\artgents-bot-active`, ветка
`codex/d2-stage1-contract`, baseline HEAD и локальный origin branch
`cebd09bd0deca0dd5c52fd0b3c4b70d6ef8dc654`; `origin/main` и merge-base
`141ce91fb1731cd990fcf8391550150016c73e7f`. Перед реализацией tracked
diff и staging пусты. Чужие untracked `data/` и
`docs/MARKETING_ANSWER_SCENARIOS.md` не правились и не stage. Карточка REC-4
была untracked и входит в checkpoint. Полный точный write allowlist — § «Точный
write allowlist будущей реализации» [карточки REC-4](DEMO_D2_REC4_PRICE_BUTTONS_TASK.md),
включая три отдельно разрешённых старых test-файла. Владелец отдельно
разрешил обновить в них проверку краткой цены и проверку опубликованного
объёма удаления зуба; остальные изменения в этих файлах касаются CTA.

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-REC-4 — краткие цены и кнопки | **ACCEPTANCE:** срез A01/A02/A07/A09/A10/A13/A14/A15, B06/B08/B12/B13/B14/B16/B17, C04/C05/C07/C09/C10 только в границе REC-4: одна точная услуга показывает все применимые опубликованные offers текущего tenant по возрастанию, включая четвёртую временную позицию, с именем варианта, scope и обязательными оговорками; первый ответ не перечисляет состав пакета и этапы оплаты, но они остаются в captured offer. Общий authored обзор до трёх цен и четыре кнопки объёма; follow-up подпись без якоря при сохранённом section ref; CTA документа приоритетна, иначе разрешённая нейтральная `default_consult`, без auto-lead. **D2 ROUTE:** offline JSON/SSE → один production parser → captured tenant snapshot и price/UI authority → frozen plan/render/store/replay → существующий widget/lead owner; цена и CTA не извлекаются из прозы модели. **LEGACY IMPACT:** второго prompt/parser, semantic regex, старого runtime, fallback и второго owner состояния нет; JSON/SSE и lead/privacy wire не менялись. **OWNER DECISION:** владелец подтвердил D2-100: для одного точного вопроса нет лимита три; общий обзор и B14 остаются отдельно. Владелец дал GO реализации и разрешил перечисленные расширения старых тестов; Astra дала read-only архитектурное заключение. **Test isolation:** fake provider, временные tenant copy/DB/logs, блокировка внешней сети; рабочий `data/` не открывался на запись, provider/live/SMTP 0. **Evidence:** адресный REC-4/price/snapshot набор 37 passed; широкий набор семи файлов на clean HEAD 61 passed / 9 failed и на REC-4 diff 61 passed / 9 failed с теми же девятью test IDs; B14, lead CTA, stale/forged и запреты CTA 6 passed, 1 failed. Последний `test_price_content_price_preserves_independent_content_and_request_order` падает тем же assertion на clean HEAD. Старые девять: doctor authored `patient_text_required`, history `spam_closed`, три старых content/source assertions и четыре старых snapshot/scope assertions; тесты не скрыты и не ослаблены. **FUTURE SCOPE:** REC-5 полная приёмка и ручная widget-проверка, отдельный анализ старых красных тестов, возможный показ большого каталога частями, live/merge/deploy. Это не полный A15/REC-5. | Draft до независимого Checker и отдельного Cursor review реализации. Staging, commit и push не выполнялись. После PASS Ledger не дописывать. |

## Draft — 2026-09-26: коррекция model envelope и подписи цены

Baseline `28ff60a4f51228dec1409e7b703cd279ea2dcee7`, ветка
`codex/d2-stage1-contract`; origin branch совпал, `origin/main` и merge-base
`141ce91`. До работы tracked/staged diff пуст. Чужой untracked `data/`
сохранён; лог теста владельца прочитан только для диагностики. Точный
allowlist — [карточка коррекции](DEMO_D2_ENVELOPE_CORRECTION_TASK.md).

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-ENVELOPE-CORR | **ACCEPTANCE:** B14/D2-080/T2, C01/R4 и подпись проверенной цены D2-093; не полный REC-4/5. **D2 ROUTE:** единственный действующий prompt явно отделяет самостоятельные вопросы текущего сообщения от пропущенного referent из истории; production parser по-прежнему отвергает `resolved` с null ID. Materializer замораживает имя услуги именно из `bundle.services[offer.service_id].name` рядом с price offer; renderer, числовые цены и условия не менялись. Widget преобразует только видимый `d2_invalid_turn` в человеческий текст; JSON/SSE error code остаётся, failed turn не commit ordinary/lead. **LEGACY IMPACT:** нового parser, второго call, semantic regex и старого fallback нет. **OWNER DECISION:** владелец разрешил отдельную коррекцию перед REC-4 и подпись услуги перед ценой; Astra дала read-only архитектурное заключение. **EVIDENCE:** три trace из карточки без копирования raw payload. До правок baseline 15 passed / 1 failed: старый prompt-version тест ждёт v19 при текущем v20; штатный browser fixture внутри sandbox истёк по timeout. После правок адресный набор 14 passed; расширенный набор 75 passed / 2 failed: старый `other` → `d2_experiment_content_not_resolved` и `test_price_content_price_preserves_independent_content_and_request_order`. Последний тест не менялся и повторил то же падение после удаления нового service-name префикса только в памяти процесса; это ограниченная изоляция, не clean HEAD baseline. Отдельный JSON/SSE tenant/replay тест 4 passed; browser harness с fake provider вне sandbox 1 passed. Сеть/provider 0, временные DB/logs. **FUTURE SCOPE:** REC-4 — краткость цены, повтор единицы, кнопки/CTA; REC-5 и отдельно разрешённый live eval; упрощение schema только новой карточкой. | Независимый Checker PASS: P0/P1 нет, его офлайн набор 16 passed. Cursor review ещё требуется. Staging/commit/push отсутствуют; после Cursor PASS Ledger не менять. |

## Draft — 2026-09-26: REC-3 память точной услуги

Baseline `279b21c3504b1c2ae999575e1f44eb85567d3ac7`, ветка
`codex/d2-stage1-contract`; локальный origin branch совпал, `origin/main` и
merge-base `141ce91`. До реализации tracked/staged diff пуст, чужой `data/`
сохранён. Точный allowlist — [карточка REC-3](DEMO_D2_RECOVERY_MEMORY_TASK.md),
включая отдельно разрешённый владельцем `core/response_plan_materialization.py`.

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-REC-3 — сохранение фокуса | **ACCEPTANCE:** точная услуга без topic сохраняется и связывается с одной следующей короткой ценовой частью, даже если модель не повторила ID; две разные ценовые услуги не превращают первую в фокус; одинаковые части оставляют однозначный фокус; CLARIFY service click сохраняет ценовую задачу; новая услуга и TTL не наследуют старую память или чужую ситуацию. Это REC-3, не полный A15/REC-5. **D2 ROUTE:** offline JSON/SSE → production parser → captured tenant/context → effective typed envelope → итоговый response plan и `session_delta` → ordinary state/store/replay. Первая цена, отложенная часть и UI сравнивались с одиночной ценой. **LEGACY IMPACT:** нового parser, semantic regex и fallback нет. **OWNER DECISION:** GO REC-3 и отдельное расширение allowlist для сборщика плана получены; Astra проверила две узкие коррекции после Checker REJECT. Исходный выбранный offline baseline: 70 passed / 1 failed (`spam_closed` в старом тесте истории). До Checker находок новый REC-3 и соседний набор: 84 passed / 1 failed (то же историческое падение); отдельные проверки границ 37 passed / 46 deselected. Затем Checker выявил два P1: короткая цена без повторного ID уходила в CLARIFY, а no-topic service click мог сохранять старую ситуацию/варианты. Оба случая воспроизведены красными HTTP-тестами до исправления. После исправления REC-3 + session-context: **73 passed**; REC-3 + session-context + multipart + R1: **91 passed / 1 failed**, старый `other` → `d2_experiment_content_not_resolved`. Более широкий промежуточный набор до P1-правок: 114 passed / 1 failed, старый тест истории; финальным aggregate его не считать. Вопрос о враче проверен через текущий `model_prose` с сохранённым service и replay; прежний `authored` directory path всё ещё отвергается, детерминированный справочник врачей этим checkpoint не подтверждён. Fake provider, временные DB/logs, live/provider/SMTP 0. **FUTURE SCOPE:** REC-4/5, отдельный разбор старых authored/`other` отказов, live/merge/deploy. | Draft. Первый независимый Checker review дал REJECT по двум P1; после их исправления требуется focused Checker recheck и отдельный Cursor review рубежа 3. Staging/commit/push не выполнены. Ledger после PASS не дописывать. |

## Draft — 2026-09-26: коррекция REC-2 D2-097/098

Baseline `7621441ca84e6bfc39fce79b744b647cc521a8b4`, ветка
`codex/d2-stage1-contract`; origin branch совпал, `origin/main` и merge-base
`141ce91`. Tracked/staged diff до работы пуст; чужой untracked `data/`
сохранён. Точный allowlist — § «Точный write allowlist» в
[карточке коррекции](DEMO_D2_REC2_CORRECTION_TASK.md).

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-REC-2-CORR | **ACCEPTANCE:** A03/B12/C01 и регрессии C04/C05/C07/C09/C10, не полный REC-5. **D2 ROUTE:** `/ask`/`/ask/stream`, один parser, captured tenant snapshot разрешает optional claims и проверенный document action в одном effective envelope **до** session binding; затем прежний materializer/frozen plan/store/replay. **LEGACY IMPACT:** запрещённый runtime/fallback не подключается. **OWNER DECISION:** владелец отнёс D2-097/098 к REC-2, после первого Cursor REJECT согласовал узкое правило для чистого документного клика и разрешил добавить Product Decisions в allowlist; D2-099 остаётся REC-4. До кода baseline: 2 passed / 18 deselected в узком HTTP-тесте. Новый P1-тест до fix: 6 failed / 1 passed. После fix и окончательного ограничения чистым кликом: целевой P1/source/multipart набор **18 passed / 44 deselected**, соседний widget/replay/lead/R1 набор **24 passed / 2 deselected**. Широкий aggregate шести файлов до последнего ограничения: **86 passed / 1 failed / 1 deselected**; красный `test_other_with_prose_gets_authored_help_not_price_gate` упирается в старый `d2_experiment_content_not_resolved` для `other`, описанный в исходной REC-2 карточке; тест не ослаблялся. В соседнем наборе исключены старый `other` и browser-case; browser в этом checkpoint не запускался. Тестовые DB/логи в `%TEMP%`, fake provider; live/provider/SMTP 0. **FUTURE SCOPE:** REC-3–5, live/merge/deploy и старые read-only падения REC-2 открыты. | Draft после Cursor REJECT; требуется focused Checker recheck находки и новый отдельный Cursor review diff до commit; staging пуст. Исторический PASS `bc76169` и прежний Checker PASS этой коррекции не переносятся на изменённый diff. |

## Draft — 2026-09-26: документальная фиксация widget-дефектов

Baseline `6c4a96339a2eb293fa3dc2b95e253ad6efedd1c9`, ветка
`codex/d2-stage1-contract`, `origin/main` и merge-base `141ce91`.
Перед правкой tracked/staged diff пуст; чужой untracked `data/` сохранён.
Точный write allowlist: этот Ledger, `DEMO_D2_PRODUCT_DECISIONS.md`,
`DEMO_D2_ACCEPTANCE.md`, `DEMO_D2_DELIVERY_ROADMAP.md`.

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-WIDGET-FINDINGS-DOC | **ACCEPTANCE:** только уточнённый план A03/B12/C01 и регрессии C04/C05/C07/C09/C10, без runtime PASS. **D2 ROUTE:** текущие `/ask`/`/ask/stream` не меняются. **LEGACY IMPACT:** код и старый runtime не меняются. **OWNER DECISION:** владелец попросил зафиксировать общий D2-сбой, связь CTA с документом и нейтральную CTA; отдельно подтвердил, что она показывается только в разрешённых D2-012 ответах. Полный локальный журнал подтвердил `d2_invalid_turn` (`276c9af0caf245bebc04fa56e65370d2`) и потерю source CTA (`f60977c81a8d4dc9a170496195526beb`); сырые переписки и ПД в commit не включаются. **FUTURE SCOPE:** владелец ещё определит место D2-097/098 в ограниченной карточке и даст отдельный GO; D2-099 проверить в REC-4; REC-3–5/live/merge/deploy не разрешены. | Draft до review. Независимый Checker ожидается; Cursor на требуемом рубеже отдельно. Документальный diff ещё не stage/commit/push; офлайн-тесты не запускались, provider/live/SMTP 0. Известные старые падения REC-2 не меняют статуса. |

## Дополнение — 2026-09-26: локальная полная D2-трассировка, offline-reviewed

REC-2 после отдельных независимых Checker и Cursor отчётов сохранён и отправлен
в `codex/d2-stage1-contract` как `bc7616999ed9fa2a9a3f74a3e7bdc8b47ba0e171`.
Его historical Draft ниже описывает состояние проверяемого diff до checkpoint.
Новый baseline: `bc76169`; staging до работы пуст, foreign `data/` не тронут.

По отдельному запросу владельца создаётся opt-in локальный полный журнал D2,
включая тестовые ПД. Он не заменяет REC-1 безопасные события и не разрешает
live/merge/deploy. Исторический `d2_full_audit.py` используется только как
reference writer; старый dialogue/HTTP runtime не переносится. Карточка:
[D2 local full audit](DEMO_D2_FULL_AUDIT_TASK.md). Код прошёл offline review:
последний полный прогон нового `tests/test_d2_full_audit.py` — **15 passed**;
связанный офлайн-набор full audit + diagnostics/HTTP/SSE/widget/no-legacy/lead
до последнего расширения маски credentials — **71 passed**. После расширения
отдельные 3 целевых теста также прошли; это не повтор общего набора.
Независимый Checker дважды указал на пробелы маскировки и перехода lead state;
после исправлений его focused recheck дал PASS. Переданный владельцем отдельный
read-only Cursor review также дал PASS: 15 новых и 67 связанных тестов прошли.
Статусы записаны после получения отчётов, не как предварительный вердикт.
Локальное включение журнала, live, merge и deploy отдельно не разрешены.
Fake provider и временные DB/log/tenant; provider/live/SMTP 0.

## Дополнение — 2026-09-26: реализация REC-2 на проверке

Active-папка `C:\Cursor Projects\artgents-bot-active`, ветка
`codex/d2-stage1-contract`, implementation baseline `ce47c16f564498165c1d00b2d0efd997dcbb9c22`.
Карточка получила внешние Checker/Cursor PASS, затем владелец дал отдельный GO
на реализацию. Это не PASS реализации. Staging/commit/push для текущего diff не
выполнены, live/provider/SMTP 0; foreign `data/` не менялся.

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-REC-2 — пригодная проза и optional provenance | **ACCEPTANCE:** C01–C03 и регрессии C04/C05/C08/C09/C10/A12; не полный REC-5. **D2 ROUTE:** `/ask`/`/ask/stream` → один parser → тот же materializer/plan/store. **LEGACY IMPACT:** fallback и semantic selector не добавлены. **OWNER DECISION:** GO на код REC-2 получен; REC-3/4 и live отдельно. На исходном baseline 8 файлов: 83 passed / 27 failed. Последний полный набор 10 файлов: 150 passed / 13 failed; после него точечно восстановлен прежний код ошибки неизвестной услуги (2 passed; новый полный aggregate не заявлен). Остаток — старые parser/R1 проверки (v19, прежний HTTP fixture/old `other` route). Новые собранные JSON/SSE, replay, follow-up, mixed, tenant/typed strict и review-sink сценарии проходят. Дополнительный read-only regression set без browser-case: 52 passed / 6 failed / 1 deselected; browser-case отдельно прошёл вне sandbox. Шесть read-only красных тестов не менялись из-за allowlist, список и причины — §9 карточки. | **Draft; ожидаются независимый Checker и Cursor именно implementation diff.** Не повышать исторический PASS, не записывать verdict в diff. Commit/push только после review и отдельного решения владельца. |

## Дополнение — 2026-09-26: REC-1 сохранён, REC-2 только планируется

В active-папке на `codex/d2-stage1-contract` по отдельному разрешению владельца
создан и отправлен `f4bae9b0b292026733854ae1d8fd34e608f953d5`
(`feat(d2): add safe REC-1 diagnostics`). Ровно девять проверенных файлов;
remote branch hash подтверждён ls-remote. Checker и Cursor отчёты REC-1,
включая late-clock дополнение, получены отдельно до commit; исторический
Draft ниже отражает состояние проверяемого diff до этих завершающих действий.
В этом шаге тесты повторно не запускались. Live/provider/SMTP 0.

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-REC-2-DOC — карточка ответов и ссылок | **ACCEPTANCE:** план C01–C03 и обязательные регрессии границ; никаких новых runtime PASS. **D2 ROUTE:** существующий, без изменения кода. **LEGACY IMPACT:** старый WIP не переносится. **OWNER DECISION:** разрешены документы, не реализация. **FUTURE SCOPE:** отдельный GO REC-2, REC-3–5/live. Baseline f4bae9b; allowlist — новая Recovery Content Task, Roadmap, Ledger. Проверены code-level места отказов и действующий D2-092. Тесты не запускались, provider/live/SMTP 0. | Draft; независимый Checker и Cursor review карточки ожидаются отдельными отчётами. Карточка не stage/commit/push; чужой data/ сохранён. |

## Текущее дополнение — 2026-09-25

Активная папка: `C:\Cursor Projects\artgents-bot-active`; ветка
`codex/d2-stage1-contract`; baseline документационного diff и runtime:
`e261383515d94e7d925acc705d8a6731aa704e48`.
`origin/main` / merge-base: `141ce91fb1731cd990fcf8391550150016c73e7f`.
Это журнал evidence, не самостоятельный план. Текущий порядок — в
[Delivery Roadmap](DEMO_D2_DELIVERY_ROADMAP.md); сохранённые источники и
ограничения аудита — в [inventory](DEMO_D2_RECONCILIATION_INVENTORY.md).

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-REC-1 — безопасная диагностика | **ACCEPTANCE:** диагностический срез C01/C05/C06/C09/C10; regressions C04/C08/A12, не C03/полное демо. **D2 ROUTE:** реальные JSON/SSE, прежние adapter/common turn/parser/materializer/store; attempt-local observer, без изменения ответа/state/wire. **LEGACY IMPACT:** старый runtime не добавлен. **OWNER DECISION:** отдельный GO на REC-1 и шесть test packages получен. **FUTURE SCOPE:** REC-2–5/live отдельно. Baseline `a185b54`; точные allowlist, manifest, команды и ограничения — §9 карточки. | Draft; verdict отдельными отчётами, тестовое дополнение требует focused recheck. Existing baseline: 38 passed / 2 failed (v19 expectation, sandbox browser timeout). Исторический implementation aggregate: 64 passed / 2 failed, browser прошёл; fixture уточнено, focused recheck 26 passed. Последующий полный прогон по переданному владельцем отчёту Cursor: 65 passed / 1 failed, 111 с; прежнее ожидание v19 вместо v20 остаётся. Затем добавлены шесть late-clock случаев без production-правок: focused diagnostics 32 passed, 20.84 с; нового полного aggregate после них нет. Подробности — §9 карточки. Provider/live/SMTP 0; staging пуст, commit/push не выполнены. |
| D2-REC-DOC — план восстановления и карточка диагностики | **ACCEPTANCE:** только документы; runtime-критерии не закрываются. **D2 ROUTE / LEGACY IMPACT:** без изменений кода, данных, wire и окружения. Allowlist: этот Ledger, Delivery Roadmap, Reconciliation Inventory и Recovery Diagnostics Task. **OWNER DECISION:** разрешена фиксация документов и передача в Cursor. **FUTURE SCOPE:** отдельный GO на REC-1 и проверка тестового окружения. Проверены ссылки, 36/36 inventory и отсутствие tracked diff вне allowlist; `git diff --check` чистый. Тесты не запускались по scope; provider/live calls 0; staging пуст. | Draft — ожидается независимый Checker и завершение Cursor review исправленного diff; checkpoint не закрыт, commit/push не выполнены. Вердикты сообщаются отдельными отчётами проверяющих, не записываются внутрь проверяемого diff. |

Исторические D2-S1–S4 и CP-записи ниже не переписаны и не повышены до нового
PASS. D2-S1 остаётся с незакрытым focused review; D2-S2 PASS не подменяет
отсутствовавший в его evidence полноценный pytest. Правило exact-service
из D2-S3 позднее изменено владельцем и реализовано в `7b8554f`: ascending
без лимита и зависимости от direction, с фильтрами brand/volume; обзор
направления по-прежнему отдельный. D2-S4 PASS относится к проверенному
mixed checkpoint, не ко всем целым диалогам текущей сборки.

Результат предыдущего выбранного offline-аудита — 147 passed / 11 failed,
не новая проверка этого документационного diff и не полный CI. Тесты
запускались на другом interpreter против active-кода; ограничения и
сравнения baseline перечислены в inventory. Общая демо-приёмка открыта.
Подготовительные документы ранее получили независимый review во временной
папке; этот результат не переносится автоматически на постоянный diff.

## Историческая запись этапа 0

Обновлено: 2026-09-24 для документального этапа 0. Это не roadmap и не
план: только факты с доказательствами. Текущая точка отсчёта — сохранённый
D2 HEAD `38fdeb3`; незакоммиченный WIP в основной папке не включён и не
получает здесь задним числом статус PASS. Правила ведения — в
[DEMO_D2_EXECUTION_LOCK.md](DEMO_D2_EXECUTION_LOCK.md). В будущем новая строка
добавляется в незакоммиченный diff **до** независимого review вместе с кодом и
тестами. Она называет checkpoint; фактический hash сообщается в финальном
closeout, потому что commit не может содержать свой собственный hash.

## Текущая точка отсчёта

На `38fdeb3` `app.ask` и `app.ask_stream` вызывают `run_d2_ask_json`, который
вызывает общий `run_d2_dialogue_turn`; widget подключён к `/ask/stream`.
FullContext-подготовка присутствует. Это подтверждает активность пути, но
не устойчивость ответов, корректность ценовых кликов или прохождение новой
приёмки A13–A15/C03. Отдельный этап 0 меняет только документы; его
Checker/Cursor verdict будет указан после проверки diff. Прежняя строка
`Current local runtime` и заключительная фиксация CP5 ниже сохраняются
как исторические снимки на момент их составления, а не текущие инструкции.

Исключение ниже отмечено явно: CP1 был уже закоммичен без строки Ledger. Его
факт добавлен отдельным документным correction checkpoint и не выдаётся за
часть исходного проверенного diff.

| Checkpoint | Что реально работает | Где вызывается | Статус legacy runtime | Что не доказано | Cursor verdict | Evidence commit / closeout |
|---|---|---|---|---|---|---|
| D2 component series C2–C15 | Отдельные D2 seams/детали: расширенный D1R envelope (части, typed situation), price modes, deferral, part failure, prose realization, tenant snapshot/sources, TTL-проекция, continuation binding, plan focus, cross-topic carry | Только изолированные unit/seam-тесты (`tests/test_d2_*`); из общего маршрута и HTTP не вызываются | Не затронут: `/ask` и виджет продолжают работать через legacy path | Полный пользовательский сценарий, сборка компонентов вместе, HTTP integration, реальная модель | PASS отдельных изолированных checkpoint (по журналу задач S2); сборку и сценарии не подтверждают | `b9e0de6`–`0f8e405` |
| S2-V0 A08 | Внутренний D2 route проходит **два хода A08** целиком: raw fake provider → production D1R parser → production tenant loader → resolver/materializer → text/UI → persistent typed SQLite state, включая close/reopen store; legacy Composer/sales_fast/вторая ordinary memory не вызываются (runtime observer); сеть запрещена; tenant isolation, TTL, invalid provider output и атомарность записи проверены | `core/d2_dialogue.py::run_d2_dialogue_turn`; вызывается только из `tests/test_d2_dialogue_a08.py` | Не затронут: legacy path остаётся единственным обслуживающим `/ask`/`/ask/stream`/widget | Подключение к `/ask`, `/ask/stream`, widget; реальная модель; replay результата по request_id; lead/privacy мост; все сценарии кроме A08 | **PASS** (независимый Checker этого checkpoint) | `8e7a3b6` |
| CP1 — D1R prompt-contract (late Ledger correction) | Единственный production prompt v17 явно требует для каждого request typed `service_id`, `topic_id`, `statement_mode` и `situation`; production parser принимает корректный raw A08 envelope и отвергает неверный enum `continuity` | `core/one_call_prompt_contract.py`; production parser проверен в `tests/test_request_understanding_schema_offline.py`; внутренний A08 test использует isolated tenant copy | Не затронут: legacy path остаётся единственным обслуживающим `/ask`/`/ask/stream`/widget | Approved demo tenant data, настоящая модель, HTTP/widget, replay/lead bridge и все сценарии кроме внутреннего A08 | **PASS** для исходного CP1 по отчёту независимого Cursor; данная строка требует отдельной проверки только как поздняя документационная коррекция | Original CP1 `7a0fa7c`; 20 targeted offline tests, provider calls 0 |
| CP2 — demo tenant data для A08 | Штатный `clients/demo` tenant pack содержит direction-level данные для `implantation` и `prosthetics`: порядок существующих прайс-карточек, цена/единица/обязательные условия и authored пояснения. Внутренний двухходовый A08 читает только temporary copy этого production pack через tenant snapshot, сохраняет один зуб при переходе темы и не берёт данные из test-only fixture | `core/d2_dialogue.py::run_d2_dialogue_turn` → `load_d2_tenant_snapshot` → `build_d2_snapshot_sources`; проверка в `tests/test_d2_dialogue_a08.py` | Не затронут: legacy path остаётся единственным обслуживающим `/ask`/`/ask/stream`/widget | Настоящая модель, HTTP/widget, replay/lead bridge и все сценарии кроме внутреннего A08 | **PASS** | `c195051`; 21 targeted offline tests, provider calls 0 |
| CP3 — ограниченная live-проверка A08 | Два точных последовательных хода A08 прошли через один production D1R parser и штатный demo tenant snapshot: `implantation` показала утверждённые три offer, затем `prosthetics` показало только `implant_supported_prosthetics.default` с перенесённым extent `one_tooth`. Совпадающий legacy duplicate канонизируется внутри единственной модели `RequestUnderstanding`; отличающийся по-прежнему отвергается. D2 follow-up instruction использует только typed `D2_SESSION_CONTEXT`, не создаёт новый tenant-data/wire/parser contract. | Только явно авторизованный internal runner `scripts/run_d2_a08_live.py` → `D2Cp3LiveProvider` → `run_d2_dialogue_turn`; данные — `clients/demo` через production loader/snapshot | Не затронут: `/ask`, `/ask/stream`, widget и legacy path не вызывались | HTTP/SSE/widget, другие A01–A12, replay/lead/privacy, deployment; результат не доказывает общий live runtime. Raw provider payload и текст не сохранены. | **PASS** | `8bfaf38`; 100 targeted offline tests; qwen3.8-flash, 2 explicitly authorized calls, no automatic retries; demo data baseline `c195051` |
| CP4 — common turn completion | Внутренний D2 route резервирует один `(tenant, sid, request_id)` до model call, атомарно фиксирует typed ordinary state и точный final result в одном `D2DialogueStore`, а повтор того же payload возвращает сохранённый result без model call. Иной payload с тем же request ID отклоняется; второй параллельный request того же session не становится final. PII-safe provider input использует существующий privacy boundary без обращения к legacy `session`. Явно переданный existing lead-effect сохраняется только как effect ID/status без контактов; после commit допускается ровно одна попытка dispatcher, ambiguous outcome остаётся `unknown` без automatic retry. | Только `core/d2_dialogue.py::run_d2_dialogue_turn` и `D2DialogueStore`; тестовый dispatcher не является HTTP/widget/lead UI entry | Не затронут: `/ask`, `/ask/stream`, widget, Composer, sales_fast и legacy runtime/selectors не вызываются | HTTP/SSE delivery/replay, реальный lead UI/transport, другие A01–A12, общий runtime, deployment; CP4 не меняет правила паузы/выхода/возврата lead flow и не создаёт пользовательский сценарий | **PASS** | `b1bf1a34304874c06ca1e6ea57c5a81714cd62db`; 124 targeted offline tests, provider/live calls 0 |
| CP5-A10a — same-topic price continuation | Внутренний common D2 route собирает два хода через production parser, штатный demo tenant snapshot, materializer/renderer и единый `D2DialogueStore`: после утверждённого A08 «один зуб / имплантация» короткий typed same-topic price follow-up сохраняет тот же extent и `situation_owner_id`, показывает те же утверждённые demo offer и условия. Перенос происходит только из fresh typed `carried_situation`; текст диалога не интерпретируется. Expired context не переносится. | Только `core/d2_dialogue.py::run_d2_dialogue_turn` → `build_d2_snapshot_sources` → `resolve_d2_envelope_response`; test копирует `clients/demo`, не fixture | Не затронуты `/ask`, `/ask/stream`, HTTP/SSE, widget, Composer, sales_fast, legacy runtime/selectors и fallback | Полный A10: новая пустая сессия, смена услуги, broad overview/volume choices; все другие сценарии, общий runtime и deployment | **PASS** | `b93dfc673c6bc59582dfe2abbf1339f3525ff2a7`; 129 targeted offline tests; provider/live calls 0 |
| CP5-B13a — simple direct service price | Внутренний common D2 route собирает один прямой вопрос о цене лечения кариеса через production parser, штатный demo tenant snapshot, materializer/renderer и единый `D2DialogueStore`. Он выбирает только единственную active offer данного сервиса прямо из snapshot, без legacy selector: сохраняются опубликованные «от», единица `tooth` и условие; промо/fact refs не допускаются к показу через этот checkpoint. | Только `core/d2_dialogue.py::run_d2_dialogue_turn` → `build_d2_snapshot_sources` → `resolve_d2_envelope_response`; test копирует `clients/demo`, не fixture | Не затронуты `/ask`, `/ask/stream`, HTTP/SSE, widget, Composer, sales_fast, legacy runtime/selectors и fallback | Несколько offer одного сервиса, промо/marketing facts, цена с обязательной metadata, A02 и иные прямые услуги; все другие сценарии, общий runtime и deployment | **PASS** | `b66dc5c9d04e0ff94e9a5d1e5773d1b651e86241`; 42 targeted offline tests passed (one known unrelated baseline failure excluded); provider/live calls 0 |
| CP5 governance — scenario/marketing simplification audit | Read-only аудит сохранил доказанные A08/A10a/B13a, выявил риск service-specific веток и перекрывающихся legacy marketing authority. Зафиксирован будущий D2 contract: один fact с short/full form, один service commercial profile, не более одного пакета усилителя и одного пакета «Также» на услугу (D2-090), compatibility groups и mechanism-based checkpoint batching. D2-O4 закрыто; числовые caps «Также 1–3» / «0–5» отменены. | Только документы governance; runtime, tests и tenant data не менялись | Legacy runtime/data не изменены. Старые marketing docs явно помечены как неканоничные для D2 | CP5-M1/M2/M3, A02/A11/B08, HTTP/SSE/widget и live не доказаны | Draft — ожидает independent Cursor review | Uncommitted documentation diff including D2-090; provider/live calls 0 |
| CP5-M1 — commercial data contract | Существующий `load_d2_tenant_snapshot` / `build_d2_model_view` читает D2 commercial contract из штатного `clients/demo/target_response/d2_commercial.json`: один promo fact ID с short/full, service profile (`promo_refs` ≤2, необязательные один `price_booster_id` и один `also_list_id`), пакет = имя + готовый текст, compatibility groups с `explanation_text`. Пустые/отсутствующие пакеты валидны. Повреждённые ID, чужой tenant, два booster/also, противоречивые short/full — `D2TenantSnapshotError`, без fallback. D2 не берёт `scenario_rules` / overlapping marketing lists как authority. | Только `load_d2_tenant_snapshot` → `build_d2_model_view`; proof в `tests/test_d2_commercial_contract.py`. Не `run_d2_dialogue_turn`, не HTTP/widget/materializer commercial plan | Не затронуты `/ask`, `/ask/stream`, widget, Composer, sales_fast, legacy selectors и fallback. Legacy `/ask` не расширялся | A02/A11/B08, CP5-M2 commercial plan, HTTP/SSE/widget, live, полные тексты клиники и визуал «Также» не доказаны | **PASS** | `d0975ffb8c82aec1c3d1df9e797dc7cca44cea74`; 18 targeted offline tests, provider/live calls 0 |
| CP5-M2 — common commercial plan | Внутренний common D2 route читает commercial contract из snapshot и до freeze кладёт в plan short promo, необязательный один пакет усилителя, необязательный один пакет «Также» и compatibility block с готовым текстом. Пустой профиль не ломает опубликованную цену. Auto-promo учитывает сохранённые shown IDs. Legacy `select_target_marketing` / `scenario_rules` не вызываются. Offer `fact_refs` больше не являются D2 commercial gate. | `run_d2_dialogue_turn` → `load_d2_tenant_snapshot` → `build_d2_snapshot_sources` → `resolve_d2_commercial_plan` → `resolve_d2_envelope_response` до freeze; proof в `tests/test_d2_commercial_plan.py` | Не затронуты `/ask`, `/ask/stream`, widget, Composer, sales_fast и fallback. Legacy marketing selector недостижим из D2 route | A02/A11/B08, визуал списка «Также», полные тексты клиники, HTTP/SSE/widget и live не доказаны | **PASS** | `d36ae7d806067b5ce0fc1d23c74a7b0dfceed164`; 23 targeted offline tests, provider/live calls 0 |
| CP5-M3 — assembled A02/A11/B08 | Внутренний common D2 route собирает A02 (цена отбеливания и отдельно виниров одним price profile без service-specific кода), A11 (полный прямой ответ об акциях услуги и общий список, повтор ранее показанной акции) и B08 (price profile, пакет «Также» с гарантией, compatibility group из двух видимых альтернатив). Auto использует короткую форму, direct promotion — полную. Просроченные promo не показываются. Legacy marketing selector не вызывается. | `run_d2_dialogue_turn` → `resolve_d2_commercial_plan` → `resolve_d2_envelope_response`; proof в `tests/test_d2_commercial_scenarios.py` | Не затронуты `/ask`, `/ask/stream`, widget, Composer, sales_fast и fallback | D2-017 обычный content+short promo без цены, визуал «Также», HTTP/SSE/widget, live и остальные CP5 семьи не доказаны | **PASS** | 45 targeted offline tests, provider/live calls 0 |
| CP5-C1 — content / direct-fact lookup | Внутренний common D2 route собирает lookup материала: A03 (страх будущей боли — `model_prose` по pain.md + source UI, video/follow-up не повторяются, CTA отдельно, до 2 коротких акций без booster/«Также»), A04 (прямой вопрос о гарантии — `model_prose` по `clinic__info__warranty.md` + follow-up/CTA документа, не полная форма `implant_warranty` и не пакет «Также», D2-091), B04 только механизм сравнения D2-034 (готовое сравнение → его текст/UI; два материала → нейтральные факты без follow-up; нет стороны → честный пробел без подмены), B15 (раздел ниже korotko, материал без korotko, нерелевантная резервная цитата не подменяет нужный раздел). Typed refs → grounded answer + source UI. | `run_d2_dialogue_turn` → `build_d2_snapshot_sources` → `resolve_d2_envelope_response`; proof в `tests/test_d2_content_scenarios.py`; test копирует `clients/demo`, не fixture | Не затронуты `/ask`, `/ask/stream`, HTTP/SSE, widget, Composer, sales_fast, legacy selectors и fallback | Две независимые информационные части в одном сообщении (D2-072), continuation/choice, directory/UI, terminal текущей боли, полный T3 prose repair, HTTP/SSE/widget и live не доказаны; гибрид гарантия model+fact отложен | **PASS** | `1be27e9`; voice correction D2-091; provider/live calls 0 |
| CP5-C2a — continuation/choice slice | Внутренний common D2 route собирает срез continuation/choice: A01 (обзор направления до 3 цен + 4 кнопки объёма; reported объём; hypothetical не переписывает факт; correction переписывает), A07 («Не знаю» после обзора — ориентир по цене + CTA `price`, без повторного scope-текста/volume-кнопок и без lead; кнопка «Рассказать о ситуации» в этом срезе не собиралась), TTL (после idle ambiguous follow-up не несёт expired situation). Volume labels из `ui.yaml` scope_nav. A10a не переписан. | `run_d2_dialogue_turn` → `build_d2_snapshot_sources` → `resolve_d2_envelope_response`; proof в `tests/test_d2_continuation_scenarios.py`; demo `d2_direction_prices.json` / `ui.yaml` | Не затронуты `/ask`, `/ask/stream`, HTTP/SSE, widget, Composer, sales_fast, legacy selectors и fallback | Полный A10 (пустая сессия / смена на отбеливание), полный B11 (смена человека), secondary «Рассказать о ситуации» (D2-022), multi-part, directory/UI, terminal, HTTP/SSE/widget и live не доказаны | **PASS** | `0e134fa`; provider/live calls 0 |
| CP5-C2b — A10 empty/switch + B11 person | Внутренний common D2 route: A10 пустая сессия «Сколько стоит?» → `CLARIFY` из `ui.yaml` continuation_clarify + guided_menu (без выдуманной цены); после имплантации «А отбеливание?» → только `professional_whitening.default`, без carry имплант-situation/цен (D2-032); B11 срез — `relation=other` даже с `continuity=same` не наследует `carried_situation` / owner (новый `situation_owner_id`). Lead consent / A12 / terminal вне среза. | `run_d2_dialogue_turn` → `build_d2_focus_clarify_response` / `bind_d1r_envelope_to_d2_context` → `resolve_d2_envelope_response`; proof в `tests/test_d2_continuation_scenarios.py` | Не затронуты `/ask`, `/ask/stream`, HTTP/SSE, widget, Composer, sales_fast, legacy selectors и fallback | Lead consent (D2-031), полный B11 (активная заявка/контакты после TTL, неповтор UI), All-on-4 как отдельный кейс, multi-part, directory/UI, terminal, HTTP/SSE/widget и live не доказаны | **PASS** | `48e8245`; provider/live calls 0 |
| CP5-MP — multi-part A05/A06/B14 | Внутренний common D2 route собирает составное сообщение: A05 (обзор цен имплантации + боль `model_prose`, без follow-up/видео боли), A06 (цена виниров + гарантия md без переноса услуги между частями), B14 (два ценовых вопроса — ответ на первый ≤3 offer, второй `deferred` с notice D2-080; цена+info сохраняет info). Смежно C02: пустой direct-service прайс → `d2_no_price_candidates`, живая content-часть сохраняется. Multi-topic parts не требуют единого session focus. | `run_d2_dialogue_turn` → production parser → `build_d2_snapshot_sources` → `resolve_d2_envelope_response` → `D2DialogueStore`; proof в `tests/test_d2_multipart_scenarios.py`; temporary copy `clients/demo` | Не затронуты `/ask`, `/ask/stream`, HTTP/SSE, widget, Composer, sales_fast, legacy selectors и fallback | Полный C02/C01, availability/policy, recovery, directory/UI, terminal/lead, две независимые info-части без цены (чистый D2-072-only), HTTP/SSE/widget и live не доказаны | **PASS** | `cf79475`; provider/live calls 0 |
| CP5-AP — availability/policy B01/B10 | Внутренний common D2 route: B01 — `bone_graft` `no_public_price` (approved_text, без суммы); понятая услуга без `content_ref` → info gap (D2-024), не «не оказываем»; typed authored alternative `braces→aligners` из `clinic_policies.yaml` в snapshot; inactive без alternative → тот же gap. B10 — `clinic_policy` по typed `policy_ids` / eligibility scheme / child subject → authored answers ОМС/ДМС/дети из snapshot; пустой policy → CLARIFY; неизвестный id → gap, не yes/no. Triggers/`match_clinic_policy_key` не вызываются. | `run_d2_dialogue_turn` → `build_d2_clinic_policy_response` / `build_d2_service_availability_response` / price materializer; proof в `tests/test_d2_availability_scenarios.py`; snapshot читает `clinic_policies.yaml` | Не затронуты `/ask`, `/ask/stream`, HTTP/SSE, widget, Composer, sales_fast, legacy selectors и fallback | Recovery, directory/UI, terminal/lead, полный B01 (все price modes), booking+policy блокировки, HTTP/SSE/widget и live не доказаны | **PASS** | `8939a29`; provider/live calls 0 |
| CP5-REC — D2-native recovery B16/C02 | Внутренний common D2 route: неполный ответ внутри того же D2 plan. B16 — нет цены + живой независимый материал → стандартный price-gap, content сохранён, разрешённая CTA, без «не оказываем» и без auto-lead (D2-081). C02 — живая цена сохраняется при ошибочном `content_ref` (`d2_content_source_missing`) и при prose money (T3 unavailable/recovered); optional secondary UI сбой не скрывает цену (D2-065/D2-083). Карточка услуги только по typed ID в snapshot; чужой tenant по-прежнему fatal. Нет legacy fallback. | `run_d2_dialogue_turn` → `build_d2_snapshot_sources` → `resolve_d2_envelope_response`; proof в `tests/test_d2_recovery_scenarios.py`; soft-fail content binding в materializer | Не затронуты `/ask`, `/ask/stream`, HTTP/SSE, widget, Composer, sales_fast, legacy selectors и fallback | Terminal/lead, directory/UI, полный B17 overview, HTTP/SSE/widget и live не доказаны | **PASS** | `6d8e446`; provider/live calls 0 |
| CP5-TERM — B03 manual-contact terminal | Внутренний common D2 route: `route=ADMIN` → одна authored заглушка из `clinic_policies.yaml` (`manual_contact_template` + urgent + телефон tenant в тексте). Боль сейчас / кровь / жалоба / директор — один stub; без медсовета, цен, акций, CTA/follow-up/видео и без UI-кнопок (`canonical_contact=None`, D2-023). Контраст: страх будущей боли остаётся ordinary ANSWER (A03). `terminal_state=medical_terminal`. Нет legacy fallback. | `run_d2_dialogue_turn` → `build_d2_manual_contact_terminal_response`; proof в `tests/test_d2_terminal_scenarios.py` | Не затронуты `/ask`, `/ask/stream`, HTTP/SSE, widget, Composer, sales_fast, legacy selectors и fallback | Полный A12 lead / D2-022, spam hard-stop D2-040/071, directory/UI, HTTP/SSE/widget и live не доказаны | **PASS** | provider/live calls 0; hash в closeout |
| CP5-LEAD — A12 lead/privacy on common route | Внутренний common D2 route собирает существующий D1R lead/privacy без переписывания: adult `kind=booking` → `collecting_name` (tone name prompt, cancel QR, без подтверждения слота/времени); child booking → policy block, lead не стартует; cancel/defer выходит без CTA; имя→телефон→один `lead_effect` (`demo_stub`); pending-вопрос на PII-слоте (answer/continue) с 0 provider calls; D2-022 situation start→note→name без мед/маркетинг ответа; D2-031 после выхода `booking_intent_ever` не поднимает lead на ordinary ходе. Вход в booking только при `lead_bridge=True` и точном match bound session client = `session_key.client_id`; активный lead short-circuitится при matching bound session даже без флага; mismatch → fail-closed. PII в session mem; D2 store — только effect receipt. | `run_d2_dialogue_turn` → `core/d2_lead_bridge.py` → `clinic_policy_resolver` / `lead_turn_classifier` / session; proof в `tests/test_d2_lead_scenarios.py` | Не затронуты `/ask`, `/ask/stream`, HTTP/SSE, widget, Composer, sales_fast и fallback | HTTP lead UI/transport, реальный SMTP, pause/resume gray LLM, полный B11 lead-after-TTL, spam hard-stop, directory secondary situation button и live не доказаны | **PASS** | provider/live calls 0; hash в closeout |
| CP5-SPAM — D2-040/071 consecutive garbage | Внутренний common D2 route: детерминированный garbage gate (empty / short / link-only / obvious noise / mash) → один authored warn из `clinic_policies.yaml` (`spam_one_chance_template`), без CTA/меню/цен/мед; второй подряд мусор → `terminal_state=spam_closed` (`spam_closed_template`); третье сообщение в том же sid остаётся closed (D2-071). Нормальный dental FAQ после warn сбрасывает счётчик. Активный lead pre-provider не перехватывается spam. Phone-only остаётся `d2_provider_input_privacy_only`. Off-topic polite refuse и wrong-layout вне среза. Нет legacy anti-spam redirect. | `run_d2_dialogue_turn` → `core/d2_spam_gate.py` → DeterministicBypass `spam_warn`/`spam_closed`; proof в `tests/test_d2_spam_scenarios.py` | Не затронуты `/ask`, `/ask/stream`, HTTP/SSE, widget, Composer, sales_fast, legacy anti-spam redirect | Off-topic polite refuse (вторая ветка D2-040), wrong keyboard layout, directory/UI, HTTP/SSE/widget и live не доказаны | **PASS** | `e531cb1`; provider/live calls 0 |
| CP5-DIR-A — doctors/protocols directory | Внутренний common D2 route: typed directory без patient_text regex. Врачи услуги (`topic_id=doctors` + `service_id`) → список из `doctor_catalog.json` по явной связи service_ids, без «лучшего». Карточка врача (`content_ref=doctors__doctor__*.md`) → name/position/experience из каталога. Протоколы направления (`topic_id` + без service/content_ref) → только active `protocol`/`advanced_protocol` family (не CT/синус); до 3 options + до 2 secondary QR; без цены и без CTA. Контраст: ADMIN medical_terminal без directory. Contacts/CTA добраны в CP5-DIR-B. | `run_d2_dialogue_turn` → `core/d2_directory.py`; proof в `tests/test_d2_directory_scenarios.py` | Не затронуты `/ask`, `/ask/stream`, HTTP/SSE, widget, Composer, sales_fast | Overview команды, полный B12 UI matrix, HTTP/SSE/widget и live не доказаны | **PASS** | provider/live calls 0; hash в closeout |
| CP5-DIR-B — contacts + CTA free gate | Внутренний common D2 route: `kind=contact` → факты из `clinic_policies.yaml` contact текущего tenant (phone/address/…), call-кнопка + `canonical_contact`, `terminal_state=none` (не locks contacts). Список врачей услуги получает одну CTA; подпись «бесплатн…» только если fact `free_implant_consult` flag-active **и** в окне `active_from`/`active_until` на `as_of=now.date()` (иначе tone `doctor`/`booking`). Протоколы и medical_terminal без CTA. Не полный B12. | `run_d2_dialogue_turn` → `core/d2_contacts_cta.py` / `d2_directory.py`; proof в `tests/test_d2_directory_ui_scenarios.py` | Не затронуты `/ask`, `/ask/stream`, HTTP/SSE, widget, Composer, sales_fast | Полный B12 (source UI matrix, overview команды), HTTP/SSE/widget и live не доказаны | **PASS** | `0e0c02e`; provider/live calls 0 |
| CP5-B12 — CTA source/default/free matrix | Внутренний common D2 route: один offline набор B12. Source — md `cta_key`/`cta_action` → tone label (pain→`consult`, без «бесплатн»); secondary ≤2 (video+QR). Default — overview volume QR, затем «Не знаю» → одна CTA `price` (A07). Free — doctors list: free book_label внутри `active_until`, tone doctor после expiry. Forbid — pure CLARIFY (guided QR, 0 CTA); medical_terminal и spam_warn без CTA. Не полный click-wire виджета. | `run_d2_dialogue_turn` + existing materializer/directory/spam; proof в `tests/test_d2_ui_b12_scenarios.py` | Не затронуты `/ask`, `/ask/stream`, HTTP/SSE, widget, Composer, sales_fast | Widget click replay, HTTP/SSE/widget и live не доказаны | **PASS** | `95e81af`; provider/live calls 0 |
| CP5-OTOV — off-topic refuse + doctors overview | Внутренний common D2 route: (1) D2-040 polite refuse — typed `kind=other` без clinic ids → authored `ui.yaml` fallback_menu.offtopic (proof: unique tenant mark, не code default); `terminal_state=none`, без CTA; garbage по-прежнему spam_warn до provider; medical не offtopic. (2) Overview команды — `content_ref=doctors__doctor__overview.md` через content lookup (не directory card); текст из md/prose, CTA `booking` из frontmatter; без «лучш» и без списка имён каталога. | `run_d2_dialogue_turn` → `core/d2_offtopic.py` / content materializer; proof в `tests/test_d2_offtopic_overview_scenarios.py` | Не затронуты `/ask`, `/ask/stream`, HTTP/SSE, widget, Composer, sales_fast | Wrong keyboard layout, полный prompt offtopic live, HTTP/SSE/widget и live не доказаны | **PASS** | `66db042`; provider/live calls 0 |
| CP5-REG — общая offline регрессия assembled CP5 | В одном прогоне 16 assembled CP5-файлов: **100 passed, 0 failed**. На baseline `4f7ac07` ранее сообщалось 70 passed / 26 failed с остановкой на `session.current_session_client_id()`. CP5-LEAD требует probe tenant binding даже при `lead_bridge=False`, чтобы active lead не попал к provider; он не читает ordinary state. Восьми широким runtime sentinel разрешён только этот точный вызов `session`, любые `mem_get`/другие функции по-прежнему запрещены. После этого выявились 3 устаревших ожидания числа `project_d2_session_context`: ранний lead/spam gate и provider path делают по одной проекции на ordinary turn; ожидания уточнены без изменения остальных route counts. | Внутренний `run_d2_dialogue_turn` и `D2DialogueStore`; `tests/test_d2_dialogue_a08.py`, `test_d2_dialogue_b13.py` и 14 assembled scenario/test файлов из команды CP5-REG. Ordinary state/result принадлежит одному D2 store, PII/lead slots — существующему `session` owner | Не затронуты `/ask`, `/ask/stream`, widget; локальный legacy HTTP route остаётся активен | HTTP/SSE/widget, все полные A/B семьи, общий live provider, внешний lead transport; тесты не доказывают HTTP cutover | **PASS** — independent Cursor Checker, P0/P1 findings нет | Baseline `4f7ac07`; targeted A08/B13: 22 passed; aggregate: 100 passed, 2 `datetime.utcnow` deprecation warnings; provider/live/network calls 0; Checker report `23733e8b-f6a3-4451-bd0e-50e1e89b033f` |
| CP5-B04i — первая попытка двух информационных вопросов | Разные темы отвечались обе; классификация по различию service/topic ошибочно принимала два самостоятельных вопроса одной темы за сравнение. | Общий D2 route и materializer, без HTTP/widget | Legacy runtime не менялся | Отклонённая эвристика полностью заменена CP5-B04s | **REJECT** — Cursor Checker P1 | Content 5 passed; Checker воспроизвёл component foreign-source failure на чистом HEAD: baseline, не регрессия B04i; provider/live/network calls 0 |
| CP5-B04s — единое правило для двух материалов | Общий D2 route отвечает на оба вопроса независимо от совпадения topic/service. Materializer не классифицирует текстовый запрос как «сравнение»: любая пара content parts сохраняет оба ответа и не показывает follow-up/видео отдельных материалов; один готовый comparison md сохраняет свой UI. Отсутствующая вторая опора даёт честный пробел. | `core/d2_dialogue.py`, `core/response_plan_materialization.py`, `tests/test_d2_content_scenarios.py`, `tests/test_d2_independent_request_parts.py`, D2-042/072, B04 acceptance и target contract; raw fake provider → production parser → tenant snapshot → D2 store | `/ask`, `/ask/stream`, widget и legacy runtime не менялись | Живая модель и HTTP не проверены; точный выбор цены названного бренда B05 остаётся отдельной задачей | **PASS** — independent Cursor Checker, P0/P1 findings нет | Rejected P1 focused recheck: 6 passed; 16-файловый assembled offline набор: 105 passed; tenant/lead boundaries: 3 passed. Checker подтвердил foreign-source component failure на чистом HEAD: baseline, не регрессия. Provider/live/network calls 0; staging пуст; шесть foreign WIP файлов не затронуты. |
| CP5-B05 — бренд, страна и цена имплантации | Внутренний D2 принимает typed `brand_id`: один существующий документ объясняет Implantium/Impro/Nobel, каталог даёт страну, а price materializer фильтрует активные предложения только выбранного бренда. Общий вопрос показывает опубликованные примеры по разным объёмам; точная услуга без карточки нужного бренда даёт пробел без чужой цены и акции. Osstem получает уже утверждённый ответ из tenant policy по точному brand term; для неизвестного бренда/страны — честный пробел без утверждения «не ставим». | `run_d2_dialogue_turn` → production D1R parser → demo snapshot → materializer/renderer → один `D2DialogueStore`; fake provider в `tests/test_d2_brand_scenarios.py`; D2 provider prompt получает существующий brand catalog и implant systems md из snapshot | `/ask`, `/ask/stream`, widget и legacy runtime не менялись; новая ordinary memory не добавлена | Реальная модель не проверена: распознавание русских форм, выбор `brand_id` и качество прозы требуют отдельного разрешённого live-прогона; HTTP/widget не подключены. Сложные персональные вопросы B07 вне среза | **PASS** — независимый Cursor Checker, P0/P1 нет | B05: 9 passed; assembled CP5: 105 passed; lead/privacy: 10 passed. `tests/test_d2_demo_snapshot.py`: 7 passed, 2 известных component failure, не B05-регрессии. Provider/live/network calls 0, staging пуст; foreign WIP не затронут. |
| CP5-EDGE — короткая проверка перед `/ask` | A06: два ответа на составной вопрос, затем неоднозначная цена вызывает CLARIFY без подстановки услуги. A09: «3 зуба, обе челюсти» хранится как typed факт, цена остаётся с опубликованной единицей. B07: запрос об уже установленном в другой клинике импланте проходит через существующий общий документ о протезировании с осмотром/консультацией, без личного обещания совместимости в тестовом ответе. B02: typed неизвестный термин вызывает один вопрос о значении, повтор — честный пробел и консультацию. | `run_d2_dialogue_turn` → production parser → demo snapshot → один `D2DialogueStore`; `tests/test_d2_launch_edges.py`; B02 использует существующий `clarify_pending` без второй памяти. | HTTP/SSE/widget и legacy runtime не менялись; provider/live/network calls 0 | Fake-provider тест B07 доказывает route и опору на документ, но не гарантирует формулировку живой модели; полный B07 со стадией и всеми персональными вариантами вне среза. Общий `clarify_pending` после unrelated CLARIFY может сразу дать неизвестному термину честный gap; Checker счёл это допустимым fail-safe для узкого «дважды подряд». Для более точного поведения позже потребуется причина уточнения в том же D2 store. | **PASS** — независимый Cursor Checker, P0/P1 нет | Авторский focused: 4 passed; assembled CP5 + EDGE: 111 passed, 0 failed. Checker: focused 4 passed, tenant/lead/privacy 11 passed, независимо собранный CP5 + EDGE 109 passed. `git diff --check` чистый; staging пуст; шесть foreign WIP не затронуты. |
| CP6a — JSON `/ask` cutover | **ACCEPTANCE:** применимые C05/C07/C08/C09: настоящий POST `/ask` отдаёт сохранённые text/UI/actions одного D2 completion; replay после reopen store, payload conflict, два конкурентных хода, tenant isolation, invalid provider и отказ commit проверены. Старый ordinary context не импортируется, replay не делает повторный отбор после изменения tenant pack. Booking → name → pending question → phone остаётся у lead owner; PII нет в D2 ordinary store/provider, replay не обновляет effect receipt. Отказ commit на booking или телефон откатывает session lead state; телефон можно завершить при повторе. | **D2 ROUTE:** `app.ask` → `run_d2_ask_json` → `run_d2_dialogue_turn` → production D1R parser → tenant snapshot → один `D2DialogueStore`; fake provider, временные DB/logs/копия tenant pack и blocked network. | **LEGACY IMPACT:** `/ask` больше не вызывает Composer, sales_fast, legacy semantic selectors, старую ordinary memory или legacy finalizer; активный lead читается через узкий read-only probe. `/ask/stream` пока остаётся legacy. | **OWNER DECISION:** не требуется — это технический CP6a cutover по Execution Lock §4 и Delivery Roadmap. **FUTURE SCOPE:** CP6b SSE parity, CP6c widget action/retry wire, CP7 физическое удаление legacy. Внешняя доставка заявки не запускалась (локальный `demo_stub` receipt); live model и браузер не проверялись. | **PASS** — независимый Cursor Checker, P0/P1 нет | Focused HTTP: 10 passed; assembled HTTP + lead/tenant/A08/EDGE before added C07/freeze test: 46 passed, 0 failed. Wider D2 offline before rollback change: 330 passed, 2 unchanged component failures (`test_d2_independent_request_parts.py::test_foreign_content_source_fails_closed_without_neighbor_substitution`, `test_d2_multi_request.py::test_content_for_another_service_is_rejected`), оба повторены отдельно; их тесты и materializer не менялись от HEAD. `test_d2_demo_snapshot.py` и live-provider offline file исключены из wider run. Provider/live/network/SMTP calls 0; staging пуст. |
| CP6b — SSE `/ask/stream` cutover | **ACCEPTANCE:** применимые C05/C08/C09: настоящий SSE endpoint отдаёт тот же сохранённый D2 final text/UI/actions/state, что JSON `/ask`; replay в обе стороны без нового provider/effect. Обрыв после раннего status до работы не фиксирует ход; обрыв после commit до UI сохраняет результат для replay. Terminal выдаёт `ui`/`done`, invalid provider и отказ commit — один `error` без final UI/late write. Ошибка framing после commit возвращает `error`, сохранённый результат доступен для replay. Tenant/freeze/lead и endpoint sentinels проверены. | **D2 ROUTE:** `app.ask_stream` → `run_d2_ask_json` → `run_d2_dialogue_turn` → один `D2DialogueStore`; SSE только обрамляет сохранённый payload, не делает второго materialize/render. | **LEGACY IMPACT:** старый `orchestrate_sales_one_plus_ask_turn`, Composer/sales_fast, semantic selectors, ordinary memory и legacy finalizer больше не вызываются ни из JSON, ни из SSE normal path. Старые функции физически остаются до CP7. | **OWNER DECISION:** не требуется — техническое SSE подключение по Execution Lock §4 и Delivery Roadmap CP6b. **FUTURE SCOPE:** CP6c браузерный widget с typed action ownership/retry; CP7 удаление legacy; live model и внешняя доставка без отдельного разрешения не проверялись. | **PASS** — независимый Cursor Checker, P0/P1 нет | Focused HTTP/SSE: 19 passed; assembled HTTP/SSE + lead/tenant/A08/EDGE: 56 passed, 0 failed; временные DB/logs/tenant pack, network blocked, provider/live/SMTP calls 0; staging пуст. Известные component failures из CP6a в этом наборе не запускались. |
| CP6c — widget D2 wire и typed actions | **ACCEPTANCE:** применимые C04/C05/C08/C09/C10: настоящий `widget.js` читает сохранённые `answer`/`ui`/`revision` D2; scope и CTA клики отправляют `ref` + текущую `ui_revision`, старые/чужие/непоказанные refs отклоняются до provider/effect. Новый ход получает новый request ID; автоматический и ручной повтор после обрыва сохраняют ID и дают один bot bubble. CTA входит в существующий lead owner без provider; телефонный ход даёт один локальный `demo_stub` effect, replay не обновляет receipt. Terminal не получает CTA; быстрые ответы и видео взяты из реального D2 UI projection. | **D2 ROUTE:** `static/widget/widget.js` → `static/widget/api.js` → реальный `/ask/stream` → `run_d2_ask_json` → `run_d2_dialogue_turn` → один `D2DialogueStore`; store читает последнюю сохранённую UI projection для ownership, без второй ordinary memory или повторного render. | **LEGACY IMPACT:** widget больше не читает legacy `meta`/`quick_replies`/`cta` как authority, не посылает старые `cta_action`/`action`, не использует booking regex для маршрута и не вызывает старый `/reset`; Composer/sales_fast и fallback недостижимы из JSON/SSE normal endpoint. Физическое удаление старых helpers — CP7. | **OWNER DECISION:** не требуется: typed UI ownership и retry прямо заданы Delivery Roadmap CP6c, Execution Lock §4. **FUTURE SCOPE:** CP7 удаление legacy; CP8 итоговый regression/live evidence. Реальная модель, внешний lead delivery и браузерная проверка с живым provider не запускались. | **PASS** — независимый Cursor Checker, P0/P1 нет | Авторский assembled HTTP/widget + lead/tenant: 34 passed до TTL-кейса; финальный focused widget/HTTP/SSE/no-legacy после TTL-кейса: 22 passed. Chrome harness использует реальные D2 payload из offline Flask endpoint, page network только localhost; DB/logs/tenant pack временные, fake provider, live provider/SMTP 0. `git diff --check` чистый, staging пуст; шесть foreign WIP не затронуты. |
| CP7 — изоляция legacy semantic route | **ACCEPTANCE:** C08: из `app.py` удалены старые JSON/SSE orchestration handlers, worker, semantic imports и ordinary-memory writes; реальные `/ask` и `/ask/stream` продолжают работать только через `run_d2_ask_json`, `/lead` сохранён. Startup provenance указывает D2. Endpoint sentinels, HTTP и lead/privacy regressions проходят; прямой импорт `app` не загружает Composer, sales_fast, старый finalizer или прежний orchestration entry. | **D2 ROUTE:** `app.ask` / `app.ask_stream` → `core/d2_http_adapter.py` → общий `run_d2_dialogue_turn` и один D2 store. | **LEGACY IMPACT:** старый semantic route больше не существует как callable wiring в `app.py`. Исторические legacy модули и их unit/eval tests физически остаются в репозитории, но не загружаются и не вызываются из bot HTTP entry; это не fallback и не normal-dialogue механизм. | **OWNER DECISION:** не требуется: удаление прежнего entry wiring задано Delivery Roadmap CP7 и Execution Lock §2–3. **FUTURE SCOPE:** CP8 итоговые offline/live evidence и качество модели; merge/deploy вне D2 rebuild. Полная уборка исторических файлов вне текущего функционального удаления маршрута. | Draft — ожидает independent Cursor Checker | Авторский focused endpoint/no-legacy/lead: 29 passed, 0 failed; health/widget-config/lead transport smoke: 3 passed; `app` import legacy-loaded `[]`; provider/live/network/SMTP calls 0; staging пуст, foreign WIP не затронуты. |
| Current local runtime | JSON `/ask`, SSE `/ask/stream` и браузерный widget используют D2 result/wire; старый semantic entry wiring удалён из `app.py`. | `static/widget/widget.js` → `api.js` → `app.py` → `core/d2_http_adapter.py` → общий D2 turn | Исторические legacy файлы существуют, но normal path их не импортирует и не вызывает | CP8 итоговый evidence pack; полная уборка исторических файлов может выполняться отдельно без восстановления старого маршрута | — (сводка состояния) | CP7 uncommitted draft; независимый review ещё не проведён |
| D2-S1 — смысловой контракт | Один действительный FullContext prompt строится из полного captured MD corpus текущего tenant. Обычная живая проза живёт в `request_understanding[].content_text`: `patient_text=null`, отсутствующий либо форматно повреждённый `content_ref` не уничтожают пригодный ответ и не авторизуют source UI. Прямой typed `service_id` для цены не требует необязательный `topic_id`; session binder не выводит topic по тексту/label и D2 gate пропускает такой service к catalog-owned materializer. Пустая ordinary prose не становится completed answer. | `build_d2_d1r_messages` → raw fake provider → `parse_production_envelope_json` → `run_d2_dialogue_turn` → tenant snapshot/materializer/store; тест использует temporary tenant copy/DB/log и network block | Legacy Composer/sales_fast, semantic selectors, второй prompt/parser/state и fallback не добавлялись и не вызывались этим checkpoint | Live-понимание русских форм, UI/session memory следующего этапа, несколько цен и единый multipart plan не доказаны. Owner decision не требуется: применены T2 и C01 без нового visible rule. | Draft — ожидает focused recheck Checker | Авторский focused: `tests/test_d2_r1_contract.py` — 12 passed; provider/live/network calls 0; staging пуст до review. |
| D2-S2 — typed память и UI | Общий D2 state хранит до 3 bounded очищенных пар live model prose, typed click ref без label, отдельную typed задачу CLARIFY (`request_id`, kind, service, extent) и ordered D2 offer refs без цены/label/display text. TTL 30 минут не проецирует ordinary state и очищает D2 memory при следующем commit. | `run_d2_dialogue_turn` → один D1R prompt/parser → tenant snapshot/materializer → один `D2DialogueStore`; `core/d2_live_provider.py` передаёт context и selected ref в тот же prompt; fake provider/temporary DB/network block. | Composer/sales_fast, legacy ordinary memory, второй prompt/parser/state и fallback не добавлены. | Owner отдельно утвердил 3 пары, 1000 символов, TTL 30 минут и узкое offer state; price assembly, HTTP/SSE/widget wire, live provider и deploy вне этапа. | **PASS** — независимый Checker и Cursor review | `py_compile` и `git diff --check` проходят; полноценный pytest в текущем runtime пока недоступен (`pytest` и `yaml` отсутствуют). SQLite `data/` не тронута; staging пуст. |
| D2-S3 — exact-service prices and scope | Для точной услуги D2 materializer выбирает только ID из единственного tenant-authored direction order, отфильтрованные по typed service и extent, в исходном порядке и максимум три. All-on-4 demo order подтверждён владельцем: Impro → Implantium → Nobel. Нет или неоднозначность order дают безопасный published-price gap без catalog/legacy selector; no-public остаётся frozen row. Первая price part materialized, остальные deferred; state продолжает хранить лишь offer/service IDs и порядок. | `run_d2_dialogue_turn` → production D1R parser → temporary demo tenant copy → snapshot/materializer → один `D2DialogueStore`; raw fake provider, сеть заблокирована в тестах. | Composer/sales_fast, semantic/strategy selector, старый runtime, второй prompt/parser/state и fallback не добавлены. | HTTP/SSE/widget, mixed price+content assembly (этап 4), live provider, merge/deploy вне этапа. Полный pytest не запускался: в bundled runtime нет `pytest` и `yaml`; пакеты не устанавливались. | **PASS** — Independent Checker и Cursor recheck | `py_compile`, JSON parse и `git diff --check` проходят. `data/` и две debug SQLite не затронуты; staging пуст; commit/push не выполнялись. |

| D2-S4 — единый mixed response | Один common D2 turn сохраняет один frozen plan с FullContext prose и typed price/policy/contact parts; первая price part materialized, следующие deferred; unavailable price не стирает независимые content/contact. Exact blocks входят в pre-resolver plan, поэтому есть один final UI/render pass и нет post-freeze selection. JSON/SSE и browser widget получают сохранённые answer/UI. | production D1R parser → `run_d2_dialogue_turn` → tenant snapshot/materializer/pre-resolver → один `D2DialogueStore` → реальный `/ask`, `/ask/stream` и `d2_widget_harness.mjs`; raw fake provider, temporary tenant copy/DB/logs, сеть заблокирована. | Composer/sales_fast, legacy semantic selectors, ordinary memory, второй prompt/parser/state и fallback не добавляются. `app.py`, HTTP adapter и widget production wire не меняются. | Existing Target Contract §6–8 covers exact typed policy composition and partial unavailable price. После finding owner 2026-09-25 explicitly allowed `core/response_plan_resolver.py` only to move exact blocks before its final UI pass; any other allowlist expansion still requires owner decision. Live provider, full stage-5 matrix, merge/deploy and legacy deletion remain future scope. | **PASS** — независимый Checker и Cursor review | Targeted pytest: `test_d2_stage4_mixed_response.py`, `test_d2_http_contract.py`, `test_d2_widget_replay.py` — 14 passed. Fake provider, temporary tenant copy/DB/logs; provider/live calls 0. `git diff --check` чистый; staging был пуст до checkpoint. |

## Историческая фиксация прежних checkpoint

- Через внутренний common D2 route собраны **A08**, узкая часть **A10a**
  (same-topic price continuation), узкая часть **B13a** (одна простая
  опубликованная service price), **A02**, **A11**, **B08**, **A03**, **A04**,
  механизм сравнения **B04** и два независимых информационных вопроса B04s
  (focused recheck и Cursor PASS), **B15**, срез
  **A01/A07/TTL** (CP5-C2a), **A10 empty/switch + B11 person-change** (CP5-C2b;
  lead consent и полный B11 с заявкой не доказаны), multi-part **A05/A06/B14**
  (CP5-MP), availability/policy **B01/B10** (CP5-AP), D2-native recovery
  **B16/C02** (CP5-REC), terminal **B03** manual-contact (CP5-TERM), lead
  **A12** / D2-022 / D2-031 / D2-036 privacy bridge (CP5-LEAD; HTTP/SMTP и
  pause gray LLM не доказаны), и spam hard-stop **D2-040/071** consecutive
  garbage (CP5-SPAM; off-topic polite refuse вне среза), directory
  **B09** врачи/протоколы (CP5-DIR-A) и contacts + CTA free-gate
  (CP5-DIR-B), и UI CTA matrix **B12** source/default/free + forbid
  (CP5-B12), off-topic polite refuse и doctors overview content
  (CP5-OTOV). Это не
  означает готовность полного A10/B13 и не подключает HTTP/виджет.
- **Кроме перечисленных, никакие другие A01–A12 или B01–B17 не считаются
  собранными D2 пользовательскими сценариями.** Зелёные unit/seam-тесты
  деталей остаются доказательствами компонентов, не сценариев.
  Документационный marketing audit также не является assembled-сценарием.
- CP3 отдельно подтвердил A08 тем же внутренним entry с ограниченным live
  provider; это не HTTP и не виджет.
- CP1 доказал только prompt/parser contract для этого внутреннего A08; он не
  является live-проверкой модели и не подключил D2 к пользователю.
- Внутренние result replay и PII-free lead-effect receipt доказаны только CP4
  internal route. HTTP/SSE integration, реальный lead UI/transport и общий runtime
  **не начаты**. Live-проверка ограниченно доказана только для CP3 A08, не для
  общего runtime.

Owner widget smoke §24 — 2026-10-06: после предложенных сценариев владелец
сообщил «Вроде ок» и разрешил commit/push §23–24. Это owner smoke, не
полная REC-5/live quality аттестация. Далее — внешний вид виджета без
изменения архитектуры ответов. Foreign data/SIM0 в checkpoint не включать.

§36 audit group 4 — 2026-10-09, implementation checkpoint in progress.
Baseline 6381945. Ordinary contract excludes internal authorized explanation
state; verified source task retains its existing
explanation-only completion. Tests/Checker pending; provider/live/SMTP 0.
No commit/push. Foreign widget HTML/CSS, data/SIM0 excluded. This is structural
simplification, not proof of live model correctness or complete REC-5 acceptance.
Direct-price required target deferred because a null target may already execute
authored clinic policies; earlier rejection not approved. Price types/gate unchanged.
Final focused offline recheck: 64 passed, 124.89s, no failures/skips.
Preliminary wider selection: 93 passed, 330.64s, before price-scope correction.
Final evidence contract-boundary-final/results.xml; independent Checker PASS
for narrow §36, no blockers/test weakening; full group remains open.
No full-CI or live/widget acceptance; residual model-output errors stay open.
