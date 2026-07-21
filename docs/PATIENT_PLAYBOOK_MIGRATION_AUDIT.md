# S14 — аудит переноса `patient_playbook.yaml`

**Baseline:** `73ec922 docs: govern patient playbook migration audit S14`

**Режим:** read-only audit. Этот документ не меняет ответы, данные клиента, target
schema, runtime или authority.

## Короткий вывод для владельца

`clients/demo/patient_playbook.yaml` — действующий конфигурационный файл текущей
архитектуры. Он действительно хранит приоритеты услуг и сейчас используется локальным
demo для ответов вида «какие варианты подойдут в моей ситуации?».

В новой архитектуре его нельзя ни выбросить, ни целиком скопировать в новый файл.
Current playbook одновременно хранит пять разных вещей:

1. признаки ситуации, при которых выбирается правило;
2. допустимость отдельных услуг;
3. коммерческий порядок услуг;
4. CTA и инструкции стилю ответа;
5. служебные `role`/`positioning` для LLM-контекста.

Target architecture разделяет эти обязанности. Значительная часть допустимости уже
перенесена в S11 service catalog. Приоритеты ещё нужно материализовать в
`clinic_strategy.yaml`, CTA — отдельно в target marketing policy. Перед этим требуется
зафиксировать правило разрешения пересекающихся strategy rules: frozen S1 model хранит
rules, но не определяет, как выбирать или объединять несколько совпадений.

Current playbook остаётся единственным product consumer. Ничего из S14 не подключено к
ответам.

## Что реально работает сейчас

Current loader читает две секции одного YAML:

- `rules` — основной composable selector;
- `patient_situations` — старый fallback по имени ситуации.

Основной selector:

1. проверяет current `kind/problem/extent/jaw/intent/modifiers`;
2. считает specificity: каждый обычный заполненный признак даёт один балл, каждый
   modifier — два;
3. выбирает совпавшее правило с наибольшим score;
4. при равном score сохраняет первое правило в authored order;
5. применяет `show_when`, доступность current service и `max_options`;
6. передаёт выбранные options, `role`, `positioning`, strategy label и style в current
   product flow.

Это подтверждено `core/patient_playbook.py` и current unit acceptance. Frozen target
strategy models такой resolver не содержат.

При S14 read-only прогоне выяснилось, что два current unit expectations уже расходятся
с фактическим кодом. Это не результат S14: client data, code и tests не менялись.

## Exact inventory

В current YAML ровно восемь основных rules:

1. `one_tooth_restore`;
2. `extraction_then_implant_restore`;
3. `few_teeth_restore`;
4. `existing_implant_prosthetic_stage`;
5. `full_arch_restore`;
6. `upper_full_arch_with_bone_deficit`;
7. `upper_full_arch_restore`;
8. `bone_deficit_solution`.

Отдельно существует ровно один fallback:

- `patient_situations.full_arch_missing`.

Fallback дословно повторяет `full_arch_restore` по `max_options`, CTA, strategy,
answer-style и четырём ordered options с priorities. Это current compatibility data,
а не основание удалить его до retirement текущего runtime.

## Карта владельцев полей

