# PriceBook v2 (demo)

**Demo:** единственный источник сумм — `pricebook/services/*.json`. Legacy `prices.json` / `price_offers.json` для demo удалены.

Runtime: PriceBook → при отсутствии entry fallback на `price_offers.json` / `prices.json` (другие клиенты).

| Файл | Назначение |
|------|------------|
| `manifest.json` | Группы overview (имплантация, челюсть) |
| `facts.json` | Общие факты (`text_fact`, `render_mode`: strict \| natural) |
| `services/*.json` | Одна услуга = один файл |

Код: `core/pricebook_loader.py`, `core/price_answer_assembler.py`, lint: `scripts/lint_pricebook.py`.

Миграция legacy → services: `python scripts/migrate_pricebook_services.py`.

Спека: `docs/PRICEBOOK_V2.md`.
