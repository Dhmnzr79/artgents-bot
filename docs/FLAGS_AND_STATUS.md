# Конфигурация нынешнего D2 demo

Срез2026-10-13. [Архитектура](CURRENT_ARCHITECTURE.md),
[статус](tasks/DEMO_D2_CURRENT_STATUS.md). Старый registry Composer/Verifier,
S*/A9/performance экспериментов — [архив](archive/pre-d2/FLAGS_AND_STATUS.md).
Наличие старого имени в config.py не доказывает его чтение обычным D2 path.

| Настройка | Фактическое назначение |
|---|---|
| DEFAULT_LLM_MODEL | Одна модель D2 first/price-completion; согласовано deepseek-flash, clean default qwen3.8-flash |
| CHAT_BASE_URL | Явный endpoint; для DeepSeek https://api.deepseek.com; missing URL не повод подставлять провайдера |
| CHAT_API_KEY | Секрет из окружения; DASHSCOPE_API_KEY — legacy env alias |
| APP_ENV | local/prod; readiness проверяет transport, tenant config и persistence отдельно |
| D2_CLIENTS_ROOT | Корень captured tenant packs, offline fixtures используют temporary root |
| D2_DIALOGUE_DB_PATH | SQLite dialogue/completion store path; локальные БД не коммитятся |
| RATE_LIMIT_MAX_PER_IP / RATE_LIMIT_WINDOW_SEC | Demo admission per-IP cap/window, defaults40/60s |
| D2_FULL_AUDIT_LOG | Full audit default ON в local, OFF в prod; raw conversations не публикуются |

Session30 и daily400 model calls заданы в core/d2_demo_limits.py; это не env
переключатели. Каждый вызов provider, включая completion, расходует budget.
Полный список env и все auxiliary tools — не предмет этого короткого индекса.
Secrets/.env не входят в образ/Git. Topic push не выкладывает VPS; merge/publish/
deploy требуют согласованного процесса. Исторический production paragraph про
«только localhost» отменён фактом VPS demo, не гарантией real-user operation.
