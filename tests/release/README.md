# Current release tests — PR и Publish

Эти два списка выбирают действующие проверки выкладки. Они читаются самим pytest
через `@file`; отдельного runtime, классификатора или test runner нет.

- `offline.txt` — PR job Offline unit and contracts.
- `policy.txt` — PR job Demo D1 clinic policy regression (имя историческое, protocol D2).
- Publish verify: объединение этих списков через `sort -u` плюс G3 image contract.

Не добавлять `tests/` целиком, flags, skip/xfail или старые suites ради их возраста.
Сначала проверить actual path и сохраняемый invariant: tenant/privacy, lead,
quota, native price, contacts/text_ref, persistence, commit/replay, deploy safety.
Assertions отменённых JSON/envelope/doctor/ordinary-detail механизмов не восстанавливать.
Остальные файлы tests/ не сертифицированы как нынешний release gate: там есть
historical probes и ещё не классифицированные guards. Красный тест не доказательство
runtime-регрессии; сравнивать с baseline. Не считать всё вне списка мусором.

Изменение списка — предмет review. G2–G8 и selection contract проверяют обязательные
защиты и совпадение списков. Secret scan, client validation, PostgreSQL qualification,
Docker build/smoke/publish и deploy остаются отдельными обязательными этапами.
Temporary demo coverage review ещё открыт; добавлять полезные guards после миграции,
а не возвращать historical suite целиком. Green gate не гарантирует все legacy tests PASS.

Локально offline без .env/provider: `python -m pytest -p no:cacheprovider @tests/release/offline.txt`.
Policy отдельно: `python -m pytest -p no:cacheprovider @tests/release/policy.txt`.
Перед запуском установить `PYTHON_DOTENV_DISABLED=1`; не использовать настоящие ключи.
Оба списка относятся к тестам, не к базе знаний клиента.
