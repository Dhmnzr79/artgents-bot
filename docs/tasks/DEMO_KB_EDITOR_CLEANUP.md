# Demo KB: согласованная минимальная редакционная чистка

Классификация: редакционная чистка, не архитектурное упрощение. Основание: согласие владельца на бесспорные правки после аудита 2026-10-09.

**Цифры, факты, смыслы, офферы, обещания, медицинские формулировки, условия и исключения сохраняются строго. Их запрещено сглаживать или менять.**

## Baseline и границы

- Репозиторий: `C:/Cursor Projects/artgents-bot-active`.
- Ветка: `codex/model-price-experiment`; HEAD: `7c78ea3723042523ea3de489abfd10914d50a62c`.
- origin/main и merge-base: `efa3f773bcf10891e2997addf8bbec38c7ae1317`.
- Staging пуст. Существующий WIP: core/d2_live_provider.py, docs/tasks/DEMO_MODEL_PRICE_EXPERIMENT.md, docs/tasks/DEMO_KB_EDITOR_AGENT.md, docs/audits/DEMO_KB_EDITOR_AUDIT_2026-10-09.md; не изменять.
- Без provider/live/SMTP, commit/push/deploy.

## Точный allowlist

- `clients/demo/md/clinic__info__consultation.md`
- `clients/demo/md/clinic__info__contacts.md`
- `clients/demo/md/clinic__info__promo__free_implant_consult.md`
- `clients/demo/md/clinic__info__promo__implant_same_day_discount.md`
- `clients/demo/md/clinic__info__technology.md`
- `clients/demo/md/clinic__info__warranty.md`
- `clients/demo/md/comparison__all_on_4_vs_all_on_6.md`
- `clients/demo/md/comparison__bone_graft_vs_all_on_4.md`
- `clients/demo/md/comparison__classic_vs_one_stage.md`
- `clients/demo/md/comparison__implant_vs_bridge.md`
- `clients/demo/md/diagnostics__service__tomography.md`
- `clients/demo/md/doctors__doctor__fedorova.md`
- `clients/demo/md/doctors__doctor__grigoriev.md`
- `clients/demo/md/doctors__doctor__kuznetsov.md`
- `clients/demo/md/doctors__doctor__morozova.md`
- `clients/demo/md/doctors__doctor__orlov.md`
- `clients/demo/md/doctors__doctor__overview.md`
- `clients/demo/md/doctors__doctor__volkov.md`
- `clients/demo/md/extraction__service__tooth_extraction.md`
- `clients/demo/md/implantation__faq__duration.md`
- `clients/demo/md/implantation__faq__osseointegration.md`
- `clients/demo/md/implantation__faq__pain.md`
- `clients/demo/md/implantation__faq__safety.md`
- `clients/demo/md/implantation__faq__tooth_loss.md`
- `clients/demo/md/implantation__faq__tooth_one_day.md`
- `clients/demo/md/implantation__info__curator.md`
- `clients/demo/md/implantation__info__implant_systems.md`
- `clients/demo/md/implantation__info__methods_overview.md`
- `clients/demo/md/implantation__info__steps.md`
- `clients/demo/md/implantation__service__all_on_4.md`
- `clients/demo/md/implantation__service__all_on_6.md`
- `clients/demo/md/implantation__service__benefits.md`
- `clients/demo/md/implantation__service__bone_graft.md`
- `clients/demo/md/implantation__service__classic.md`
- `clients/demo/md/implantation__service__pterygoid_implants.md`
- `clients/demo/md/implantation__service__sinus_lift.md`
- `clients/demo/md/implantation__service__temporary_teeth.md`
- `clients/demo/md/implantation__service__zygomatic_implants.md`
- `clients/demo/md/orthodontics__service__aligners.md`
- `clients/demo/md/periodontology__service__periodontitis.md`
- `clients/demo/md/prosthetics__service__clasp_dentures.md`
- `clients/demo/md/prosthetics__service__implant_supported_prosthetics.md`
- `clients/demo/md/prosthetics__service__removable_dentures.md`
- `clients/demo/md/prosthetics__service__veneers.md`
- `clients/demo/md/prosthetics__service__zirconia_crowns.md`
- `clients/demo/md/treatment__service__caries.md`
- `clients/demo/md/treatment__service__pulpitis.md`
- `clients/demo/md/treatment__service__teeth_treatment.md`
- `clients/demo/md/whitening__service__teeth_whitening.md`
- `docs/tasks/DEMO_KB_EDITOR_CLEANUP.md`

