# Подготовка контента вымышленного медцентра — owner GO 2026-10-16

## Полный редакторский рерайт — owner GO 2026-10-16

Продолжение medical content в текущем общем продукте, ветка codex/three-tabs-catalog.
Repo/top C:/Cursor Projects/artgents-bot-active. Baseline 758f0665968cc98961e88022ec741135d7fc85ad;
origin/main и merge base f7629491f2bb93ed80e2f58aea53770841bbd6a3.
Tracked/index чистые; foreign otzyv-1/2/3.jpg сохраняются.
Тип: контентная редактура, без архитектурного упрощения или runtime изменений.

Owner: переписать каждое описание АртМед живым продающим языком: польза,
результаты, сроки, ход процедуры, технология и клиника; ограничения только
содержательные и по делу. До 4 anchor-разделов включая korotko; 5 допустимы
лишь при необходимости. Разные структуры, каждый раздел — самостоятельная
полезная тема follow-up. Удалить язык прайса/интерфейса, отсылки к карточкам,
каталогу и извиняющиеся метакомментарии. Допускаются придуманные организационные
факты клиники; медицинские свойства/сроки сверяются по тематическим источникам.
Не подменять содержательную пользу универсальными гарантиями излечения.
Новое решение заменяет прежнее требование ссылаться в MD на ценовые карточки.

Scope: аудит всех 28 MD (21 услуга + 7 clinic info), полный рерайт; редактура
тех же публичных marketing body/text_fact без изменения цен, составов, сроков
акций, allowed refs или механизмов выбора. Metadata ownership/CTA сохраняются,
suggest_h3 указывают на существующие разделы. Прайс не дублируется в MD.
Текущий пользователь уже разрешил отдельного контент-агента в этом проекте;
исследование/редактура 10 aesthetic и 11 medical service docs делегируются
ранее созданным профильным агентам. Общие документы и финальный аудит — root.

Exact allowlist до редактирования:
- `docs/tasks/MEDICAL_DEMO_CONTENT_TASK.md`
- `docs/evidence/client_pack/MEDICAL_DEMO_CONTENT_REPORT.txt`
- `docs/evidence/client_pack/MEDICAL_DEMO_RESEARCH_MEDICAL.json`
- `docs/evidence/client_pack/MEDICAL_DEMO_RESEARCH_AESTHETIC.json`
- `docs/evidence/client_pack/MEDICAL_DEMO_RESEARCH_CLINIC.json`
- `clients/demo_medical/target_response/d2_commercial.json`
- `clients/demo_medical/target_response/pricebook/facts.json`
- `clients/demo_medical/md/cardiology__service__cardiology_consultation.md`
- `clients/demo_medical/md/cardiology__service__ecg.md`
- `clients/demo_medical/md/clinic__info__about.md`
- `clients/demo_medical/md/clinic__info__faq.md`
- `clients/demo_medical/md/clinic__info__first_visit.md`
- `clients/demo_medical/md/clinic__info__payment.md`
- `clients/demo_medical/md/clinic__info__promotions.md`
- `clients/demo_medical/md/clinic__info__quality.md`
- `clients/demo_medical/md/clinic__info__technology.md`
- `clients/demo_medical/md/cosmetology__service__biorevitalization.md`
- `clients/demo_medical/md/cosmetology__service__botulinum_therapy.md`
- `clients/demo_medical/md/cosmetology__service__laser_hair_removal.md`
- `clients/demo_medical/md/cosmetology__service__photorejuvenation.md`
- `clients/demo_medical/md/cosmetology__service__plasma_therapy.md`
- `clients/demo_medical/md/cosmetology__service__ultrasound_lifting.md`
- `clients/demo_medical/md/dermatology__service__dermatology_consultation.md`
- `clients/demo_medical/md/dermatology__service__digital_dermatoscopy.md`
- `clients/demo_medical/md/ent__service__ent_consultation.md`
- `clients/demo_medical/md/ent__service__ent_endoscopy.md`
- `clients/demo_medical/md/ent__service__nasal_lavage.md`
- `clients/demo_medical/md/general_medicine__service__therapist_consultation.md`
- `clients/demo_medical/md/gynecology__service__cervical_screening.md`
- `clients/demo_medical/md/gynecology__service__gynecology_consultation.md`
- `clients/demo_medical/md/neurology__service__neurology_consultation.md`
- `clients/demo_medical/md/pediatrics__service__pediatric_consultation.md`
- `clients/demo_medical/md/ultrasound__service__abdominal_ultrasound.md`
- `clients/demo_medical/md/ultrasound__service__thyroid_ultrasound.md`
- `clients/demo_medical/md/urology__service__urology_consultation.md`