| Поле current playbook | Что оно делает сейчас | Target-владелец / решение |
|---|---|---|
| `rules[].id` | stable имя current правила и metadata | кандидат на stable target rule id |
| `match.extent`, `match.jaw` | нейтральные признаки ситуации | прямые target axes после проверки общей semantics |
| `match.kind`, `match.problem` | понятия current classifier | не копируются как новые target fields |
| `match.modifiers: bone_deficit` | current составной сигнал | кандидат `reported_context: reported_bone_deficit`, не автоматическая эквивалентность |
| `match.intent` | требует current `choose_solution` | planner/dialog concern, не источник допустимости strategy |
| `max_options` | ограничивает current result | target clinic strategy; значения `4` требуют approved cap `3` |
| `primary_cta` | CTA выбранного обзора | target marketing/CTA policy, не clinic strategy |
| `strategy` | current LLM/metadata label | отдельного frozen target field нет; rule id не следует дублировать без необходимости |
| `answer_style.max_options` | повторяет верхний limit | не становится вторым target source |
| `answer_style.mention_consult_ct` | инструкция current LLM context | marketing/content/CTA concern |
| `avoid_single_winner` | запрещает ложного единственного победителя | общий product guardrail, не priority data |
| `avoid_medical_promise` | запрещает медицинское обещание | общий product guardrail, не priority data |
| `options[].service_id/priority` | commercial order | кандидат `service_priorities` после applicability filtering |
| `options[].show_when` | дополнительная допустимость | S11 service/option selection; не strategy ranking |
| `options[].role/positioning` | служебная рамка current LLM | frozen target owner отсутствует; нельзя молча потерять или положить в ranking |

## Аудит каждого правила

### 1. `one_tooth_restore`

- Current match: `problem=missing_teeth`, `extent=one_tooth`.
- Current order: `classic: 100`, `one_stage: 80`.
- Current limit/CTA/label: `2`, `ct_consultation`, `one_tooth_implant_first`.
- Current special condition: `one_stage` только при `extraction_context`.
- Уже в S11: `classic` допускает one/few teeth; `one_stage` требует one/few teeth и
  `stage=extraction_context`.
- Candidate target match: `extent=one_tooth`.
- Граница: target не должен заново вводить `problem=missing_teeth`; нужно доказать, что
  applicability filtering не применит этот ranking к несвязанной one-tooth услуге.

### 2. `extraction_then_implant_restore`

- Current match: `kind=extraction_then_implant`.
- Current order: `one_stage: 100`, `classic: 80`, `tooth_extraction: 40`.
- Current limit/CTA/label: `3`, `ct_consultation`, `extraction_implant_ct_first`.
- Уже в S11: `one_stage` требует `stage=extraction_context`; `classic` имеет scope
  one/few teeth; `tooth_extraction` остаётся direct service.
- Candidate target match: `stage=extraction_context`.
- Граница: current `kind` одновременно выражает связку удаления и восстановления.
  Простая замена на stage не должна автоматически назначать удаление или имплантацию.

### 3. `few_teeth_restore`

- Current match: `problem=missing_teeth`, `extent=few_teeth`.
- Current order: `implant_supported_prosthetics: 100`, `classic: 80`,
  `clasp_dentures: 50`, `removable_dentures: 40`.
- Current limit/CTA/label: `4`, `ct_consultation`, `fixed_or_removable_by_defect`.
- Уже в S11: все четыре services имеют explicit extent coverage; implant-supported
  prosthetics требует `implant_placed`, clasp dentures — `natural_tooth_present`, а
  removable option `partial` — `few_teeth`.
- Candidate target match: `extent=few_teeth`.
- Граница: primary target result допускает максимум три options. Четвёртая current
  услуга не удаляется из каталога; следующий checkpoint должен определить shortlist и
  доступ к остальному списку без скрытой медицинской рекомендации.

### 4. `existing_implant_prosthetic_stage`

- Current match: `kind=existing_implant_prosthetic_stage`.
- Current order: `implant_supported_prosthetics: 100`, `zirconia_crowns: 60`,
  `temporary_teeth: 40`.
- Current limit/CTA/label: `3`, `consult`, `prosthetic_stage_first`.
- Уже в S11: все три services допускают `stage=implant_placed`; zirconia crowns также
  допускают natural tooth, temporary teeth — extraction context.
- Candidate target match: `stage=implant_placed`.
- Граница: mapping должен сохранить product-law «не продавать установку импланта
  повторно», но не считать наличие импланта медицинским выбором конкретной конструкции.

### 5. `full_arch_restore`

- Current match: `problem=missing_teeth`, `extent=full_arch`.
- Current order: `all_on_4: 100`, `all_on_6: 90`, `removable_dentures: 50`,
  `zygomatic_implants: 40`.
