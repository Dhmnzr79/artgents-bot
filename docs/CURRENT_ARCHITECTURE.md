# Текущая архитектура D2 demo

Срез 2026-10-15, deployed demo `e93cb12`. Описывает существующий код, не обещает безошибочный выбор
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

Первый документ в model `sources` — основной и единственный источник follow-up UI.
Остальные дают дополнительные факты; неверный основной не заменяется следующим.
Все claims проверяются. При документном клике задача и источник уже определены сервером.

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

## Локальная галерея demo

`static/widget/cases.js` содержит demo-only каталог All-on-4 и циркониевых коронок:
service/document связи, пути к `static/clients/demo/cases/` и тексты каждой фазы.
Это UI-данные, не model corpus и не общий механизм подключения новых tenants.
Общий `clients/demo/md/clinic__info__results.md` — краткий вводный документ.
Его точный проверенный quick reply виджет заменяет существующей локальной галереей.
Нет поиска ключевых слов в вопросе или нового model action для кейсов.

Меню, ссылки после услуги и authored results reply открывают тот же renderer.
Фото/описание меняются кнопками «До»/«После»; кейсы — стрелками/свайпом,
220 мс с reduced motion. Открытие/переключение галереи не вызывает модель.
Прямой results reply допускает повторный просмотр; обычные service offers скрывают
открытые кейсы. Новая серверная semantic memory о выбранном кейсе не добавлена.

Gallery CTA переносит опубликованный `ref`/`revision`, когда он есть. Без него
«Я хочу так же» отправляет обычный booking request существующему model/lead пути;
форма зависит от `start_booking`, не появляется принудительно при произвольной prose.
Current revision, pending/retry и active/paused lead guards сохраняются.
Локальный Inter использует 400–600; цены, заголовки и service names имеют 600
на desktop/touch. Размеры остаются CSS presentation, не свойством model response.

## Модель и запуск

Согласованная модель — DeepSeek Flash:
`DEFAULT_LLM_MODEL=deepseek-flash`, `CHAT_BASE_URL=https://api.deepseek.com`,
`CHAT_API_KEY`. Код сохраняет legacy env aliases; clean environment имеет
Qwen default в config.py, это не автоматический fallback после ошибки DeepSeek.
Readiness разрешает точный api.deepseek.com, сохраняя HTTPS/credentials/query/fragment guards.
Секреты и .env не коммитятся. Native first/second response имеют одного provider owner.

Локальный запуск: [WORKFLOW_GIT](WORKFLOW_GIT.md), scripts/start_local_widget.ps1.
На VPS есть demo deployment; последний подтверждённый release — `e93cb12`, PR #29 merged.
CI → Publish verified immutable Docker image → manual Deploy production.
Изменение локальных файлов или push topic branch само по себе VPS не обновляет.
Runtime fallback, миграцию пользователей и новые гарантии не предполагать.

## Проверки и остатки

[Текущий статус](tasks/DEMO_D2_CURRENT_STATUS.md),
[очередь](tasks/DEMO_D2_DELIVERY_ROADMAP.md),
[карточка закрытия §64](tasks/DEMO_D2_INTERFACE_TASK.md#64-release-handoff--2026-10-15).
Temporary demo gate не означает полный historical suite PASS. Полезные старые
tests мигрируются, проверки удалённых механизмов и доказанные дубли можно убрать.
Техническая KB cleanup/экономия tokens, doctor UI и общий multi-client gallery
отложены. Demo gallery уже реализована. Следующий отдельный этап — НикаДент,
сначала read-only аудит; существующая папка клиента не означает его готовность.
