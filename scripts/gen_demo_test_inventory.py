#!/usr/bin/env python3
"""One-off generator for docs/DEMO_TEST_INVENTORY.md"""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
md_dir = ROOT / "clients" / "demo" / "md"
pb_dir = ROOT / "clients" / "demo" / "pricebook" / "services"
policies_path = ROOT / "clients" / "demo" / "clinic_policies.yaml"
catalog = json.loads((ROOT / "clients" / "demo" / "service_catalog.json").read_text(encoding="utf-8"))

POLICY_LABELS = {
    "no_pediatric_dentistry": "Детская стоматология",
    "no_oms": "ОМС (бесплатное лечение по полису)",
    "no_dms": "ДМС (прямое страхование)",
}

fm_re = re.compile(r"^---\s*\n(.*?)\n---", re.S)
h3_re = re.compile(r"^###\s+(.+?)(?:\s*\{#([a-z0-9\-_]+)\})?\s*$", re.I | re.M)

TOPIC_LABELS = {
    "implantation": "Имплантация",
    "prosthetics": "Протезирование",
    "treatment": "Терапия (лечение зубов)",
    "extraction": "Удаление",
    "periodontology": "Пародонтология",
    "orthodontics": "Ортодонтия",
    "whitening": "Отбеливание",
    "clinic": "Клиника",
    "doctors": "Врачи",
}

topics: dict[str, list] = {}
for path in sorted(md_dir.glob("*.md")):
    text = path.read_text(encoding="utf-8")
    m = fm_re.match(text)
    fm = yaml.safe_load(m.group(1)) if m else {}
    topic = str(fm.get("topic") or "unknown")
    doc_id = str(fm.get("doc_id") or path.stem)
    doc_type = str(fm.get("doc_type") or "")
    body = text[m.end() :] if m else text
    chunks = []
    for hm in h3_re.finditer(body):
        title = hm.group(1).strip()
        aid = hm.group(2) or ""
        ref = f"{doc_id}.md#{aid}" if aid else f"{doc_id}.md"
        chunks.append({"id": aid, "title": title, "ref": ref})
    topics.setdefault(topic, []).append(
        {"doc_id": doc_id, "doc_type": doc_type, "file": path.name, "chunks": chunks}
    )

# prices
price_rows = []
for path in sorted(pb_dir.glob("*.json")):
    e = json.loads(path.read_text(encoding="utf-8"))
    sid = e["service_id"]
    cat = catalog.get(sid, {})
    title = cat.get("title") or e.get("display_name") or sid
    model = e.get("price_model")
    unit = e.get("default_unit")
    row = {
        "service_id": sid,
        "title": title,
        "model": model,
        "unit": unit,
        "md_entry_ref": cat.get("md_entry_ref"),
        "price_display": cat.get("price_display"),
        "concern_ref": cat.get("concern_ref"),
    }
    if model == "simple" and e.get("price"):
        p = e["price"]
        row["from_rub"] = p["value"]
        row["price_type"] = p["price_type"]
        row["note"] = p.get("note")
    if e.get("variants"):
        row["variants"] = [
            {
                "label": v["brand_label"],
                "unit": v["unit"],
                "total": v["total"],
                "recommended": v.get("recommended", False),
            }
            for v in e["variants"]
        ]
        row["from_rub"] = min(v["total"] for v in e["variants"])
    price_rows.append(row)

# catalog without md
no_md = [k for k, v in catalog.items() if v.get("active") and not v.get("md_entry_ref") and v.get("price_key")]

policies_raw = yaml.safe_load(policies_path.read_text(encoding="utf-8")) if policies_path.is_file() else {}
policies_map = policies_raw.get("policies") or {}
service_alts = policies_raw.get("service_alternatives") or []

def _one_line(text: str, limit: int = 100) -> str:
    s = " ".join(str(text or "").split())
    return s if len(s) <= limit else s[: limit - 1] + "…"