- Current limit/CTA/label: `4`, `ct_consultation`, `fixed_implant_first`.
- Current special condition: zygomatic option только при
  `bone_deficit_or_upper_jaw`.
- Уже в S11: All-on-4/6 и full removable option покрывают full arch; zygomatic service
  более строго требует full arch + upper jaw + reported bone deficit.
- Candidate target match: `extent=full_arch`.
- Граница: cap становится `3`; более строгая S11 eligibility важнее старого широкого
  `show_when` и не должна ослабляться strategy.

### 6. `upper_full_arch_with_bone_deficit`

- Current match: `problem=missing_teeth`, `extent=full_arch`, `jaw=upper`,
  `modifiers=[bone_deficit]`.
- Current order: `zygomatic_implants: 100`, `all_on_4: 90`, `all_on_6: 80`,
  `removable_dentures: 40`.
- Current limit/CTA/label: `4`, `ct_consultation`,
  `upper_jaw_complex_fixed_first`.
- Уже в S11: zygomatic service требует exact full arch + upper + reported deficit;
  остальные services остаются доступными только по своим selection conditions.
- Candidate target match: `extent=full_arch`, `jaw=upper`,
  `reported_context=reported_bone_deficit`.
- Граница: patient-reported context не равен медицински подтверждённому дефициту;
  strategy только сортирует уже допустимые услуги. Cap становится `3`.

### 7. `upper_full_arch_restore`

- Current match: `problem=missing_teeth`, `extent=full_arch`, `jaw=upper`.
- Current order: `all_on_4: 100`, `all_on_6: 90`, `zygomatic_implants: 70`,
  `removable_dentures: 40`.
- Current limit/CTA/label: `4`, `ct_consultation`, `upper_jaw_fixed_first`.
- Уже в S11: zygomatic service дополнительно требует reported deficit, поэтому один
  только upper-jaw context не делает её допустимой.
- Candidate target match: `extent=full_arch`, `jaw=upper`.
- Граница: current rule overlap с более specific bone-deficit rule должен получить
  deterministic target law; cap становится `3`.

### 8. `bone_deficit_solution`

- Current match: `modifiers=[bone_deficit]`, `intent=choose_solution`.
- Current order: `sinus_lift: 100`, `all_on_4: 80`, `zygomatic_implants: 70`.
- Current limit/CTA/label: `3`, `ct_consultation`, `bone_deficit_ct_first`.
- Уже в S11: sinus lift требует upper jaw + reported deficit; zygomatic additionally
  requires full arch; All-on-4 requires full arch.
- Candidate target fact: `reported_context=reported_bone_deficit`; `intent` остаётся у
  planner/dialog layer.
- Граница: target strategy не создаёт отдельный medical classifier/route и не решает,
  какая процедура пациенту подходит. Без достаточных selection facts список может быть
  короче, и это честнее current broad match.

## Где именно находятся четыре варианта

`max_options: 4` имеют четыре rules:

- `few_teeth_restore`;
- `full_arch_restore`;
- `upper_full_arch_with_bone_deficit`;
- `upper_full_arch_restore`.

То же значение имеет отдельный fallback `patient_situations.full_arch_missing`.
Target architecture уже ограничивает основной результат двумя-тремя вариантами, но S14
не выбирает, как показывать четвёртый вариант или какой из них исключать.

## Что уже перенесено offline

- S11: canonical service IDs, aliases, family/roles, active, content refs и coarse
  applicability selection для всех 21 услуг.
- S12: 31 offers, exact prices/units/packages, brands и commercial facts.
- S13: exact payment stages для 12 top offers.
- S7/S9: doctor profiles и exact service links.
- S10: pure common context `service → offers → doctors`.

Это данные и offline-связи. Они пока не заменяют current playbook в ответах.

## Что ещё не перенесено

