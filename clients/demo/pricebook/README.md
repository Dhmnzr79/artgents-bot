# PriceBook v2 (demo)

Runtime читает `pricebook/services/*.json` **в первую очередь**; при отсутствии файла — fallback на `price_offers.json` / `prices.json`.

| Файл | Назначение |
|------|------------|
| `manifest.json` | Группы overview (имплантация, челюсть) |
| `facts.json` | Общие факты (`text_fact`, `render_mode`: strict \| natural) |
| `services/*.json` | Одна услуга = один файл |

Код: `core/pricebook_loader.py`, `core/price_answer_assembler.py`, lint: `scripts/lint_pricebook.py`.

Миграция legacy → services: `python scripts/migrate_pricebook_services.py`.

Спека: `docs/PRICEBOOK_V2.md`.
