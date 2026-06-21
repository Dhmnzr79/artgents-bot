#!/usr/bin/env python3

"""One-shot migration: price_offers.json + prices.json → pricebook/services/*.json (demo)."""

from __future__ import annotations



import json

import sys

from pathlib import Path



ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:

    sys.path.insert(0, str(ROOT))



from contracts.price_offer import PriceOffersFile

from contracts.pricebook import PricebookServiceEntry, PriceVariant, SimplePrice, ServicePromo

from core.pricebook_loader import infer_brand_group



DEMO = ROOT / "clients" / "demo"

OUT = DEMO / "pricebook" / "services"



_IMPLANT_FOLLOWUPS = [

    {

        "label": "Что будет на консультации",

        "action": "md_ref",

        "ref": "clinic__info__consultation.md#korotko",

    },

    {"label": "Оплата по этапам", "action": "price_aspect", "aspect": "stages"},

    {"label": "Что входит", "action": "price_aspect", "aspect": "includes"},

]



_DISPLAY_NAMES = {

    "classic": "Классическая имплантация",

    "one_stage": "Одномоментная имплантация",

    "all_on_4": "All-on-4",

    "all_on_6": "All-on-6",

    "professional_whitening": "Профессиональное отбеливание",

    "pulpitis": "Лечение пульпита",

}



_DEFAULT_UNITS = {

    "classic": "one_tooth",

    "one_stage": "one_tooth",

    "all_on_4": "jaw",

    "all_on_6": "jaw",

}





def _variant_from_offer(offer) -> PriceVariant:

    return PriceVariant(

        offer_id=offer.offer_id,

        brand=offer.brand,

        brand_label=offer.brand_label,

        brand_group=infer_brand_group(offer.brand_label),

        unit=offer.unit,

        total=offer.total,

        currency=offer.currency,

        recommended=offer.recommended,

        payment_stages=list(offer.payment_stages),

        includes=list(offer.includes),

        excludes=list(offer.excludes),

    )





def migrate_complex(client_id: str = "demo") -> None:

    raw = json.loads((DEMO / "price_offers.json").read_text(encoding="utf-8"))

    parsed = PriceOffersFile.model_validate(raw)

    by_service: dict[str, list] = {}

    for offer in parsed.offers:

        by_service.setdefault(offer.service_id, []).append(offer)



    OUT.mkdir(parents=True, exist_ok=True)

    for sid, offers in sorted(by_service.items()):

        entry = PricebookServiceEntry(

            service_id=sid,

            price_model="complex",

            display_name=_DISPLAY_NAMES.get(sid, sid),

            default_unit=_DEFAULT_UNITS.get(sid),

            tags=["implantation"] if sid in _DEFAULT_UNITS else [],

            variants=[_variant_from_offer(o) for o in offers],

            fact_refs=["free_implant_consult"] if sid in {"classic", "one_stage", "all_on_4", "all_on_6"} else [],

            followups=_IMPLANT_FOLLOWUPS if sid in {"classic", "one_stage", "all_on_4", "all_on_6"} else [],

            cta_key="price",

        )

        path = OUT / f"{sid}.json"

        path.write_text(

            json.dumps(entry.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",

            encoding="utf-8",

        )

        print(f"wrote {path.relative_to(ROOT)}")





def migrate_simple() -> None:

    prices = json.loads((DEMO / "prices.json").read_text(encoding="utf-8"))

    OUT.mkdir(parents=True, exist_ok=True)



    whitening = prices.get("professional_whitening") or {}

    if whitening:

        entry = PricebookServiceEntry(

            service_id="professional_whitening",

            price_model="simple",

            display_name=_DISPLAY_NAMES["professional_whitening"],

            price=SimplePrice(

                price_type=whitening.get("price_type") or "from",

                value=int(whitening.get("value") or 0),

                note=whitening.get("note"),

            ),

            promo=ServicePromo(

                text="Сейчас на эту процедуру скидка 10% до 15 июля.",

                active_until="2026-07-15",

            ),

            fact_refs=["installment_12"],

            followups=[],

            cta_key="price",

        )

        path = OUT / "professional_whitening.json"

        path.write_text(

            json.dumps(entry.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",

            encoding="utf-8",

        )

        print(f"wrote {path.relative_to(ROOT)}")



    pulp = prices.get("pulpitis") or {}

    if pulp:

        entry = PricebookServiceEntry(

            service_id="pulpitis",

            price_model="simple",

            display_name=_DISPLAY_NAMES["pulpitis"],

            price=SimplePrice(

                price_type=pulp.get("price_type") or "from",

                value=int(pulp.get("value") or 0),

                note=pulp.get("note"),

            ),

            followups=[

                {

                    "label": "Что входит в лечение",

                    "action": "price_aspect",

                    "aspect": "includes",

                    "detail_ref": "therapy__service__pulpitis.md#chto-vhodit",

                }

            ],

            cta_key="price",

        )

        path = OUT / "pulpitis.json"

        path.write_text(

            json.dumps(entry.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",

            encoding="utf-8",

        )

        print(f"wrote {path.relative_to(ROOT)}")





def main() -> int:

    migrate_complex()

    migrate_simple()

    return 0





if __name__ == "__main__":

    raise SystemExit(main())