1. Demo target `clinic_strategy.yaml`.
2. Demo target marketing policy и CTA mapping.
3. Resolver target strategy rules и закон пересечений.
4. Dialog-focus/product wiring и authority.
5. Явный target-owner для current `role`/`positioning`.
6. Current offer recommendation signals.

Последний пункт находится не в playbook, а в current pricebook. Сейчас ровно шесть
offers имеют `recommended=true`:

- `all_on_4.jaw.impro`;
- `all_on_6.jaw.impro`;
- `classic.one_tooth.impro`;
- `one_stage.one_tooth.impro`;
- `removable_dentures.jaw.partial`;
- `sinus_lift.one_site.closed`.

S12 правильно не сохранил `recommended` как ценовой факт: target architecture относит
порядок offers к clinic strategy. Их projection должен войти в будущий strategy TASK,
но не смешиваться с этим read-only audit.

## Неразрешённый gap target strategy

Frozen S1 contract задаёт форму rule и проверяет ссылки, limits и уникальные IDs. Он не
задаёт:

- применяется одно совпавшее правило или несколько;
- используется ли current specificity scoring;
- является ли authored order tie-breaker или precedence;
- складываются ли default и context priorities;
- какое значение имеет отсутствующий priority;
- как стабильно сортируются равные priorities;
- как явно названная услуга гарантированно обходит commercial ranking.

Архитектурный документ требует фильтровать applicability до strategy и уважать явно
названную услугу, но точного resolver algorithm для пересекающихся rules пока нет.
Следовательно, S14 не может честно объявить target strategy materialization готовой.

## Найденные current несоответствия

### Extraction rule проигрывает по specificity

`test_extraction_then_implant_prefers_one_stage_then_classic` ожидает rule
`extraction_then_implant_restore`. Фактически current detector также заполняет
`problem=missing_teeth` и `extent=one_tooth`:

- `extraction_then_implant_restore` получает specificity `1` за `kind`;
- `one_tooth_restore` получает specificity `2` за `problem + extent`.

По действующему algorithm выбирается `one_tooth_restore`. Изолированный тест
воспроизводит тот же результат. Это подтверждает, что overlap law нужно формализовать
до target materialization; S14 не меняет score, порядок rules или expected test.

### Fallback test отключает не оба источника

`test_no_playbook_returns_none` подменяет только `load_patient_playbook`, то есть старую
секцию `patient_situations`. Основной `load_patient_playbook_rules` остаётся активным и
выбирает `full_arch_restore`, поэтому result не равен `None`.

Изолированный тест воспроизводит failure. Для настоящей проверки отсутствующего
playbook нужно отдельно определить expected behavior при отсутствии обеих секций, но
правка protected current tests/core не входит в S14.

Итог read-only verification:

- `tests/test_patient_playbook.py`: `15 passed, 2 failed`;
- каждый из двух failures отдельно воспроизведён;
- `tests/test_demo_target_service_catalog.py`: `7 passed`;
- skip/xfail не использовались.

Аудит может быть завершён с красным current-result: его задача — честно выявить границу,
а не подогнать старые tests. Эти два несоответствия должны быть учтены в следующем
strategy-semantics governance TASK.

## S15 resolution status

S15 реализовал и независимо проверил недостающие semantics offline: explicit baseline
priorities, одно первое matching context rule поверх baseline, missing priority `0`,
stable ties и precedence явно названного уже допустимого candidate. Current specificity
не переносится, rules не merge-ятся, пустой catch-all rule запрещён.

Completion verification: resolver/contract `80 passed`, S2/S10 neighbors `38 passed`,
target data `15 passed`; product wiring отсутствует.

Это закрывает resolver gap, но ещё не материализует demo `clinic_strategy.yaml`, не
исправляет два current mismatch и не подключает target data к ответам. Следующий data
checkpoint сможет перенести audited service priorities и шесть current offer
recommendation signals. Target marketing/CTA migration остаётся отдельным этапом.

До отдельного authority checkpoint current `patient_playbook.yaml` продолжает управлять
локальным demo; A9 остаётся shadow-only.