Проверка: редакторское чтение каждого документа; ссылки/anchors/suggest_h3,
реальный D2 loader/validator и границы commercial refs без вызовов модели.
Один independent Checker из-за изменения структуры разделов и ссылок,
пропорциональный контенту, без D2 architecture audit/всего CI/browser.
No provider/SMTP/VPS/merge/deploy. Отчёт по каждому документу в существующем
MEDICAL_DEMO_CONTENT_REPORT.txt, research provenance вне model corpus.

Рерайт завершён: 28 MD, в каждом ровно4раздела включая korotko; новые56suggest
refs разрешаются. Каждый документ прочитан и разобран по пользе/результату/
срокам/процессу, индивидуальные замечания до→после в существующем report.txt.
Переписаны также6публичных marketing facts и2commercial body без изменений
scope/дат/цен/refs. Medical timing provenance отделена от придуманного сервиса.
Медицинские гарантии не добавлены, срок/эффект описаны содержательно, без
извиняющегося шаблона. Структурный check28MD/112sections/56refs и сохранности
metadata/marketing scope PASS; canonical client-pack validator PASS.
Independent Checker — PASS, P0/P1/P2 нет: прочитаны все28MD и marketing тексты,
сопоставлены45offers, validator и refs повторно проверены; выборочно подтверждены
медицинские сроки в первичных источниках. Provider/SMTP/VPS0. Checkpoint в той же
ветке/PR34; точный commit и push state в итоговом сообщении/Git log. Scope35путей,
foreign JPG сохраняются; индекс до review пуст. Full CI/browser/live не запускались.

## Историческая подготовка: тип и границы

Контент/документация, не runtime bug fix и не реализованное архитектурное упрощение.
Владелец разрешил вымышленную клинику, содержательные продающие описания,
демонстрационные факты, цены, акции, составы и условия. На каждую из 21 услуг
изучить минимум две тематические страницы клиник; исследование и редактуру
делегировать отдельным агентам. Подготовить также общую презентацию клиники.

Repository/Git root: C:/Cursor Projects/artgents-bot-active.
Ветка codex/medical-demo-content создана от freshly fetched origin/main
f7629491f2bb93ed80e2f58aea53770841bbd6a3. Handoff d2785c3 перенесён явно
cherry-pick commit cefb2ee. Рабочий baseline этого контент-этапа cefb2ee.
Индекс/отслеживаемые файлы перед этапом чистые, foreign otzyv-1/2/3.jpg не трогать.

## Контракт подготовки

Один canonical draft в clients/demo_medical/: 10 направлений, 21 услуга.
Данные из прототипа не являются отдельным прайсом и не импортируются вслепую.
Точные суммы, составы, отдельные расходы и оплата только в offers; числовые
условия акций в facts. MD объясняет услугу, опыт вымышленной клиники и FAQ,
ссылаясь на ценовую карточку без копии прайса. Источники исследования вынесены
в evidence и не загружаются в медицинский FullContext.

Честные ID новых категорий и единицы не маскировать зубами/челюстями/терапией.
Pack пока не регистрировать в routing/ALLOWED_CLIENTS. Схемную готовность на
старом dental enum не объявлять. Новые runtime/API/control fields не добавлять.
Не создавать старые marketing.yaml/clinic_strategy.yaml ради legacy validator.
Не создавать d2_direction_prices до удаления автоматических dental controls.
Пустой brand catalog допустим; реальные рейтинги/лицензии/премии не выдумывать.
По последующему решению владельца 2026-10-16 клиентская подача — обычная клиника «АртМед»: без маркировок вымышленности, демо и учебной формы. Происхождение данных фиксируется только в служебных материалах. Это редактура текста, без включения доставки заявок, платежей или подключения tenant.
Медицинские исходы/эффективность/безопасность не гарантировать; число посещений
в продаваемом пакете не равно назначенному курсу или обещанию результата.
Demo_stub, реальные контакты/SMTP/CRM/слоты/платежи отключены.
Существующие demo и nikadent, backend, widget и deployed VPS не изменяются.

## Уже согласованные решения интерфейса для следующего этапа

Общие три вкладки, история/позиция каталога/черновик сохраняются; browse не
меняет тему. Кнопки «Спросить об этой услуге» нет. Одна карточка по заполнению,
длинные варианты вертикальным списком, сначала варианты с ценами, детали после
выбора. No-public-price услуги видны. Точный выбор переносится в общую форму.
Нажатие заявки у другой услуги заменяет выбор, сохраняя контакты; просмотр нет.
В новом UI последовательный сбор контактов сообщениями заменяется формой.
Поля доступны сразу; пустая галочка согласия блокирует отправку, но не ввод;
галочка сама не отправляет, нужна кнопка. После success благодарность без
«Новой заявки». Начальная тема задаётся вручную настроенной страницей входа,
далее переходы по сайту не меняют разговор; эта возможность входит в первый
этап будущей реализации. Сейчас это контент, новые page-context поля не вводим.

