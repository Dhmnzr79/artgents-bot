# Текущая архитектура D2 demo

Срез 2026-10-13. Описывает существующий код, не обещает безошибочный выбор
моделью и не закрывает всю историческую SIM/REC приёмку. Старое описание
Composer/playbook/router сохранено в [архиве](archive/pre-d2/CURRENT_ARCHITECTURE.md).

## Общий путь

`app.py` /ask и /ask/stream → `core/d2_http_adapter.py` →
`core/d2_dialogue.py` → захваченный tenant snapshot и completed history →
`core/d2_live_provider.py` → текстовый protocol / native price tool →
кодовое исполнение операций → frozen answer/UI и durable completion/replay.
JSON/SSE — HTTP transport, не обязательная JSON-оболочка ответа модели.
Lead/privacy и опубликованные UI actions проверяются существующими владельцами.
Старые Composer/selectors/playbook не являются запасным обычным путём.

## Текст и контекст

Модель получает весь approved MD corpus выбранного клиента, актуальную историю
завершённых ответов и данные уже показанной карточки. Snapshot captures tenant
files; последующая правка диска не переписывает уже захваченные данные.
Canonical публичные контакты из `clinic_policies.yaml -> contact` разбирает
`core/clinic_contact_policies.py`; `core/d2_tenant_snapshot.py` передаёт их
в существующем `clinic_policy_catalog_json`. Адрес/метро, часы, парковка,
телефон/WhatsApp и branch binding не дублируются в contacts MD.
Policy IDs ссылаются через text_ref на authored MD, а не inline answer copies.

Обычный ответ — свободный текст. Optional `<D2_META>` actions/sources идут после
него отдельными строками. Непустая строка `{invalid` не structural JSON error:
в нынешнем protocol это prose. Это не разрешение обходить action/security guards.
Для обычного уточнения и вопроса о составе отдельные команды не требуются.

## Цена и интерактивные карточки

На обычном ходу `D2HttpProvider.generate` предоставляет native `show_price`
с tool_choice=auto. Модель определяет запрос и аргументы; код берёт только
утверждённые tenant price данные, materializes результат и карточку.
Предварительная prose перед tool call не публикуется как окончательный ответ.
`complete_price` получает фактический результат и пишет финальный текст;
на этом вызове tool_choice=none, повторная команда запрещена.
Оба вызова используют одну настроенную модель и каждый считается в quota.
При отсутствии tool карточка не обязана появиться; полезная prose сохраняется.
Модельные финансовые неточности остаются принятым остаточным риском;
это не повод добавлять classifier, semantic sanitizer или legacy fallback.

Табы/аккордеоны и проверенные price_select/price_detail clicks исполняются кодом
по опубликованным refs и revision. Сохраняемый direct UI price_detail не означает
возврата удалённой модельной ordinary price_detail. Факты выбранной карточки
доступны следующему диалогу. Подробнее ответственность —
[Target Contract §3](tasks/DEMO_D2_TARGET_CONTRACT.md).

## Контакты, заявки и безопасность

`show_contacts` остаётся code-owned способом показать exact контактные блоки;
это не единственный способ обычного разговора об адресе/парковке.
`start_booking` и существующие lead steps принимают имя/телефон и управляют
pause/resume/cancel. Intake PII не включается в ordinary model history.
Формат телефона и composer_input_mode — UI projection, не новая semantic память.
Demo заявка учебная; реальную доставку для конкретного tenant подтверждают отдельно.
Tenant isolation, forged/stale UI rejection, quota boundaries, transactional
commit/error и replay — действующие проверки, не legacy-долг для удаления.
Situation intake выключен; его старые действия не должны запускать модель/заявку.

## Модель и запуск

Согласованная модель — DeepSeek Flash:
`DEFAULT_LLM_MODEL=deepseek-flash`, `CHAT_BASE_URL=https://api.deepseek.com`,
`CHAT_API_KEY`. Код сохраняет legacy env aliases; clean environment имеет
Qwen default в config.py, это не автоматический fallback после ошибки DeepSeek.
Readiness разрешает точный api.deepseek.com, сохраняя HTTPS/credentials/query/fragment guards.
Секреты и .env не коммитятся. Native first/second response имеют одного provider owner.

Локальный запуск: [WORKFLOW_GIT](WORKFLOW_GIT.md), scripts/start_local_widget.ps1.
На VPS есть demo deployment; последний подтверждённый release8888fdd.
CI → Publish verified immutable Docker image → manual Deploy production.
Изменение локальных файлов или push topic branch само по себе VPS не обновляет.
Runtime fallback, миграцию пользователей и новые гарантии не предполагать.

## Проверки и остатки

[Текущий статус](tasks/DEMO_D2_CURRENT_STATUS.md),
[очередь](tasks/DEMO_D2_DELIVERY_ROADMAP.md),
[карточка чистки §60](tasks/DEMO_D2_INTERFACE_TASK.md#60-cleanup-checkpoint--2026-10-13).
Temporary demo gate не означает полный historical suite PASS. Полезные старые
tests мигрируются, проверки удалённых механизмов и доказанные дубли можно убрать.
KB cleanup/экономия context tokens и optional doctor/case UI — отдельно позже.
