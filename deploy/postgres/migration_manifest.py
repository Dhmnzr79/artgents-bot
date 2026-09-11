"""Pure manifest / checksum helpers for PostgreSQL migration runner (offline-testable)."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

_SAFE_FILENAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*\.sql$")

_LEDGER_SCHEMA = "bot_migration"
_LEDGER_TABLE = "schema_migrations"


@dataclass(frozen=True)
class ManifestEntry:
    filename: str
    path: Path
    checksum: str


@dataclass(frozen=True)
class LedgerRow:
    filename: str
    checksum: str


class MigrationManifestError(Exception):
    """Invalid manifest, path, or ledger divergence (fail-closed)."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(code if not detail else f"{code}:{detail}")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _parse_manifest_lines(text: str) -> list[str]:
    names: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        names.append(stripped)
    return names


def load_manifest(manifest_path: Path, migrations_dir: Path) -> list[ManifestEntry]:
    if not manifest_path.is_file():
        raise MigrationManifestError("manifest_missing", manifest_path.name)
    raw_names = _parse_manifest_lines(manifest_path.read_text(encoding="utf-8"))
    if not raw_names:
        raise MigrationManifestError("manifest_empty")
    seen: set[str] = set()
    entries: list[ManifestEntry] = []
    for name in raw_names:
        if name in seen:
            raise MigrationManifestError("manifest_duplicate", name)
        seen.add(name)
        if not _SAFE_FILENAME.match(name):
            raise MigrationManifestError("manifest_unsafe_path", name)
        if ".." in name or "/" in name or "\\" in name:
            raise MigrationManifestError("manifest_unsafe_path", name)
        sql_path = (migrations_dir / name).resolve()
        try:
            sql_path.relative_to(migrations_dir.resolve())
        except ValueError:
            raise MigrationManifestError("manifest_unsafe_path", name) from None
        if not sql_path.is_file():
            raise MigrationManifestError("manifest_missing_file", name)
        entries.append(
            ManifestEntry(
                filename=name,
                path=sql_path,
                checksum=sha256_file(sql_path),
            )
        )
    return entries


def reconcile_ledger(
    manifest_filenames: frozenset[str],
    ledger_rows: list[LedgerRow],
) -> None:
    """Fail-closed if ledger contains migrations not present in manifest."""
    for row in ledger_rows:
        if row.filename not in manifest_filenames:
            raise MigrationManifestError("ledger_unknown_migration", row.filename)


def manifest_prefix_entries(
    entries: list[ManifestEntry],
    through_filename: str,
) -> list[ManifestEntry]:
    """Return manifest prefix through inclusive target (exact manifest filename)."""
    names = [e.filename for e in entries]
    if through_filename not in names:
        raise MigrationManifestError("through_target_invalid", through_filename)
    end = names.index(through_filename) + 1
    return entries[:end]


def plan_actions(
    entries: list[ManifestEntry],
    ledger_by_name: dict[str, LedgerRow],
) -> list[tuple[ManifestEntry, str]]:
    """
    Return (entry, action) where action is 'skip' | 'apply'.
    Raises on checksum mismatch.
    """
    planned: list[tuple[ManifestEntry, str]] = []
    for entry in entries:
        existing = ledger_by_name.get(entry.filename)
        if existing is None:
            planned.append((entry, "apply"))
            continue
        if existing.checksum != entry.checksum:
            raise MigrationManifestError("checksum_mismatch", entry.filename)
        planned.append((entry, "skip"))
    return planned


def checksum_prefix(checksum: str, length: int = 12) -> str:
    return checksum[:length]


def ledger_qualified_table() -> str:
    return f"{_LEDGER_SCHEMA}.{_LEDGER_TABLE}"


def ledger_schema_ddl() -> str:
    return f"""
CREATE SCHEMA IF NOT EXISTS {_LEDGER_SCHEMA};
CREATE TABLE IF NOT EXISTS {_LEDGER_SCHEMA}.{_LEDGER_TABLE} (
  filename text PRIMARY KEY,
  checksum text NOT NULL,
  applied_at timestamptz NOT NULL DEFAULT now()
);
""".strip()


# Session advisory lock for entire migration run (single global key; not user input).
MIGRATION_ADVISORY_LOCK_KEY = 0x4D4947525F544E54  # "MIGR_TNT"
