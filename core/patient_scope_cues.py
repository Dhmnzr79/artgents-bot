"""Shared patient/price scope cue patterns (price_scope, price_offers, patient_situation)."""

from __future__ import annotations

import re

from config import PRICE_LOOKUP_RE

# --- Implant / jaw / tooth (price_offers + price_scope) ---
IMPLANT_PRICE_RX = re.compile(r"имплант|импланат|implant", re.I | re.U)
JAW_EXPLICIT_RX = re.compile(
    r"all[\s-]?on|все\s+на|челюст|весь\s+зубной|полный\s+протез|all-on",
    re.I | re.U,
)
UPPER_JAW_RX = re.compile(
    r"верхн\w*\s+челюст|на\s+верхн\w*\s+челюст|сверху",
    re.I | re.U,
)
JAW_RESTORATION_RX = re.compile(
    r"в(?:ся|есь)\s+(?:верхн\w*\s+)?челюст|нет\s+зуб|восстанов|все\s+зуб",
    re.I | re.U,
)
ONE_TOOTH_EXPLICIT_RX = re.compile(
    r"один\s+(?:зуб|имплант)|1\s+зуб|one\s+tooth|одного\s+зуба|одним\s+зубом|одного\s+импланта",
    re.I | re.U,
)
FULL_ARCH_RX = re.compile(
    r"все\s+зуб|вставить\s+все|восстановить\s+все\s+зуб|полностью\s+зуб|весь\s+зубной",
    re.I | re.U,
)
CROWN_INCLUSION_RX = re.compile(
    r"коронк\w*.*(?:отдельн|входит|входят)|(?:отдельн|входит|входят).*коронк",
    re.I | re.U,
)
ONE_STAGE_PRICE_RX = re.compile(
    r"(?:удал\w*|удален\w*).{0,48}(?:сразу|одномомент|в\s+день).{0,48}имплант|"
    r"имплант.{0,48}(?:сразу|одномомент).{0,48}удал",
    re.I | re.U,
)
ALL_ON_4_ONLY_RX = re.compile(r"all[\s-]?on[\s-]?4|все\s+на\s+4", re.I | re.U)
ALL_ON_6_ONLY_RX = re.compile(r"all[\s-]?on[\s-]?6|все\s+на\s+6|all-on-6", re.I | re.U)
ALL_ON_6_RX = re.compile(r"all[\s-]?on[\s-]?6|все\s+на\s+6|all-on-6", re.I | re.U)

SCOPE_PRICE_RX = re.compile(
    r"(цена|стоимост|сколько\s+сто(?:ит|ят)|прайс|расценк|по\s+цене|сколько\s+будет|сколько\s+руб|сколько\s+обойд)",
    re.I | re.U,
)
ZYGOMATIC_RX = re.compile(r"скулов\w*|zygomatic", re.I | re.U)
PTERYGOID_RX = re.compile(r"птеригоид\w*|pterygoid", re.I | re.U)
ONE_TOOTH_SITUATION_RX = re.compile(
    r"нет\s+одн\w+\s+зуб|восстанов\w*\s+один\s+зуб|один\s+зуб\s+имплант",
    re.I | re.U,
)
PROSTHETIC_STAGE_RX = re.compile(
    r"уже\s+стоит\s+имплант|имплант\s+уже|коронк\w*\s+на\s+имплант",
    re.I | re.U,
)

# --- patient_situation-specific ---
CHOOSE_SOLUTION_RX = re.compile(
    r"(что\s+(?:мне\s+)?подойд|что\s+делать|как\s+лучше|какой\s+вариант|что\s+можно|чем\s+лучше|посовет\w*|что\s+дальше|с\s+чего\s+начать|как\s+быть)",
    re.I | re.U,
)
RESTORE_RX = re.compile(r"восстанов\w*|постав\w*|встав\w*|вернут\w*", re.I | re.U)
COMPARE_RX = re.compile(r"сравн|отличи|чем\s+лучше|или\s+лучше", re.I | re.U)
DOCTOR_RX = re.compile(r"врач|доктор|хирург|имплантолог", re.I | re.U)
WARRANTY_RX = re.compile(r"гарант", re.I | re.U)
FEW_TEETH_RX = re.compile(
    r"нескольк\w+\s+зуб|2\s+зуб|3\s+зуб|два\s+зуб|три\s+зуб|не\s+хватает\s+зуб",
    re.I | re.U,
)
ALL_TEETH_MISSING_RX = re.compile(
    r"нет\s+зуб\w*\s+вообще|нет\s+всех\s+зуб|без\s+зуб|зубов\s+нет|зубов\s+почти\s+не\s+осталось|полн\w*\s+зубн\w*\s+ряд",
    re.I | re.U,
)
FULL_JAW_RESTORE_RX = re.compile(
    r"восстанов\w*\s+(?:всю|всей)\s+челюсть|вся\s+челюсть|всю\s+челюсть",
    re.I | re.U,
)
UPPER_JAW_BONE_RX = re.compile(r"мало\s+кост\w*\s+сверху|кост\w*\s+на\s+верхн", re.I | re.U)
EXTRACTED_TOOTH_RX = re.compile(
    r"удалил\w*|удален\w*|выдернул\w*|шест[её]рк|седьм[её]рк|восьм[её]рк",
    re.I | re.U,
)
GAP_RX = re.compile(r"промежуток|пустое\s+место|щел|щель|диастем", re.I | re.U)
CHEW_SIDE_RX = re.compile(r"нечем\s+жевать|жевать\s+нечем|не\s+могу\s+жевать", re.I | re.U)
EXISTING_IMPLANT_RX = re.compile(
    r"уже\s+(?:стоит|вкручен|установлен)\s+имплант|имплант\s+уже|вкручен\w*\s+имплант",
    re.I | re.U,
)
CROWN_ON_IMPLANT_RX = re.compile(
    r"коронк\w*\s+на\s+имплант|протез\s+на\s+имплант\w*|абатмент",
    re.I | re.U,
)
BONE_DEFICIT_RX = re.compile(
    r"мало\s+кост|недостат\w*\s+кост|не\s+хватает\s+кост|кост\w*\s+мало",
    re.I | re.U,
)
SINUS_GRAFT_RX = re.compile(
    r"синус[\s-]?лифт|костн\w*\s+пластик|наращив\w*\s+кост|без\s+костн\w*\s+пластик",
    re.I | re.U,
)
EXTRACTION_IMPLANT_RX = re.compile(
    r"нужно\s+удал|удалить.{0,40}имплант|имплант.{0,40}удалить|сразу\s+после\s+удал",
    re.I | re.U,
)
URGENT_RX = re.compile(
    r"болит|боль\s+в\s+зуб|сломал\w*\s+зуб|треснул\w*\s+зуб|срочно|можно\s+сегодня|сегодня\s+можно|от[её]к",
    re.I | re.U,
)
GENERIC_IMPLANT_RX = re.compile(
    r"что\s+такое\s+имплант|виды\s+имплант|какие\s+есть\s+имплант|имплантаци\w*\s+—|хочу\s+имплант,\s+с\s+чего",
    re.I | re.U,
)
IMPLANT_INTEREST_RX = re.compile(r"имплант|имплантаци", re.I | re.U)
TOOTH_RX = re.compile(r"зуб", re.I | re.U)


def has_price_intent(text: str) -> bool:
    return bool(SCOPE_PRICE_RX.search(text) or PRICE_LOOKUP_RE.search(text))


def is_one_tooth_situation_cue(text: str) -> bool:
    return bool(ONE_TOOTH_EXPLICIT_RX.search(text) or ONE_TOOTH_SITUATION_RX.search(text))
