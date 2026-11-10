# Demo: исходные замеры базы — 2026-11-01

Статус: инвентаризация и размеры сняты; содержательный аудит каждого файла ещё не выполнен.

Основа: текущий рабочий checkout `27e78ff`, включая прежнее изменение пустых строк в документе отбеливания. Рабочие файлы не изменялись. Полный SHA-256 каждого файла и машинные показатели — в [JSON](DEMO_KB_OPTIMIZATION_BASELINE_20261101.json). План — [дорожная карта](DEMO_KB_OPTIMIZATION_ROADMAP.md).

## Методика

Символы Unicode, включая пробелы; CRLF/CR нормализованы в LF. Байты и хеш — по исходным байтам. Шапка MD включает разделители и один перевод строки после закрывающего `---`; тело — весь остаток, без strip. Токены не измерены: нужен токенизатор выбранной версии модели и отдельный учёт сериализации messages/tools. Проценты символов нельзя выдавать за экономию денег. Исторический пример отбеливания считал тело с strip, поэтому его 1465 символов нельзя напрямую сопоставлять с неочищенным body этой таблицы.

## Итоги по группам

| Группа | Файлов | Символов | Байтов UTF-8 |
|---|---:|---:|---:|
| Client configuration | 9 | 11968 | 16800 |
| Repository auxiliary | 1 | 0 | 0 |
| MD | 61 | 85373 | 142108 |
| Catalogs and rules | 8 | 35359 | 41168 |
| Commercial facts | 1 | 9039 | 11357 |
| Pricebook offers | 33 | 37236 | 48418 |

## Части текущего модельного контекста

Замерены реальной сборкой snapshot/model_view, без вызова модели. Это отдельные блоки, а не полный оплачиваемый запрос. Их строки измерены как сериализует текущий runtime (включая исходные переводы строк MD), тогда как в файловой таблице переводы строк нормализованы. Не суммировать с размерами файлов как независимые расходы.

| Блок | Символов |
|---|---:|
| `approved_md_corpus` | 94360 |
| `service_reference_catalog` | 4357 |
| `active_service_catalog` | 1875 |
| `commercial_fact_catalog` | 7861 |
| `clinic_policy_catalog` | 876 |
| `brand_catalog` | 358 |
| `direction_prices` | 1146 |
| `D2_OPERATIONS_INSTRUCTIONS` | 10605 |

## Каждый файл

Все строки ниже требуют отдельного решения на этапе аудита: сохранить / сжать / объединить / исключить из модельной проекции / удалить после проверки ссылок. «—» означает неприменимо, а не ноль. Цена и интерфейс не проверены этой инвентаризацией.