lines = [
    "# Demo — инвентарь контента и цен для тестов",
    "",
    "Автосгенерировано из `clients/demo/md/`, `clients/demo/pricebook/services/` и `clients/demo/clinic_policies.yaml`.",
    "Обновить: `python scripts/gen_demo_test_inventory.py`",
    "",
    "---",
    "",
    "## 1. Темы и чанки (md)",
    "",
    "Формат ref для eval: `{doc_id}.md#{anchor}`. Главный чанк почти всегда `#korotko`.",
    "",
]

for topic in sorted(topics.keys()):
    label = TOPIC_LABELS.get(topic, topic)
    docs = topics[topic]
    lines.append(f"### {label} (`topic: {topic}`) — {len(docs)} документов")
    lines.append("")
    for d in docs:
        lines.append(f"**{d['doc_id']}** · `{d['doc_type']}`")
        for c in d["chunks"]:
            aid = c["id"] or "—"
            lines.append(f"- `{aid}` — {c['title']}")
        lines.append("")

lines.extend(
    [
        "---",
        "",
        "## 2. Услуги с ценами (PriceBook)",
        "",
        "Источник: `clients/demo/pricebook/services/*.json`. Legacy `prices.json` удалён.",
        "",
        "| service_id | Название | Модель | Единица | от ₽ | Примечание |",
        "|------------|----------|--------|---------|------|------------|",
    ]
)

UNIT_RU = {
    "one_tooth": "1 зуб",
    "one_implant": "1 имплант",
    "one_site": "1 зона",
    "jaw": "1 челюсть",
    "full_mouth": "обе челюсти",
    None: "—",
}

for r in sorted(price_rows, key=lambda x: x["service_id"]):
    unit = UNIT_RU.get(r.get("unit"), r.get("unit") or "—")
    note = ""
    if r.get("variants"):
        parts = [f"{v['label']} {v['total']:,}".replace(",", " ") + " ₽" for v in r["variants"]]
        note = "; ".join(parts)
    elif r.get("note"):
        note = str(r["note"])[:60]
    from_rub = r.get("from_rub", "—")
    if isinstance(from_rub, int):
        from_rub = f"{from_rub:,}".replace(",", " ")
    lines.append(
        f"| `{r['service_id']}` | {r['title']} | {r['model']} | {unit} | {from_rub} | {note} |"
    )

lines.extend(
    [
        "",
        "### Complex — бренды имплантов (unit: 1 зуб под ключ)",
        "",
        "**classic**, **one_stage** — по 3 бренда:",
        "- Implantium — от 76 200 / 86 500 ₽",
        "- Impro (recommended) — от 85 200 / 96 500 ₽",
        "- Nobel Biocare — от 101 200 ₽",
        "",
        "### Complex — 1 челюсть (All-on)",
        "",
        "**all_on_4** — от 318 000 ₽ (Implantium) · **all_on_6** — от 398 000 ₽",
        "",
        "### Complex — варианты процедуры (не бренды)",
        "",
        "**sinus_lift** (`one_site`): закрытый 42 000 ₽ · открытый 68 000 ₽ — заголовок в ответе «Варианты», не «По брендам»",
        "",
        "**removable_dentures** (`jaw`): частичный 45 000 ₽ · полный 65 000 ₽",
        "",
        "---",
        "",
        "## 3. Что не делаем (`clinic_policies.yaml`)",
        "",
        "Источник: `clients/demo/clinic_policies.yaml`. Два механизма:",
        "- **Жёсткие политики** (`policies`) — ingress → `not_offered_policy`, готовый ответ без retrieval.",
        "- **Альтернативы услуг** (`service_alternatives`) — услуги нет в каталоге; ответ с пояснением + quick reply на `suggest_ref`.",
        "",
        "### Жёсткие политики (не делаем)",
        "",
        "| policy_key | Что не делаем | Триггеры в вопросе | Суть ответа |",
        "|------------|---------------|--------------------|-------------|",
    ]
)

