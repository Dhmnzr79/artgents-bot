# Тесты нынешнего D2 demo

Срез2026-10-13. Это фактический список владельцев и назначение проверок,
не обещание полного pytest tests/ PASS. Прежний target с не внедрёнными markers
и результатами старого baseline сохранён в
[архиве](archive/pre-d2/TEST_SUITE_ARCHITECTURE.md).

## Обязательный release gate

Точные списки — `.github/workflows/ci.yml` и `publish-image.yml`.
PR CI: offline-unit-and-contracts + demo-d1-clinic-policy-regression.
Имя второго job историческое; содержимое проверяет текущие D2/policy paths.
Publish verify использует union этих списков плюс G3 immutable image contract.
G2/G3 contract tests защищают обязательные файлы. Временный demo gate всё ещё
ограничен; его дальнейшее изменение — миграция useful assertions, не «все старые
тесты обратно» и не безусловное снятие проверки, потому что она красная.
Secret scan, lint/client validation, PostgreSQL qualification, Docker build/smoke
и deploy-coordinate/digest checks остаются независимыми обязательными слоями.

Основные current modules:

| Проверка | Назначение |
|---|---|
| test_d2_text_reply | Prose/META guards, frozen known-task binding, removed command rejection и отсутствие JSON response_format |
| test_d2_demo_release_gate | JSON/SSE, ordinary prose, nativeprice, booking/contact, tenant/PII/replay/commit/error guards |
| test_d2_native_price_runtime | native show_price и provider completion после фактической карточки |
| test_d2_contact_model_context | YAML→snapshot→обычный provider prompt, адрес/метро/часы/парковка, branch/tenant binding |
| test_d2_demo_session_budget | 30 model calls/session, включая второй price response |
| test_d2_demo_limits | Actual admission: replay/free click, daily/IP windows, atomic persistent counters, charged failures и сохранность lead при quota denial |
| test_d2_phone_mask | frozen phone projection и lead transitions/replay |
| test_d2_situation_disabled | obsolete actions отвергаются; old flags не вмешиваются в обычную речь/заявку; pause/resume и PII |
| test_d2_policy_text_refs | Authored MD/ref integrity, captured snapshot, price/booking refusals и published history |
| test_d2_af1b_contacts_http | Exact contacts, missing fields, mixed prose/replay, branch ownership и безопасный local gap |
| PG/privacy/G2–G8 | сохраняемые изоляция, persistence, security и безопасная выкладка |

Это не exhaustive список: workflows — источник actual selection.
Не суммировать PASS из пересекающихся PR/publish наборов как уникальные cases.

## Fixture protocol

Обычный fake response — текст; booking/contact/handoff actions — корректный
<D2_META> JSON block с opening/closing tags на отдельных строках.
Ценовой integration test использует native tool_calls show_price и отдельный
provider response с результатом кода; один старый envelope не эквивалентен этому.
Перед dependent assertions про profile/phone/UI проверять HTTP200, SSE error/done
и фактический lead step. Без этого зелёный тест может проверять не тот сценарий.
Fixtures пишут только temporary tenant copies и БД; реальные client packs не правят.
Реальный nikadent не сертифицирован как действующий клиент demo gate.

## Historical debt и удаления

Полезные tenant/privacy/quota/lead/replay/missing-data guards мигрировать.
Envelope/ordinary price_detail/doctor JSON/selector-only assertions отменённых
механизмов удалять после trace imports/callers и equivalent coverage check.
Дубли удалять при явном указании актуального теста, который их заменяет.
Карта и результат этапа — Interface Task §60; не скрывать failures через skip/xfail
или semantic runtime adapters. Historical artifact integrity не равна current
runtime compatibility и не разрешает возвращать удалённые поля/команды.

## Локальная проверка без provider calls

Использовать .venv Python, PYTHON_DOTENV_DISABLED=1 и dummy CHAT_API_KEY,
чтобы локальная .env не попала в offline fixtures/logs. pytest запускается на
точных файлах текущего изменения; перед merge — согласованный полный CI gate.
Wide historical tests/ запускать для инвентаризации с baseline comparison,
а не объявлять все старые падения regressions. Live provider/widget semantic
verification требует отдельного owner GO и hard call budget.

## Удаления §60.4

Удалены15 obsolete cases: обязательный HTTP json_object2, старые JSON prompt
examples6 и doctor-envelope7. Known-task binding/empty guards и отсутствие JSON
теперь проверяются текущим text protocol; removed doctors/META-price не исполняются.
Native price schema/arguments/transcript проверяет test_d2_native_price_runtime.
Historical strict probe budget/no-retry/no-secret safety остаётся; весь файл
structured_output не объявлен current или зелёным. Общие legacy helpers импортируются
другими suites, поэтому адресные удаления не превращены в массовый file deletion.
