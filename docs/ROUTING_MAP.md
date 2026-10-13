# Маршрутизация нынешнего D2

Текущий путь описан в [CURRENT_ARCHITECTURE](CURRENT_ARCHITECTURE.md).
Для /ask и /ask/stream владелец dialogue — core/d2_dialogue.py через
core/d2_http_adapter.py. Ordinary text/native price, frozen UI refs и lead/privacy
имеют действующие owners; old resolver/composer/playbook routes не запасной путь.

Историческая карта2026-07 с legacy route labels сохранена в
[архиве](archive/pre-d2/ROUTING_MAP.md). Она не задаёт нынешний порядок.
Полная приёмка всех веток не объявляется по этому документальному переносу.