for key, pol in policies_map.items():
    label = POLICY_LABELS.get(key, key)
    triggers = ", ".join(f"`{t}`" for t in (pol.get("triggers") or []))
    answer = _one_line(pol.get("answer") or "")
    lines.append(f"| `{key}` | {label} | {triggers} | {answer} |")

lines.extend(
    [
        "",
        "Примеры для eval (ingress): «Есть детский стоматолог?» → `no_pediatric_dentistry`; «по ОМС» → `no_oms`; «по ДМС» → `no_dms`.",
        "",
        "### Альтернативы (нет в каталоге → что предложить)",
        "",
        "| Ключевые слова | Не делаем | Предлагаем | suggest_ref |",
        "|----------------|-----------|------------|-------------|",
    ]
)

for alt in service_alts:
    kws = ", ".join(f"`{k}`" for k in (alt.get("match_keywords") or []))
    mention = alt.get("mention") or "—"
    note = _one_line(alt.get("note") or "")
    ref = alt.get("suggest_ref") or "—"
    lines.append(f"| {kws} | {note.split(';')[0] if note else '—'} | {mention} | `{ref}` |")

lines.extend(
    [
        "",
        "Примеры: «ставите брекеты» → не в каталоге, ответ про элайнеры + кнопка `orthodontics__service__aligners.md#korotko`.",
        "«базальная имплантация» / «мини-импланты» / «Osstem» — аналогично, свой `suggest_ref`.",
        "",
        "---",
        "",
        "## 4. Каталог без md (только facts + цена)",
        "",
    ]
)
for sid in no_md:
    v = catalog[sid]
    lines.append(f"- **{sid}** — {v.get('title')} · `price_display: {v.get('price_display')}` · facts-карточка")

lines.extend(
    [
        "",
        "---",
        "",
        "## 5. Нюансы для eval / smoke",
        "",
        "### Маршруты",
        "- **content** — вопрос без явной цены → один md-чанк + слоты",
        "- **price_lookup** — «сколько стоит…» → PriceBook (не md)",
        "- **price_concern** — «почему дорого» → `concern_ref` (обычно `implantation__faq__cost.md#korotko`)",
        "- **group_overview** — «сколько имплантация?» без протокола → manifest `implantation` (5 кнопок)",
        "- **price:classic** ref — widget quick reply → price_lookup без retrieval",
        "",
        "### Цены в ответе",
        "- Формат сумм: **`76 200 ₽`** (пробел thousands) — не `76200`",
        "- `price_display: always` — цена **дописывается** в конец контентного ответа (КТ, кариес, пульпит, лечение зубов)",
        "- Синус-лифтинг **не входит** в цену импланта «под ключ» — отдельная услуга",
        "",
        "### Конфликты / осторожно",
        "- Generic «сколько имплантация?» → overview, не classic",
        "- «All-on-4 на челюсть» → **all_on_4**, не group full_jaw",
        "- «сколько стоит вся верхняя челюсть» / «нет зубов на верхней» + цена → **upper_jaw** overview (All-on-4 + All-on-6, текст про КТ сверху)",
        "- «имплантация на челюсть» без «верхн» → **full_jaw** overview",
        "- Отбеливание: catalog `professional_whitening`, md `whitening__service__teeth_whitening`",
        "",
        "### Shared facts (pricebook/facts.json)",
        "- `installment_12`, `free_implant_consult`, `implant_warranty`, `tax_deduction` — могут дописываться к price-ответу",
        "- Рассрочка от 150 000 ₽ — в `clinic__info__payment_terms.md`, не в PriceBook",
        "",
        "### Чего нет в demo (см. также §3)",
        "- Жёсткие отказы: дети, ОМС, ДМС — только через `clinic_policies`, не через md",
        "- Брекеты, базальная/мини-имплантация, Osstem — альтернатива из §3",
        "- Legacy `*__pricing__*.md` удалены — цены только PriceBook",
        "",
    ]
)

out = ROOT / "docs" / "DEMO_TEST_INVENTORY.md"
out.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"wrote {out}")
