# NOT PROD — контент ЦЭСИ

**Статус:** временная копия demo-контента. **Не деплоить на боевой VPS** без замены маркеров ниже.

## Что ещё demo / вымышленное

| Маркер | Где | Заменить на |
|--------|-----|-------------|
| ~~видео~~ | `video_catalog.yaml` | **убрано на старт** — добавить, когда будет ролик |
| ~~all-on pricing md~~ | удалены | цены all-on нет — `clinic__info__payment_terms.md` |
| «бесплатная консультация» | md, fallback в коде | политика ЦЭСИ |

## Перед prod

1. Правки в `clients/cesi/md/`, prices, policies.
2. Пересборка `data/cesi/` (Phase M2).
3. `lead_config.yaml` — реальный email.
4. `widget_config.json` — `allowed_origins`: **dental41.ru** (и www).
5. Smoke 5–10 вопросов на стенде cesi.

См. `docs/MULTICLIENT.md` §15 и `docs/TECH_DEBT.md`.
