"""Small process-local cache for already-verified governed UI answers."""

from __future__ import annotations

import hashlib
import json
import threading
from collections import OrderedDict
from dataclasses import asdict

from contracts.target_cached_full_context import TargetCachedFullContext
from core.client_config_loader import load_widget_config
from core.target_composer_executor import (
    TARGET_COMPOSER_SYSTEM_POLICY,
    TargetComposerRequest,
)
from core.target_response_verifier import (
    TARGET_SEMANTIC_VERIFIER_SYSTEM_POLICY,
    TargetVerifiedComposedResponse,
)


_CACHE_FORMAT_VERSION = "verified-governed-answer-v1"
_MAX_ENTRIES = 128
_lock = threading.Lock()
_entries: "OrderedDict[str, TargetVerifiedComposedResponse]" = OrderedDict()


def governed_ui_answer_cache_eligible(*, user_message: str, client_id: str) -> bool:
    """Accept a validated nav click or an exact authored starter prompt."""

    try:
        from flask import has_request_context, request

        if has_request_context() and str(request.ctx.get("nav_ref") or "").strip():
            return True
    except Exception:
        pass
    try:
        config = load_widget_config(client_id)
    except Exception:
        return False
    prompts = config.get("starterPrompts") if isinstance(config, dict) else None
    if not isinstance(prompts, list):
        return False
    exact = user_message.strip()
    return any(
        isinstance(item, dict)
        and isinstance(item.get("q"), str)
        and item["q"].strip() == exact
        for item in prompts
    )


def _request_payload(request: TargetComposerRequest) -> dict[str, object]:
    return {
        "user_message": request.user_message,
        "spec": request.spec.model_dump(mode="json"),
        "evidence_blocks": [asdict(block) for block in request.evidence_blocks],
        "action_context": (
            request.action_context.model_dump(mode="json")
            if request.action_context
            else None
        ),
        "response_length_profile": request.response_length_profile,
    }


def build_versioned_answer_cache_key(
    request: TargetComposerRequest,
    cached_full_context: TargetCachedFullContext,
    *,
    client_id: str,
    composer_backend: object,
    semantic_backend: object,
) -> str:
    payload = {
        "format": _CACHE_FORMAT_VERSION,
        "client_id": client_id,
        "pack_sha256": cached_full_context.sha256,
        "prompt_sha256": cached_full_context.prompt_sha256,
        "composer_policy_sha256": hashlib.sha256(
            TARGET_COMPOSER_SYSTEM_POLICY.encode("utf-8")
        ).hexdigest(),
        "verifier_policy_sha256": hashlib.sha256(
            TARGET_SEMANTIC_VERIFIER_SYSTEM_POLICY.encode("utf-8")
        ).hexdigest(),
        "composer_model": getattr(composer_backend, "model", None),
        "verifier_model": getattr(semantic_backend, "model", None),
        "request": _request_payload(request),
    }
    serialized = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def get_versioned_answer(key: str) -> TargetVerifiedComposedResponse | None:
    with _lock:
        value = _entries.get(key)
        if value is not None:
            _entries.move_to_end(key)
        return value


def put_versioned_answer(key: str, value: TargetVerifiedComposedResponse) -> None:
    with _lock:
        _entries[key] = value
        _entries.move_to_end(key)
        while len(_entries) > _MAX_ENTRIES:
            _entries.popitem(last=False)


def clear_versioned_answer_cache() -> None:
    """Offline-test/startup helper; never called as part of a user turn."""

    with _lock:
        _entries.clear()
