"""Validate the actual D2 catalogs before app serves traffic."""
from __future__ import annotations

import logging
import os
import sys

from config import ALLOWED_CLIENTS, APP_ENV, DEFAULT_LLM_MODEL, QWEN_ENABLE_THINKING
from core.prod_readiness import evaluate_allowed_client_registry
from core.one_call_prompt_contract import ONE_CALL_PROMPT_CONTRACT_VERSION
from core.d2_tenant_snapshot import (
    d2_clients_root, load_d2_tenant_snapshot, build_d2_model_view,
    validate_d2_authored_content_refs,
)
from logging_setup import log_json


def run_startup_check(logger: logging.Logger) -> None:
    clients_root = d2_clients_root()
    if APP_ENV == "prod":
        registry_errors = evaluate_allowed_client_registry()
        if registry_errors:
            logger.error(
                "startup_check_failed: allowed client registry invalid: %s",
                ",".join(registry_errors),
            )
            sys.exit(1)
        client_ids = sorted(ALLOWED_CLIENTS)
    else:
        client_ids = sorted(
            path.name for path in clients_root.iterdir()
            if not path.name.startswith("_") and (path / "md").is_dir()
        ) if clients_root.is_dir() else []
    if not client_ids:
        logger.error("startup_check_failed: no client packs with md/")
        sys.exit(1)

    total_md_files = 0
    for cid in client_ids:
        md_dir = clients_root / cid / "md"

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
            snapshot = load_d2_tenant_snapshot(cid, clients_root=clients_root)
            build_d2_model_view(snapshot)
            if validate_d2_authored_content_refs(snapshot):
                raise ValueError("d2_authored_content_ref_unavailable")
        except Exception as e:
            logger.error(
                "startup_check_failed: canonical target_response invalid for %s: %s",
                cid,
                e,
            )
            sys.exit(1)
        if not snapshot.bundle.services:
            logger.error("startup_check_failed: target service catalog empty for %s", cid)
            sys.exit(1)
        if not snapshot.bundle.offers:
            logger.error("startup_check_failed: target price offers empty for %s", cid)
            sys.exit(1)

    log_json(logger, "startup_check_ok", clients=client_ids, md_files=total_md_files)
    log_json(
        logger,
        "runtime_provenance_startup",
        architecture="d2_dialogue",
        model=DEFAULT_LLM_MODEL,
        single_model=True,
        qwen_enable_thinking=QWEN_ENABLE_THINKING,
        prompt_contract=ONE_CALL_PROMPT_CONTRACT_VERSION,
    )
