"""Frozen contract for ONE_CALL architecture comparison offline harness (CP-ARCH-COMPARE-OFFLINE-V1)."""

from __future__ import annotations

import hashlib
from datetime import date

MEASUREMENT_ID = "one_call_arch_compare_offline_v1"
MATRIX_SCHEMA = "one_call_arch_compare_matrix_v1"
MATRIX_JSON_REL_PATH = "evals/v5/arch_compare/arch_compare_matrix_v1.json"
CLIENT_ID = "demo"

CONFIG_FLASH_FULL = "flash_full"
CONFIG_FLASH_CURATED = "flash_curated"
CONFIG_PLUS_FULL = "plus_full"
CONFIG_PLUS_CURATED = "plus_curated"

CONFIG_IDS: tuple[str, ...] = (
    CONFIG_FLASH_FULL,
    CONFIG_FLASH_CURATED,
    CONFIG_PLUS_FULL,
    CONFIG_PLUS_CURATED,
)

MODEL_ROLE_FLASH = "flash"
MODEL_ROLE_PLUS = "plus"
CONTEXT_MODE_FULL = "full"
CONTEXT_MODE_CURATED = "curated"

BLIND_VARIANTS: tuple[str, ...] = ("A", "B", "C", "D")

# Deterministic eval date — same across all configs/scenarios.
FROZEN_COMMERCIAL_AS_OF = date(2026, 8, 30)

# Populated after matrix stabilization; governance tests pin normalized-byte digest.
FROZEN_MATRIX_DIGEST: str = "b860e58e3ed94374e4ba095bdbd75b590028d33bd8c692405aa48ecc1c7ed347"

EXPECTED_SCENARIO_COUNT = 16
EXPECTED_TURN_COUNT = 19
EXPECTED_CONFIG_COUNT = 4
EXPECTED_SCENARIO_CONFIG_RESULTS = 64
EXPECTED_TURN_CONFIG_RESULTS = 76

FAKE_PATIENT_TEXT_PREFIX = "arch_compare_fake_wire"

DRY_RUN_DISCLAIMER = (
    "Не предназначен для оценки качества модели. "
    "Fake/offline wiring only; 0 provider/network calls."
)


def canonical_matrix_bytes(raw: bytes) -> bytes:
    """Normalize line endings for digest: CRLF and lone CR become LF."""
    return raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def matrix_digest_sha256(raw: bytes) -> str:
    """SHA-256 of matrix JSON bytes after line-ending normalization only."""
    return hashlib.sha256(canonical_matrix_bytes(raw)).hexdigest()