## Согласованные изменения

Удаляются только 83 вхождения алиасов из списка «Убрать», которые буквально присутствуют в теле или заголовках своего документа (с нормализацией регистра, ё/е, пунктуации). Спорные алиасы и документ оплаты исключены. Никаких изменений каталогов услуг/брендов, JSON/YAML коммерческих данных.

- `clients/demo/md/clinic__info__consultation.md`: frontmatter: «план лечения».
- `clients/demo/md/clinic__info__contacts.md`: frontmatter: «контакты».
- `clients/demo/md/clinic__info__promo__free_implant_consult.md`: frontmatter: «бесплатная консультация по имплантации».
- `clients/demo/md/clinic__info__promo__implant_same_day_discount.md`: frontmatter: «скидка при оплате в день обращения».
- `clients/demo/md/clinic__info__technology.md`: frontmatter: «3d диагностика»; comment: «компьютерное планирование».
- `clients/demo/md/clinic__info__warranty.md`: frontmatter: «гарантия на импланты»; frontmatter: «пожизненная гарантия».
- `clients/demo/md/comparison__all_on_4_vs_all_on_6.md`: frontmatter: «all-on-4 или all-on-6».
- `clients/demo/md/comparison__bone_graft_vs_all_on_4.md`: frontmatter: «костная пластика или all-on-4».
- `clients/demo/md/comparison__classic_vs_one_stage.md`: frontmatter: «классическая или одномоментная имплантация».
- `clients/demo/md/comparison__implant_vs_bridge.md`: frontmatter: «имплант или мост».
- `clients/demo/md/diagnostics__service__tomography.md`: frontmatter: «готовое кт»; frontmatter: «свежее кт»; frontmatter: «нужно ли делать новое кт»; comment: «нужно ли делать новое кт».
- `clients/demo/md/doctors__doctor__fedorova.md`: frontmatter: «фёдорова ирина михайловна».
- `clients/demo/md/doctors__doctor__grigoriev.md`: frontmatter: «григорьев павел игоревич».
- `clients/demo/md/doctors__doctor__kuznetsov.md`: frontmatter: «кузнецов дмитрий андреевич».
- `clients/demo/md/doctors__doctor__morozova.md`: frontmatter: «морозова анна сергеевна».
- `clients/demo/md/doctors__doctor__orlov.md`: frontmatter: «орлов никита владимирович».
- `clients/demo/md/doctors__doctor__overview.md`: frontmatter: «наши врачи».
- `clients/demo/md/doctors__doctor__volkov.md`: frontmatter: «волков александр сергеевич».
- `clients/demo/md/implantation__faq__duration.md`: frontmatter: «срок имплантации»; comment: «можно ли ускорить имплантацию».
- `clients/demo/md/implantation__faq__osseointegration.md`: frontmatter: «приживаемость имплантов»; comment: «от чего зависит приживление».
- `clients/demo/md/implantation__faq__safety.md`: frontmatter: «стерильность при имплантации».
- `clients/demo/md/implantation__faq__tooth_loss.md`: frontmatter: «выпал зуб»; frontmatter: «выпал зуб что делать».
- `clients/demo/md/implantation__faq__tooth_one_day.md`: frontmatter: «имплантация за 1 день».
- `clients/demo/md/implantation__info__curator.md`: frontmatter: «персональный куратор».
- `clients/demo/md/implantation__info__implant_systems.md`: frontmatter: «виды имплантов».
- `clients/demo/md/implantation__info__methods_overview.md`: frontmatter: «виды имплантации».
- `clients/demo/md/implantation__info__steps.md`: frontmatter: «как проходит имплантация»; comment: «как проходит имплантация».
- `clients/demo/md/implantation__service__all_on_4.md`: frontmatter: «all-on-4»; comment: «кому подходит all-on-4».
- `clients/demo/md/implantation__service__all_on_6.md`: frontmatter: «all-on-6»; comment: «кому подходит all-on-6».
- `clients/demo/md/implantation__service__benefits.md`: frontmatter: «преимущества имплантации».
- `clients/demo/md/implantation__service__bone_graft.md`: frontmatter: «костная пластика»; comment: «скуловые импланты».
- `clients/demo/md/implantation__service__classic.md`: frontmatter: «классическая имплантация».
- `clients/demo/md/implantation__service__pterygoid_implants.md`: frontmatter: «птеригоидные импланты».
- `clients/demo/md/implantation__service__sinus_lift.md`: frontmatter: «когда нужен синус-лифтинг»; comment: «когда нужен синус-лифтинг».
- `clients/demo/md/implantation__service__temporary_teeth.md`: frontmatter: «временные зубы»; frontmatter: «временная коронка»; frontmatter: «временные зубы на имплантах».
- `clients/demo/md/implantation__service__zygomatic_implants.md`: frontmatter: «скуловая имплантация»; frontmatter: «скуловые импланты».
- `clients/demo/md/orthodontics__service__aligners.md`: frontmatter: «элайнеры»; frontmatter: «прозрачные капы»; comment: «что исправляют элайнеры».
- `clients/demo/md/periodontology__service__periodontitis.md`: frontmatter: «лечение пародонтита»; frontmatter: «пародонтит»; frontmatter: «воспаление десен».
- `clients/demo/md/prosthetics__service__clasp_dentures.md`: frontmatter: «бюгельные протезы»; frontmatter: «бюгельный протез».
- `clients/demo/md/prosthetics__service__implant_supported_prosthetics.md`: frontmatter: «протезирование на имплантах».
- `clients/demo/md/prosthetics__service__removable_dentures.md`: frontmatter: «съемное протезирование»; frontmatter: «съёмное протезирование»; frontmatter: «полный съемный протез»; comment: «частичный или полный протез»; comment: «протез натирает».
- `clients/demo/md/prosthetics__service__veneers.md`: frontmatter: «виниры»; frontmatter: «виниры e-max»; frontmatter: «накладки на зубы»; comment: «этапы установки виниров»; comment: «больно ли ставить виниры».
- `clients/demo/md/prosthetics__service__zirconia_crowns.md`: frontmatter: «коронки»; comment: «зуб сильно разрушен»; comment: «коронка на импланте».
- `clients/demo/md/treatment__service__caries.md`: frontmatter: «лечение кариеса»; frontmatter: «кариес»; frontmatter: «пломба».
- `clients/demo/md/treatment__service__pulpitis.md`: frontmatter: «лечение пульпита»; frontmatter: «пульпит»; frontmatter: «лечение каналов».
- `clients/demo/md/treatment__service__teeth_treatment.md`: frontmatter: «лечение зубов».
- `clients/demo/md/whitening__service__teeth_whitening.md`: frontmatter: «отбеливание зубов»; comment: «нужна ли чистка перед отбеливанием».

