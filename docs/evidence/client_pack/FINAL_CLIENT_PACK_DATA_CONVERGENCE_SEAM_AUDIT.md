# FINAL_CLIENT_PACK_DATA_CONVERGENCE — seam audit

**Дата:** 2026-07-26
**Baseline:** `codex/stage-a` @ `40ffc09`
**Режим checkpoint:** governance / docs / tests only
**Запрещено на этом checkpoint:** product implementation, удаление client data, LIVE, LLM, A9 tuning

## Итог

`clients/demo` пока нельзя считать идеальным шаблоном новой клиники. В pack одновременно
существуют старые и FullContext-наборы одних и тех же доменов:

| Домен | Старый источник | Канонический FullContext-источник |
|---|---|---|
| Услуги и aliases | `clients/demo/service_catalog.json` | `clients/demo/target_response/service_catalog.json` |
| Цены и состав пакетов | `clients/demo/pricebook/` | `clients/demo/target_response/pricebook/` |
| Commercial facts | `clients/demo/pricebook/facts.json` | `clients/demo/target_response/pricebook/facts.json` |
| Implant brands / aliases | `clients/demo/price_brand_aliases.json` | `clients/demo/target_response/brand_catalog.json` |
| Marketing policy | `clients/demo/marketing.yaml` | `clients/demo/target_response/marketing.yaml` |

Это не просто визуальный мусор. Planner и несколько pre-runtime helpers ещё читают старый
catalog/pricebook, а AC2/AC3, structured evidence, Composer и Verifier читают
`target_response`. Изменение только одного набора поэтому может дать разные представления
об услуге в разных частях одного turn.

Целевое состояние — **один authoring source на домен**. Для FullContext-доменов это
`clients/{client_id}/target_response/**`.

## Что является настоящим дубликатом

### 1. Два service catalog

Оба catalog содержат те же 21 `service_id`. Target catalog уже сохраняет:

- `title` как `name`;
- `aliases`;
- `active`;
- `md_entry_ref` как `content_ref`;
- дополнительные final-architecture поля `family`, `roles`, `selection`, `options`.

Старый catalog дополнительно содержит поля старого answer/price routing:

- `price_key`, `price_ref`, `price_display`;
- `response_mode`;
- `concern_ref`, `suggest_refs`;
- свободные `facts`.

Эти поля не должны переноситься механически:

- price routing теперь задаётся target offers, billing unit и AC2/AC3;
- response mode выводится из TurnFrame / ResponseStage;
- concern/marketing sources задаются governed KB/fact/doctor refs;
- Planner должен распознавать услугу, а не получать из catalog свободные медицинские или
  продающие утверждения.

### 2. Два pricebook

Старый `pricebook/services/*.json` хранит 21 агрегированную запись с `variants`.
Target pricebook хранит 31 атомарный offer с явными:

- `service_id`, option/brand;
- price mode, amount/range и `billing_unit`;
- package;
- payment stages;
- fact refs;
- follow-ups;
- `applies_to_extents`.

Target offers являются product authority для AC2/AC3 и evidence. Сохранение старого
pricebook ради Planner brand filters создаёт второй источник цен. Planner должен получать
разрешённые brands/groups из target bundle, а не загружать старые price records.

### 3. Два facts catalog

В обоих наборах находятся те же шесть fact IDs:

- `tax_deduction`;
- `installment_12`;
- `free_implant_consult`;
- `implant_warranty`;
- `implant_same_day_discount`;
- `professional_whitening_discount`.

Target facts сохраняют исходные `id`, `kind`, `text_fact`, `render_mode`, detail ref и
добавляют product applicability: `active`, dates, `allowed_service_ids`,
`allowed_topics`, `incompatible_with`.

### 4. Brand aliases

Старый `price_brand_aliases.json` нужен только legacy price helpers. Target
`brand_catalog.json` уже хранит canonical brand identity и aliases. Это единственный
допустимый источник product-brand metadata.

### 5. Две marketing policy

Старый root `marketing.yaml` содержит старые route/aspect restrictions, promo copies и
24 свободные строки `clinic_proof` / `consult_reasons`.

Ранее выполненный migration audit установил:

- promo ownership уже перенесён в target facts;
- scenario source pools представлены governed `kb:` / `doctor:` / `fact:` refs;
- CTA labels принадлежат `tone.yaml`;
- 24 свободные строки не имеют exact source в MD и не должны автоматически становиться
  grounded product facts;
- старые route/aspect поля не являются final FullContext law.

Поэтому эти свободные строки **осознанно retire**, а не копируются в новый schema.
Если клиника хочет использовать такой тезис, она должна опубликовать его в MD, doctor
catalog или typed fact.

## Активные readers старого набора

### Старый service catalog

