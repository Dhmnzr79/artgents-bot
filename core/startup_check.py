"""Validate per-client index artifacts before app serves traffic."""
from __future__ import annotations

import json
import logging
import os
import sys

from core.client_runtime import client_md_dir, client_pack_dir, list_buildable_client_ids
from core.pricebook_loader import pricebook_services_dir
from logging_setup import log_json


def _client_has_price_source(cid: str) -> bool:
    svc_dir = pricebook_services_dir(cid)
    if not os.path.isdir(svc_dir):
        return False
    try:
        return any(name.endswith(".json") for name in os.listdir(svc_dir))
    except OSError:
        return False


def run_startup_check(logger: logging.Logger) -> None:
    client_ids = list_buildable_client_ids()
    if not client_ids:
        logger.error("startup_check_failed: no client packs with md/")
        sys.exit(1)

    total_md_files = 0
    for cid in client_ids:
        md_dir = client_md_dir(cid)
        catalog_path = os.path.join(client_pack_dir(cid), "service_catalog.json")

        if not os.path.isdir(md_dir):
            logger.error("startup_check_failed: md dir missing for %s: %s", cid, md_dir)
            sys.exit(1)
        try:
            md_files = [
                name
                for name in os.listdir(md_dir)
                if name.lower().endswith(".md") and os.path.isfile(os.path.join(md_dir, name))
            ]
        except Exception as e:
            logger.error("startup_check_failed: cannot read md dir for %s: %s", cid, e)
            sys.exit(1)
        if not md_files:
            logger.error("startup_check_failed: empty md dir for %s: %s", cid, md_dir)
            sys.exit(1)
        total_md_files += len(md_files)

        if not os.path.isfile(catalog_path):
            logger.error("startup_check_failed: service_catalog missing for %s: %s", cid, catalog_path)
            sys.exit(1)
        try:
            with open(catalog_path, "r", encoding="utf-8") as f:
                catalog_obj = json.load(f)
            if not isinstance(catalog_obj, dict):
                logger.error("startup_check_failed: service_catalog must be object for %s", cid)
                sys.exit(1)
        except Exception as e:
            logger.error("startup_check_failed: invalid service_catalog for %s: %s", cid, e)
            sys.exit(1)

        if not _client_has_price_source(cid):
            logger.error(
                "startup_check_failed: pricebook missing for %s "
                "(need pricebook/services/*.json)",
                cid,
            )
            sys.exit(1)

    log_json(logger, "startup_check_ok", clients=client_ids, md_files=total_md_files)