Дополнительно: убрать один повтор помощи куратора с организационными вопросами, сохранив это обещание во вводном абзаце; разбить плотный «Коротко» All-on-4 и боли при имплантации без изменения слов; уточнить четыре заголовка кнопок, сохранив anchor и suggest_h3.

**Любые остальные медицинские и коммерческие правки, слияние разделов, перестройка оплаты и удаление документов запрещены этим согласованием.**

## Проверки

Allowlist дополнен `tests/test_d2_document_click_task_http.py`: только точное ожидаемое название согласованного заголовка. Первый offline-прогон: 13 passed, 2 failed на старом названии кнопки pain (JSON/SSE), успешный runtime-ответ. Остальные assertions сохранены.

Ожидаются: точное сохранение текста кроме согласованных исключений, метаданных кроме aliases, всех anchor/suggest_h3/CTA/video; неизменность остальных файлов Demo и защищённого WIP; targeted offline tests; независимый Checker; git diff --check. Live-понимание модели этим не аттестуется.

## Результат 2026-10-09

- 49 MD, 83 вхождения aliases; экономия 2 194 символа. Четыре названия кнопок, два абзаца, один повторный пункт куратора.
- Preservation guard: PASS для всех 110 файлов Demo; остальной текст, anchors, metadata кроме aliases, защищённый WIP неизменны. Цены и другие JSON/YAML не менялись.
- `validate_client_pack(clients/demo)`: PASS, ошибок нет.
- Финальный targeted offline: 15 passed, 0 failed, 29.24s. Snapshot; document follow-up click/replay/next context; verified document task по JSON/SSE. JUnit: внешний `d2-stage1-5omr8j_3/kb-cleanup-final.xml`.
- Независимый Checker: PASS редакционного diff; focused PASS изменения ожидаемой подписи, без ослабления assertions.
- `git diff --check`: чист. Существующие DeprecationWarning datetime.utcnow() вне scope.
- Provider/live/SMTP: 0. Staging пуст; commit/push/merge/deploy не делались. Ветка и HEAD прежние; существующий WIP 2A и отчёт/роль сохранены.
- Остались: спорные алиасы, переработка оплаты и различающиеся обещания клиники; модельные цены не включены. Перед проверкой в виджете нужна «Новая беседа», поскольку изменился fingerprint базы.