| Путь от clients/demo | Символов | Шапка MD | Тело MD | Алиасов | H3 |
|---|---:|---:|---:|---:|---:|
| `brand.yaml` | 254 | — | — | — | — |
| `clinic_policies.yaml` | 1964 | — | — | — | — |
| `features.yaml` | 640 | — | — | — | — |
| `lead_config.yaml` | 126 | — | — | — | — |
| `md/.gitkeep` | 0 | — | — | — | — |
| `md/clinic__info__advantages.md` | 908 | 234 | 674 | 4 | 1 |
| `md/clinic__info__consultation.md` | 1085 | 360 | 725 | 7 | 1 |
| `md/clinic__info__contacts.md` | 372 | 242 | 130 | 6 | 1 |
| `md/clinic__info__first_visit.md` | 1471 | 240 | 1231 | 1 | 3 |
| `md/clinic__info__payment_terms.md` | 1192 | 366 | 826 | 9 | 1 |
| `md/clinic__info__policies.md` | 2147 | 223 | 1924 | 4 | 9 |
| `md/clinic__info__promo__free_implant_consult.md` | 766 | 232 | 534 | 2 | 1 |
| `md/clinic__info__promo__implant_same_day_discount.md` | 704 | 256 | 448 | 3 | 1 |
| `md/clinic__info__promo__professional_whitening_discount.md` | 702 | 263 | 439 | 3 | 1 |
| `md/clinic__info__results.md` | 605 | 189 | 416 | 2 | 2 |
| `md/clinic__info__technology.md` | 1670 | 409 | 1261 | 7 | 3 |
| `md/clinic__info__warranty.md` | 1686 | 276 | 1410 | 2 | 3 |
| `md/comparison__all_on_4_vs_all_on_6.md` | 2086 | 491 | 1595 | 6 | 4 |
| `md/comparison__bone_graft_vs_all_on_4.md` | 2241 | 386 | 1855 | 3 | 4 |
| `md/comparison__bugel_prosthesis_vs_fixed_bridge.md` | 1951 | 509 | 1442 | 5 | 4 |
| `md/comparison__classic_vs_one_stage.md` | 2094 | 436 | 1658 | 4 | 4 |
| `md/comparison__implant_vs_bridge.md` | 1566 | 343 | 1223 | 2 | 4 |
| `md/diagnostics__service__tomography.md` | 785 | 214 | 571 | 3 | 1 |
| `md/doctors__doctor__fedorova.md` | 869 | 428 | 441 | 4 | 1 |
| `md/doctors__doctor__grigoriev.md` | 804 | 356 | 448 | 3 | 1 |
| `md/doctors__doctor__kuznetsov.md` | 1195 | 505 | 690 | 3 | 1 |
| `md/doctors__doctor__morozova.md` | 776 | 335 | 441 | 3 | 1 |
| `md/doctors__doctor__orlov.md` | 970 | 396 | 574 | 3 | 1 |
| `md/doctors__doctor__overview.md` | 842 | 236 | 606 | 4 | 1 |
| `md/doctors__doctor__volkov.md` | 1140 | 522 | 618 | 4 | 1 |
| `md/extraction__service__tooth_extraction.md` | 1842 | 396 | 1446 | 6 | 4 |
| `md/implantation__faq__cost.md` | 1421 | 411 | 1010 | 6 | 2 |
| `md/implantation__faq__duration.md` | 2158 | 427 | 1731 | 5 | 3 |
| `md/implantation__faq__osseointegration.md` | 1915 | 424 | 1491 | 4 | 4 |
| `md/implantation__faq__pain.md` | 2398 | 375 | 2023 | 3 | 4 |
| `md/implantation__faq__safety.md` | 850 | 208 | 642 | 2 | 1 |
| `md/implantation__faq__tooth_loss.md` | 713 | 215 | 498 | 3 | 1 |
| `md/implantation__faq__tooth_one_day.md` | 908 | 293 | 615 | 4 | 1 |
| `md/implantation__faq__what_included.md` | 1771 | 315 | 1456 | 2 | 3 |
| `md/implantation__info__aftercare.md` | 1491 | 340 | 1151 | 3 | 3 |
| `md/implantation__info__contraindications.md` | 2240 | 363 | 1877 | 3 | 3 |
| `md/implantation__info__curator.md` | 705 | 256 | 449 | 4 | 1 |
| `md/implantation__info__implant_systems.md` | 1526 | 363 | 1163 | 4 | 4 |
| `md/implantation__info__methods_overview.md` | 1839 | 320 | 1519 | 4 | 2 |
| `md/implantation__info__steps.md` | 1491 | 385 | 1106 | 5 | 2 |
| `md/implantation__service__all_on_4.md` | 1796 | 312 | 1484 | 2 | 4 |
| `md/implantation__service__all_on_6.md` | 1806 | 301 | 1505 | 2 | 4 |
| `md/implantation__service__benefits.md` | 849 | 174 | 675 | 1 | 1 |
| `md/implantation__service__bone_graft.md` | 1943 | 457 | 1486 | 5 | 4 |
| `md/implantation__service__classic.md` | 1468 | 285 | 1183 | 2 | 3 |
| `md/implantation__service__one_stage.md` | 1351 | 306 | 1045 | 2 | 3 |
| `md/implantation__service__pterygoid_implants.md` | 1595 | 410 | 1185 | 4 | 4 |
| `md/implantation__service__sinus_lift.md` | 1884 | 320 | 1564 | 2 | 4 |
| `md/implantation__service__temporary_teeth.md` | 1891 | 485 | 1406 | 6 | 3 |
| `md/implantation__service__zygomatic_implants.md` | 1768 | 503 | 1265 | 7 | 4 |
| `md/orthodontics__service__aligners.md` | 1522 | 307 | 1215 | 4 | 3 |
| `md/periodontology__service__periodontitis.md` | 873 | 312 | 561 | 7 | 1 |
| `md/prosthetics__service__clasp_dentures.md` | 1321 | 336 | 985 | 4 | 3 |
| `md/prosthetics__service__implant_supported_prosthetics.md` | 1794 | 439 | 1355 | 6 | 3 |
| `md/prosthetics__service__removable_dentures.md` | 1651 | 486 | 1165 | 8 | 4 |
| `md/prosthetics__service__veneers.md` | 1243 | 258 | 985 | 2 | 3 |
| `md/prosthetics__service__zirconia_crowns.md` | 1701 | 385 | 1316 | 6 | 3 |
| `md/treatment__service__caries.md` | 1039 | 327 | 712 | 7 | 1 |
| `md/treatment__service__pulpitis.md` | 843 | 262 | 581 | 6 | 1 |
| `md/treatment__service__teeth_treatment.md` | 1311 | 291 | 1020 | 3 | 2 |
| `md/whitening__service__teeth_whitening.md` | 1829 | 362 | 1467 | 5 | 4 |
| `target_response/brand_catalog.json` | 516 | — | — | — | — |
| `target_response/clinic_strategy.yaml` | 2070 | — | — | — | — |
| `target_response/d2_commercial.json` | 1807 | — | — | — | — |
| `target_response/d2_direction_prices.json` | 2597 | — | — | — | — |
| `target_response/marketing.yaml` | 10707 | — | — | — | — |
| `target_response/price_microfacts.yaml` | 1039 | — | — | — | — |
| `target_response/pricebook/facts.json` | 9039 | — | — | — | — |
| `target_response/pricebook/services/aligners.default.json` | 784 | — | — | — | — |
| `target_response/pricebook/services/all_on_4.jaw.implantium.json` | 1775 | — | — | — | — |
| `target_response/pricebook/services/all_on_4.jaw.impro.json` | 1765 | — | — | — | — |
| `target_response/pricebook/services/all_on_4.jaw.nobel.json` | 1773 | — | — | — | — |
| `target_response/pricebook/services/all_on_6.jaw.implantium.json` | 1776 | — | — | — | — |
| `target_response/pricebook/services/all_on_6.jaw.impro.json` | 1766 | — | — | — | — |
| `target_response/pricebook/services/all_on_6.jaw.nobel.json` | 1774 | — | — | — | — |
| `target_response/pricebook/services/bone_graft.default.json` | 735 | — | — | — | — |
| `target_response/pricebook/services/caries.default.json` | 750 | — | — | — | — |
| `target_response/pricebook/services/clasp_dentures.default.json` | 704 | — | — | — | — |
| `target_response/pricebook/services/classic.one_tooth.implantium.json` | 1694 | — | — | — | — |
| `target_response/pricebook/services/classic.one_tooth.impro.json` | 1684 | — | — | — | — |
| `target_response/pricebook/services/classic.one_tooth.nobel.json` | 1693 | — | — | — | — |
| `target_response/pricebook/services/implant_supported_prosthetics.default.json` | 890 | — | — | — | — |
| `target_response/pricebook/services/one_stage.one_tooth.implantium.json` | 1830 | — | — | — | — |
| `target_response/pricebook/services/one_stage.one_tooth.impro.json` | 1820 | — | — | — | — |
| `target_response/pricebook/services/one_stage.one_tooth.nobel.json` | 1829 | — | — | — | — |
| `target_response/pricebook/services/periodontitis.default.json` | 703 | — | — | — | — |
| `target_response/pricebook/services/professional_whitening.default.json` | 802 | — | — | — | — |
| `target_response/pricebook/services/pterygoid_implants.default.json` | 765 | — | — | — | — |
| `target_response/pricebook/services/pulpitis.default.json` | 652 | — | — | — | — |
| `target_response/pricebook/services/removable_dentures.jaw.full.json` | 734 | — | — | — | — |
| `target_response/pricebook/services/removable_dentures.jaw.partial.json` | 740 | — | — | — | — |
| `target_response/pricebook/services/sinus_lift.one_site.closed.json` | 1017 | — | — | — | — |
| `target_response/pricebook/services/sinus_lift.one_site.open.json` | 996 | — | — | — | — |
| `target_response/pricebook/services/teeth_treatment.default.json` | 598 | — | — | — | — |
| `target_response/pricebook/services/temporary_teeth.default.json` | 807 | — | — | — | — |
| `target_response/pricebook/services/tomography.default.json` | 641 | — | — | — | — |
| `target_response/pricebook/services/tooth_extraction.complex.json` | 726 | — | — | — | — |
| `target_response/pricebook/services/tooth_extraction.default.json` | 603 | — | — | — | — |
| `target_response/pricebook/services/veneers.default.json` | 802 | — | — | — | — |
| `target_response/pricebook/services/zirconia_crowns.default.json` | 713 | — | — | — | — |
| `target_response/pricebook/services/zygomatic_implants.default.json` | 895 | — | — | — | — |
| `target_response/service_catalog.json` | 13340 | — | — | — | — |
| `target_response/widget_catalog.json` | 3283 | — | — | — | — |
| `tone.yaml` | 3194 | — | — | — | — |
| `ui.yaml` | 2276 | — | — | — | — |
| `video_catalog.yaml` | 228 | — | — | — | — |
| `widget_config.json` | 2967 | — | — | — | — |
| `widget_integration.json` | 319 | — | — | — | — |

## Сравнение после изменений

Исходный JSON не перезаписывать. После каждого законченного этапа создать отдельный after-снимок той же методикой и таблицу: старые пути → новые пути; символы/токены до и после; абсолютное и процентное изменение; сохранённые факты; перенаправленные ссылки; результаты проверки. Объединённые документы считать группой, не объявлять удалённый файл стопроцентной экономией при переносе его текста в другое место.