## Проверки и приёмка

Прочитать итоговые MD, проверить отсутствие копий числового прайса, согласованную
клиентскую подачу, активные anchors/CTA, ссылки service/option/offer/fact/profile,
арифметику готовых этапов оплаты, 2 источника на услугу и синтаксис JSON/YAML.
Проверить отдельные offer/fact/commercial contracts; новые family/unit IDs
ожидаемо не проходят прежний dental enum и отражаются как blockers.
Один independent read-only Checker на завершённый контент-этап из-за broad
связей каталога/цен/маркетинга; никаких provider/SMTP/live тестов или всего CI.
Перед commit точные paths, staged names/stat/diff/diff-check. Topic push можно;
merge/deploy не разрешены. Не объявлять runtime-readiness, offline данные не
доказывают живой диалог/работу нового каталога.

## Точный allowlist записи

- `clients/demo_medical/README.md`
- `clients/demo_medical/brand.yaml`
- `clients/demo_medical/features.yaml`
- `clients/demo_medical/lead_config.yaml`
- `clients/demo_medical/tone.yaml`
- `clients/demo_medical/ui.yaml`
- `clients/demo_medical/widget_config.json`
- `clients/demo_medical/widget_integration.json`
- `clients/demo_medical/clinic_policies.yaml`
- `clients/demo_medical/target_response/service_catalog.json`
- `clients/demo_medical/target_response/brand_catalog.json`
- `clients/demo_medical/target_response/d2_commercial.json`
- `clients/demo_medical/target_response/pricebook/facts.json`
- `clients/demo_medical/md/ent__service__ent_consultation.md`
- `clients/demo_medical/md/ent__service__ent_endoscopy.md`
- `clients/demo_medical/md/ent__service__nasal_lavage.md`
- `clients/demo_medical/md/general_medicine__service__therapist_consultation.md`
- `clients/demo_medical/md/pediatrics__service__pediatric_consultation.md`
- `clients/demo_medical/md/gynecology__service__gynecology_consultation.md`
- `clients/demo_medical/md/gynecology__service__cervical_screening.md`
- `clients/demo_medical/md/urology__service__urology_consultation.md`
- `clients/demo_medical/md/cardiology__service__cardiology_consultation.md`
- `clients/demo_medical/md/cardiology__service__ecg.md`
- `clients/demo_medical/md/neurology__service__neurology_consultation.md`
- `clients/demo_medical/md/ultrasound__service__abdominal_ultrasound.md`
- `clients/demo_medical/md/ultrasound__service__thyroid_ultrasound.md`
- `clients/demo_medical/md/dermatology__service__dermatology_consultation.md`
- `clients/demo_medical/md/dermatology__service__digital_dermatoscopy.md`
- `clients/demo_medical/md/cosmetology__service__biorevitalization.md`
- `clients/demo_medical/md/cosmetology__service__plasma_therapy.md`
- `clients/demo_medical/md/cosmetology__service__photorejuvenation.md`
- `clients/demo_medical/md/cosmetology__service__laser_hair_removal.md`
- `clients/demo_medical/md/cosmetology__service__ultrasound_lifting.md`
- `clients/demo_medical/md/cosmetology__service__botulinum_therapy.md`
- `clients/demo_medical/target_response/pricebook/services/ent_consultation.primary.json`
- `clients/demo_medical/target_response/pricebook/services/ent_consultation.repeat.json`
- `clients/demo_medical/target_response/pricebook/services/ent_endoscopy.default.json`
- `clients/demo_medical/target_response/pricebook/services/nasal_lavage.single.json`
- `clients/demo_medical/target_response/pricebook/services/nasal_lavage.three_visits.json`
- `clients/demo_medical/target_response/pricebook/services/therapist_consultation.primary.json`
- `clients/demo_medical/target_response/pricebook/services/therapist_consultation.repeat.json`
- `clients/demo_medical/target_response/pricebook/services/pediatric_consultation.primary.json`
- `clients/demo_medical/target_response/pricebook/services/pediatric_consultation.repeat.json`
- `clients/demo_medical/target_response/pricebook/services/gynecology_consultation.primary.json`
- `clients/demo_medical/target_response/pricebook/services/gynecology_consultation.repeat.json`
- `clients/demo_medical/target_response/pricebook/services/cervical_screening.basic.json`
- `clients/demo_medical/target_response/pricebook/services/cervical_screening.extended.json`
- `clients/demo_medical/target_response/pricebook/services/urology_consultation.primary.json`
- `clients/demo_medical/target_response/pricebook/services/urology_consultation.repeat.json`
- `clients/demo_medical/target_response/pricebook/services/cardiology_consultation.primary.json`
- `clients/demo_medical/target_response/pricebook/services/cardiology_consultation.with_ecg.json`
- `clients/demo_medical/target_response/pricebook/services/ecg.default.json`
- `clients/demo_medical/target_response/pricebook/services/neurology_consultation.primary.json`
- `clients/demo_medical/target_response/pricebook/services/neurology_consultation.repeat.json`
- `clients/demo_medical/target_response/pricebook/services/abdominal_ultrasound.standard.json`
- `clients/demo_medical/target_response/pricebook/services/abdominal_ultrasound.with_kidneys.json`
- `clients/demo_medical/target_response/pricebook/services/thyroid_ultrasound.standard.json`
- `clients/demo_medical/target_response/pricebook/services/thyroid_ultrasound.with_cervical_nodes.json`
- `clients/demo_medical/target_response/pricebook/services/dermatology_consultation.primary.json`
- `clients/demo_medical/target_response/pricebook/services/dermatology_consultation.repeat.json`
- `clients/demo_medical/target_response/pricebook/services/digital_dermatoscopy.one.json`
- `clients/demo_medical/target_response/pricebook/services/digital_dermatoscopy.three.json`
- `clients/demo_medical/target_response/pricebook/services/digital_dermatoscopy.extended.json`
- `clients/demo_medical/target_response/pricebook/services/biorevitalization.face.json`
- `clients/demo_medical/target_response/pricebook/services/biorevitalization.face_neck.json`
- `clients/demo_medical/target_response/pricebook/services/plasma_therapy.scalp.json`
- `clients/demo_medical/target_response/pricebook/services/plasma_therapy.face.json`
- `clients/demo_medical/target_response/pricebook/services/plasma_therapy.three_visits.json`
- `clients/demo_medical/target_response/pricebook/services/photorejuvenation.face.json`
- `clients/demo_medical/target_response/pricebook/services/photorejuvenation.face_neck.json`
- `clients/demo_medical/target_response/pricebook/services/photorejuvenation.hands.json`
- `clients/demo_medical/target_response/pricebook/services/laser_hair_removal.underarms.json`
- `clients/demo_medical/target_response/pricebook/services/laser_hair_removal.legs.json`
- `clients/demo_medical/target_response/pricebook/services/laser_hair_removal.three_zones.json`
- `clients/demo_medical/target_response/pricebook/services/ultrasound_lifting.face350.json`
- `clients/demo_medical/target_response/pricebook/services/ultrasound_lifting.face_neck500.json`
- `clients/demo_medical/target_response/pricebook/services/ultrasound_lifting.lower_face.json`
- `clients/demo_medical/target_response/pricebook/services/botulinum_therapy.unit.json`
- `clients/demo_medical/target_response/pricebook/services/botulinum_therapy.individual.json`
- `clients/demo_medical/md/clinic__info__about.md`
- `clients/demo_medical/md/clinic__info__technology.md`
- `clients/demo_medical/md/clinic__info__first_visit.md`
- `clients/demo_medical/md/clinic__info__payment.md`
- `clients/demo_medical/md/clinic__info__quality.md`
- `clients/demo_medical/md/clinic__info__promotions.md`
- `clients/demo_medical/md/clinic__info__faq.md`
- `docs/evidence/client_pack/MEDICAL_DEMO_RESEARCH_MEDICAL.json`
- `docs/evidence/client_pack/MEDICAL_DEMO_RESEARCH_AESTHETIC.json`
- `docs/evidence/client_pack/MEDICAL_DEMO_RESEARCH_CLINIC.json`
- `docs/evidence/client_pack/MEDICAL_DEMO_CONTENT_REPORT.txt`
- `docs/tasks/MEDICAL_DEMO_CONTENT_TASK.md`

Игнорируемые рабочие артефакты генерации/проверки допускаются только в drafts/medical-demo-content/; не stage.

## Итоговый checkpoint перед независимым review

Подготовлены все 91 файла allowlist: canonical draft, 28 MD, 45 offers, 6 facts,
профили, настройки demo_stub и 3 research evidence. Минимум два источника на
каждую услугу; всего 48 URL с исследованием презентации клиники и производителя.
Content checks PASS, четыре суммы этапов проверены. Текущий runtime loader
ожидаемо отвергает новые family/unit IDs; старый validator требует два legacy
файла, которые намеренно не создаём. Полный перечень blockers и границы доказательств:
docs/evidence/client_pack/MEDICAL_DEMO_CONTENT_REPORT.txt.
Ни backend/widget/routing, ни существующие клиентские данные не менялись.
Independent Astra Checker — PASS всего подготовленного контента. P2 про
ограничения в «Отдельно» исправлен в пяти offers; focused recheck — PASS.
Проверялся именно контент, runtime-readiness не заявлена.
