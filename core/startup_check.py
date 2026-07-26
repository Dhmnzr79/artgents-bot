"""Validate per-client index artifacts before app serves traffic."""
from __future__ import annotations

import logging
import os
import sys

from core.client_runtime import client_md_dir, list_buildable_client_ids
from core.target_client_data import load_target_client_data
from logging_setup import log_json


def run_startup_check(logger: logging.Logger) -> None:
    client_ids = list_buildable_client_ids()
    if not client_ids:
        logger.error("startup_check_failed: no client packs with md/")
        sys.exit(1)

    total_md_files = 0
    for cid in client_ids:
        md_dir = client_md_dir(cid)

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

        try:
            data = load_target_client_data(cid)
        except Exception as e:
            logger.error(
                "startup_check_failed: canonical target_response invalid for %s: %s",
                cid,
                e,
            )
            sys.exit(1)
        if not data.bundle.services:
            logger.error("startup_check_failed: target service catalog empty for %s", cid)
            sys.exit(1)
        if not data.bundle.offers:
            logger.error("startup_check_failed: target price offers empty for %s", cid)
            sys.exit(1)

    log_json(logger, "startup_check_ok", clients=client_ids, md_files=total_md_files)