| Reader | Текущая роль |
|---|---|
| `core/service_selector_llm.py` | compact catalog для единого Turn Planner |
| `query_selector.py` | service matching; модуль импортируется Planner helpers |
| `doctors_lookup.py` | topic availability и catalog matching в ingress helpers |
| `core/follow_up_rewrite.py` | service label / matching |
| `core/dialog_focus.py` | catalog matching через `query_selector` |
| `core/explicit_service.py` | legacy explicit-service matcher; активных product callers нет |
| `core/startup_check.py` | требует root catalog до запуска app |

### Старый pricebook

`core/turn_planner_llm.py` загружает старые services для allowed brand filters.
`core/startup_check.py` требует старую pricebook directory.

Кроме того, импорт `query_selector.py` подтягивает legacy price island:

- `core/pricebook_loader.py`;
- `core/price_offers.py`;
- `core/price_scope.py`;
- `core/price_followup.py`;
- `core/patient_situation.py`;
- `core/patient_situation_llm.py`;
- `core/patient_situation_routing.py`;
- `core/patient_situation_session.py`;
- `core/price_answer_assembler.py`;
- `core/marketing_loader.py`;
- `core/marketing_policy.py`;
- `core/promo_overview.py`.

Большая часть функций этого island больше не вызывается FullContext product path, но
модули остаются importable, тестируются и поддерживают неоднозначность authoring.

## Что не является дубликатом и остаётся

| Путь | Назначение |
|---|---|
| `brand.yaml` | clinic/widget identity, palette, avatar |
| `target_response/brand_catalog.json` | product brands (implant systems), не UI brand |
| `clinic_policies.yaml` | offered/not-offered, contacts, hours, ingress/guard policy |
| `target_response/clinic_strategy.yaml` | ranking применимых услуг/offers |
| `doctor_catalog.json` | structured doctors |
| `md/` | FullContext corpus |
| `features.yaml` | реальные runtime capabilities; orphan flags проверяются отдельно |
| `lead_config.yaml` | lead delivery/config |
| `tone.yaml` | tone и authored CTA variants |
| `ui.yaml` | authored UI labels/navigation |
| `video_catalog.yaml` | optional video catalog |
| `widget_config.json` | widget origins/layout capabilities |

## Каноническая структура новой клиники

```text
clients/{client_id}/
├── brand.yaml
├── clinic_policies.yaml
├── doctor_catalog.json
├── features.yaml
├── lead_config.yaml
├── md/
├── target_response/
│   ├── brand_catalog.json
│   ├── clinic_strategy.yaml
│   ├── marketing.yaml
│   ├── service_catalog.json
│   └── pricebook/
│       ├── facts.json
│       ├── family_prices.json       # optional
│       └── services/*.json
├── tone.yaml
├── ui.yaml
├── video_catalog.yaml              # optional
└── widget_config.json
```

`target_response` сохраняется как проверенный schema namespace. Переименование папки
ради косметики отклонено: оно не меняет authoring model, но затрагивает runtime,
fixtures и frozen evidence.

## План конвергенции

### Checkpoint A — reader convergence

1. Ввести один client-aware cached source target response bundle.
2. Перевести Planner compact catalog и brand filters на target bundle.
3. Перевести service matching, doctor topic check и follow-up labels на target services.
4. Перевести startup validation на полный canonical pack.
5. Убрать active product imports из `query_selector` и старого price island.
6. Доказать price/service/alias parity на demo и sparse second-client fixtures.

На A старые data files остаются read-only для delta/parity tests, но product readers
после переключения должны быть равны нулю.

### Checkpoint B — deletion and authoring closeout

1. Удалить четыре root legacy authorities:
   `service_catalog.json`, `pricebook/`, `marketing.yaml`,
   `price_brand_aliases.json`.
2. Удалить orphan loaders/contracts/scripts и legacy-only tests.
3. Удалить orphan config/session fields только если importer/writer audit подтверждает
   ноль product consumers.
4. Создать `docs/CLIENT_PACK_AUTHORING.md`: одно поле → один canonical path.
5. Сделать `_template` структурно совместимым с canonical validator.
6. Добавить offline `scripts/validate_client_pack.py` без network/LLM.
7. Прогнать focused, wide safe-offline, collect-only и frozen pins.

## Инварианты

- Rich demo price/service answers не меняются семантически.
- Exact prices, units, package, brands, dates и doctor links сохраняются.
- AC1 → AC2 → AC3, A9 authority, typed UI TurnFrame и light Verifier не меняются.
- Не создаётся новый selector или второй response pipeline.
- Shared target schema используется и Planner, и response runtime.
- Новая клиника не обязана создавать legacy mirror-файлы.
- Missing/invalid canonical data fail closed на startup validation.
- Никаких demo `service_id` / brand / topic hardcodes в shared core.
- NO LIVE / NO LLM / NO A9 tuning.

## STOP law

Этот документ и governance TASK не разрешают implementation автоматически.
Checkpoint A начинается только после PRE-CODE PASS и отдельного owner GO.
Checkpoint B начинается только после A checker PASS, commit/push и отдельного owner GO.
