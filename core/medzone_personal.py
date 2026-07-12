"""Medzone-personal boundary: personal indication → hand-off, not reassurance.

Canonical guard for «у меня X, можно ли мне…» — uses ``TRIGGERS['indications']`` from config.
"""
from __future__ import annotations

import re

from config import TRIGGERS_COMPILED

_PERSONAL_CASE_RX = re.compile(
    r"(?:"
    r"у меня\s+"
    r"|мне\s+(?:диагностировали|поставили|назначили)\s+"
    r"|(?:имеется|есть)\s+(?:у меня\s+)?"
    r")",
    re.I | re.U,
)
_PERSONAL_CONDITION_RX = re.compile(
    r"(?:"
    r"пародонт|диабет|остеопороз|гипертон|онколог|беремен|"
    r"гепатит|вич|аутоиммун|ревматоид|хроническ"
    r")",
    re.I | re.U,
)


def is_medzone_personal(q: str) -> bool:
    """True when question is a personal indication case (medzone hand-off zone)."""
    text = (q or "").strip()
    if not text:
        return False
    if not TRIGGERS_COMPILED["indications"].search(text):
        return False
    if _PERSONAL_CASE_RX.search(text):
        return True
    if _PERSONAL_CONDITION_RX.search(text):
        return True
    return False