## Дополнительное согласование: оплата и КТ — 2026-10-09

Владелец явно поручил переписать два документа: оплата — один чек-лист; КТ — два пункта. Редакционное сокращение, не архитектурное упрощение. Baseline: текущее дерево после предыдущей чистки, HEAD 7c78ea3, codex/model-price-experiment, origin/main и merge-base efa3f77; staging пуст.

Точный дополнительный allowlist:
- clients/demo/md/clinic__info__payment_terms.md
- clients/demo/md/diagnostics__service__tomography.md
- clients/demo/target_response/pricebook/facts.json — только четыре detail_ref оплаты на #korotko
- tests/test_bot_cleanup_1_offline.py — только ожидания этих ссылок
- tests/test_demo_md_commerce_cleanup_offline.py — только ожидания этих ссылок
- docs/tasks/DEMO_KB_EDITOR_CLEANUP.md

Оплата объединяет всю тему без дополнительных разделов. Все суммы, сроки, исключения, фиксация договора, налоговый вычет и сравнение планов сохранены. В КТ удалён повтор про свежесть снимка, подготовка включена в первый пункт; suggest_h3 пуст, дополнительных кнопок нет. Старые непубликуемые section aliases сохранены в HTML-комментариях. Удалённые anchors не оставлены фиктивными; четыре факта ведут на единый существующий #korotko. Тексты, суммы и применимость структурированных фактов неизменны. Остальной WIP вне allowlist сохраняется.

Проверки дополнения: validator PASS; targeted offline 5 passed, 0 failed (3.17s), snapshot и две точные проверки detail_ref; независимый Checker PASS. Файлы вне дополнительного scope побайтово неизменны. git diff --check чист, staging пуст. Первый запуск не собрал тест из-за неверного имени selection; исправленный прогон завершён. Provider/live/SMTP 0, commit/push/deploy не делались.

Перед checkpoint владелец отдельно поручил удалить три HTML-комментария aliases в документе КТ. Удалены только эти комментарии; aliases в шапке и два видимых пункта сохранены. Упоминание сохранённых комментариев выше описывает предыдущий промежуточный вариант.

Checkpoint объединяет согласованную чистку с ранее проверенным 2A и сохраняет роль/отчёт аудита. Авторизация владельца: commit и push в codex/model-price-experiment; без merge/deploy. Модельные ценовые ответы пока не включены.
