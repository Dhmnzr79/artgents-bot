#!/usr/bin/env python3
"""G7 PostgreSQL backup receipt, retention, and offline verification helpers (stdlib only)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

G7_RECEIPT_SCHEMA_VERSION = 1
G7_ARCHIVE_SUFFIX = ".pgdump.custom"
G7_RECEIPT_SUFFIX = ".receipt.json"

_SHA256_RECEIPT_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_SHA_SOURCE_RE = re.compile(r"^[0-9a-f]{40}$")
_REASONS = frozenset({"pre-deploy", "pre-rollback", "scheduled"})
_ISO8601_Z_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_PG_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")
_G7_BASENAME_RE = re.compile(
    r"^pgbackup-(pre-deploy|pre-rollback|scheduled)-"
    r"\d{4}-\d{2}-\d{2}T\d{6}Z-[0-9a-f]{16}$"
)

_RECEIPT_SCHEMA_KEYS = frozenset(
    {
        "schema_version",
        "status",
        "reason",
        "source_sha",
        "created_at",
        "archive_path",
        "archive_sha256",
        "archive_size_bytes",
        "database_name",
        "pg_restore_list_check",
        "backup_id",
    }
)

_DEFAULT_BACKUPS_PARENT = Path("/var/lib/artgents/backups")
_DEFAULT_ARCHIVE_ROOT = Path("/var/lib/artgents/backups/postgres")
_DEFAULT_RECEIPT_ROOT = Path("/var/lib/artgents/backups/receipts")


def reject_symlink(path: Path, label: str) -> None:
    if path.is_symlink():
        raise ValueError(f"{label} must not be a symlink")


def validate_postgres_identifier(value: str, *, field: str) -> str:
    if not value or not _PG_IDENTIFIER_RE.fullmatch(value):
        raise ValueError(f"invalid {field}")
    return value


def validate_created_at_utc(value: str) -> datetime:
    if not isinstance(value, str) or not _ISO8601_Z_RE.fullmatch(value):
        raise ValueError("invalid created_at")
    try:
        dt = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ValueError("invalid created_at") from exc
    if dt.year < 1970 or dt.year > 9999:
        raise ValueError("invalid created_at")
    return dt


def validate_backup_id(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("invalid backup_id")
    try:
        parsed = uuid.UUID(value)
    except ValueError as exc:
        raise ValueError("invalid backup_id") from exc
    if str(parsed) != value.lower() and str(parsed) != value:
        raise ValueError("invalid backup_id")
    return str(parsed)


def assert_trusted_directory(
    path: Path,
    *,
    label: str,
    enforce_root_metadata: bool = True,
) -> Path:
    reject_symlink(path, label)
    if not path.is_dir():
        raise ValueError(f"{label} must be a directory")
    if enforce_root_metadata:
        st = path.stat()
        if st.st_uid != 0 or st.st_gid != 0:
            raise ValueError(f"{label} must be root-owned")
        mode = st.st_mode & 0o777
        if mode != 0o700:
            raise ValueError(f"{label} must be mode 0700")
    return path.resolve(strict=True)


def assert_trusted_backups_parent(
    parent: Path = _DEFAULT_BACKUPS_PARENT,
    *,
    enforce_root_metadata: bool = True,
) -> Path:
    return assert_trusted_directory(
        parent,
        label="backups parent",
        enforce_root_metadata=enforce_root_metadata,
    )


def is_g7_receipt_filename(name: str) -> bool:
    if not name.endswith(G7_RECEIPT_SUFFIX):
        return False
    stem = name[: -len(G7_RECEIPT_SUFFIX)]
    return bool(_G7_BASENAME_RE.fullmatch(stem))


def is_g7_archive_filename(name: str) -> bool:
    if not name.endswith(G7_ARCHIVE_SUFFIX):
        return False
    stem = name[: -len(G7_ARCHIVE_SUFFIX)]
    return bool(_G7_BASENAME_RE.fullmatch(stem))


def parse_g7_basename(stem: str) -> tuple[str, str, str]:
    match = re.fullmatch(
        r"pgbackup-(pre-deploy|pre-rollback|scheduled)-"
        r"(\d{4}-\d{2}-\d{2}T\d{6}Z)-([0-9a-f]{16})$",
        stem,
    )
    if not match:
        raise ValueError("invalid g7 basename")
    return match.group(1), match.group(2), match.group(3)


def created_at_to_filename_timestamp(created_at: str) -> str:
    dt = validate_created_at_utc(created_at)
    return dt.strftime("%Y-%m-%dT%H%M%SZ")


def g7_stem_from_filename(name: str, suffix: str) -> str:
    if not name.endswith(suffix):
        raise ValueError("invalid g7 filename suffix")
    return name[: -len(suffix)]


def validate_receipt_archive_binding(
    receipt_name: str,
    archive_name: str,
    payload: dict[str, Any],
) -> None:
    receipt_stem = g7_stem_from_filename(receipt_name, G7_RECEIPT_SUFFIX)
    archive_stem = g7_stem_from_filename(archive_name, G7_ARCHIVE_SUFFIX)
    if receipt_stem != archive_stem:
        raise ValueError("receipt and archive basename mismatch")
    reason, timestamp_part, _suffix = parse_g7_basename(receipt_stem)
    if reason != payload.get("reason"):
        raise ValueError("filename reason mismatch")
    expected_ts = created_at_to_filename_timestamp(payload["created_at"])
    if timestamp_part != expected_ts:
        raise ValueError("filename timestamp mismatch")


def generate_backup_identity() -> tuple[str, str]:
    backup_id = str(uuid.uuid4())
    validate_backup_id(backup_id)
    unique_suffix = backup_id.replace("-", "")[:16]
    if not re.fullmatch(r"[0-9a-f]{16}", unique_suffix):
        raise ValueError("invalid unique suffix")
    return backup_id, unique_suffix


def validate_run_artifact_path(path: Path, root: Path, kind: str) -> None:
    if kind not in ("archive", "receipt"):
        raise ValueError("invalid artifact kind")
    reject_symlink(path, kind)
    canonical = canonical_containment(
        path,
        root,
        child_label=kind,
        root_label=f"{kind} root",
        enforce_root_metadata=False,
    )
    assert_regular_file_metadata(canonical, label=kind, enforce_root_metadata=False)
    if kind == "archive":
        if not is_g7_archive_filename(canonical.name):
            raise ValueError("archive filename not in G7 format")
    elif not is_g7_receipt_filename(canonical.name):
        raise ValueError("receipt filename not in G7 format")


def canonical_containment(
    child: Path,
    root: Path,
    *,
    child_label: str = "path",
    root_label: str = "root",
    enforce_root_metadata: bool = True,
) -> Path:
    root_resolved = assert_trusted_directory(
        root, label=root_label, enforce_root_metadata=enforce_root_metadata
    )
    reject_symlink(child, child_label)
    child_resolved = child.resolve(strict=False)
    if child_resolved == root_resolved:
        raise ValueError("path must not be the root directory")
    try:
        child_resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError("path outside allowed root") from exc
    return child_resolved


def assert_regular_file_metadata(
    path: Path, *, label: str, enforce_root_metadata: bool = True
) -> None:
    reject_symlink(path, label)
    if not path.is_file():
        raise ValueError(f"{label} must be a regular file")
    if not enforce_root_metadata:
        return
    st = path.stat()
    if st.st_uid != 0 or st.st_gid != 0:
        raise ValueError(f"{label} must be root-owned")
    mode = st.st_mode & 0o777
    if mode & 0o077:
        raise ValueError(f"{label} must not be group/world accessible")
    if mode != 0o600:
        raise ValueError(f"{label} must be mode 0600")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def _read_env_assignment(env_path: Path, key: str) -> str | None:
    found: str | None = None
    with env_path.open("r", encoding="utf-8", errors="strict") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export ") :].strip()
            if "=" not in line:
                continue
            name, _, value = line.partition("=")
            if name.strip() != key:
                continue
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            if not value or any(ch in value for ch in "\n\r\t"):
                raise ValueError(f"invalid {key}")
            if found is not None:
                raise ValueError(f"duplicate {key}")
            found = value
    return found


def parse_postgres_targets(env_path: Path) -> tuple[str, str]:
    """Read POSTGRES_USER and POSTGRES_DB only (no secrets logged)."""
    reject_symlink(env_path, "production env")
    if not env_path.is_file():
        raise ValueError("production env must be a regular file")
    user_raw = _read_env_assignment(env_path, "POSTGRES_USER")
    db_raw = _read_env_assignment(env_path, "POSTGRES_DB")
    if not user_raw:
        raise ValueError("POSTGRES_USER missing from production env")
    if not db_raw:
        raise ValueError("POSTGRES_DB missing from production env")
    user = validate_postgres_identifier(user_raw, field="POSTGRES_USER")
    db = validate_postgres_identifier(db_raw, field="POSTGRES_DB")
    return user, db


def parse_postgres_db_name(env_path: Path) -> str:
    return parse_postgres_targets(env_path)[1]


def validate_receipt_payload(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("receipt must be a JSON object")
    keys = frozenset(data.keys())
    if keys != _RECEIPT_SCHEMA_KEYS:
        raise ValueError("receipt contains unknown or missing fields")

    if data.get("schema_version") != G7_RECEIPT_SCHEMA_VERSION:
        raise ValueError("unsupported receipt schema_version")
    if data.get("status") != "success":
        raise ValueError("receipt status must be success")
    reason = data.get("reason")
    if reason not in _REASONS:
        raise ValueError("invalid reason")
    source_sha = data.get("source_sha")
    if reason == "scheduled":
        if source_sha is not None:
            raise ValueError("scheduled receipt must have null source_sha")
    else:
        if not isinstance(source_sha, str) or not _SHA_SOURCE_RE.fullmatch(source_sha):
            raise ValueError("invalid source_sha")
    validate_created_at_utc(data.get("created_at"))
    archive_path = data.get("archive_path")
    if not isinstance(archive_path, str) or not Path(archive_path).is_absolute():
        raise ValueError("invalid archive_path")
    archive_sha = data.get("archive_sha256")
    if not isinstance(archive_sha, str) or not _SHA256_RECEIPT_RE.fullmatch(archive_sha):
        raise ValueError("invalid archive_sha256")
    size = data.get("archive_size_bytes")
    if not isinstance(size, int) or size <= 0:
        raise ValueError("invalid archive_size_bytes")
    db_name = data.get("database_name")
    validate_postgres_identifier(db_name, field="database_name")
    if data.get("pg_restore_list_check") != "passed":
        raise ValueError("pg_restore_list_check must be passed")
    validate_backup_id(data.get("backup_id"))
    return data


def verify_receipt_file(
    receipt_path: Path,
    *,
    archive_root: Path = _DEFAULT_ARCHIVE_ROOT,
    receipt_root: Path = _DEFAULT_RECEIPT_ROOT,
    backups_parent: Path = _DEFAULT_BACKUPS_PARENT,
    check_archive_on_disk: bool = True,
    enforce_root_metadata: bool = True,
) -> dict[str, Any]:
    reject_symlink(receipt_path, "receipt")
    reject_symlink(archive_root, "archive root")
    reject_symlink(receipt_root, "receipt root")
    reject_symlink(backups_parent, "backups parent")
    assert_trusted_backups_parent(backups_parent, enforce_root_metadata=enforce_root_metadata)
    assert_trusted_directory(
        archive_root, label="archive root", enforce_root_metadata=enforce_root_metadata
    )
    assert_trusted_directory(
        receipt_root, label="receipt root", enforce_root_metadata=enforce_root_metadata
    )
    canonical_receipt = canonical_containment(
        receipt_path,
        receipt_root,
        child_label="receipt",
        root_label="receipt root",
        enforce_root_metadata=enforce_root_metadata,
    )
    assert_regular_file_metadata(
        canonical_receipt, label="receipt", enforce_root_metadata=enforce_root_metadata
    )
    try:
        data = json.loads(canonical_receipt.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError("receipt JSON invalid") from exc
    payload = validate_receipt_payload(data)
    archive = Path(payload["archive_path"])
    reject_symlink(archive, "archive")
    archive_canonical = canonical_containment(
        archive,
        archive_root,
        child_label="archive",
        root_label="archive root",
        enforce_root_metadata=enforce_root_metadata,
    )
    assert_regular_file_metadata(
        archive_canonical, label="archive", enforce_root_metadata=enforce_root_metadata
    )
    if not is_g7_archive_filename(archive_canonical.name):
        raise ValueError("archive filename not in G7 format")
    if not is_g7_receipt_filename(canonical_receipt.name):
        raise ValueError("receipt filename not in G7 format")
    validate_receipt_archive_binding(
        canonical_receipt.name,
        archive_canonical.name,
        payload,
    )
    if check_archive_on_disk:
        on_disk_size = archive_canonical.stat().st_size
        if on_disk_size != payload["archive_size_bytes"]:
            raise ValueError("archive size mismatch")
        if sha256_file(archive_canonical) != payload["archive_sha256"]:
            raise ValueError("archive sha256 mismatch")
    payload = dict(payload)
    payload["_canonical_receipt_path"] = str(canonical_receipt)
    payload["_canonical_archive_path"] = str(archive_canonical)
    return payload


def retention_candidates(
    *,
    archive_root: Path,
    receipt_root: Path,
    retention_days: int,
    now: datetime | None = None,
    enforce_root_metadata: bool = True,
    backups_parent: Path = _DEFAULT_BACKUPS_PARENT,
) -> list[tuple[Path, Path]]:
    if retention_days < 1:
        raise ValueError("retention_days must be at least 1")
    reject_symlink(archive_root, "archive root")
    reject_symlink(receipt_root, "receipt root")
    assert_trusted_backups_parent(backups_parent, enforce_root_metadata=enforce_root_metadata)
    assert_trusted_directory(
        archive_root, label="archive root", enforce_root_metadata=enforce_root_metadata
    )
    assert_trusted_directory(
        receipt_root, label="receipt root", enforce_root_metadata=enforce_root_metadata
    )
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=retention_days)
    pairs: list[tuple[Path, Path]] = []
    for entry in sorted(receipt_root.iterdir()):
        if not is_g7_receipt_filename(entry.name):
            continue
        if entry.is_symlink() or not entry.is_file():
            continue
        try:
            data = json.loads(entry.read_text(encoding="utf-8"))
            payload = validate_receipt_payload(data)
        except (OSError, json.JSONDecodeError, UnicodeError, ValueError):
            continue
        try:
            created = validate_created_at_utc(payload["created_at"])
        except ValueError:
            continue
        if created >= cutoff:
            continue
        try:
            verified = verify_receipt_file(
                entry,
                archive_root=archive_root,
                receipt_root=receipt_root,
                backups_parent=backups_parent,
                check_archive_on_disk=True,
                enforce_root_metadata=enforce_root_metadata,
            )
        except ValueError:
            continue
        archive_path = Path(verified["_canonical_archive_path"])
        receipt_path = Path(verified["_canonical_receipt_path"])
        pairs.append((archive_path, receipt_path))
    return pairs


def delete_retention_pair(archive_path: Path, receipt_path: Path) -> None:
    reject_symlink(archive_path, "archive")
    reject_symlink(receipt_path, "receipt")
    if not archive_path.is_file() or not receipt_path.is_file():
        raise ValueError("retention pair must be regular files")
    os.remove(archive_path)
    os.remove(receipt_path)


def build_receipt_payload(
    *,
    reason: str,
    source_sha: str | None,
    created_at: str,
    archive_path: str,
    archive_sha256: str,
    archive_size_bytes: int,
    database_name: str,
    backup_id: str,
) -> dict[str, Any]:
    payload = {
        "schema_version": G7_RECEIPT_SCHEMA_VERSION,
        "status": "success",
        "reason": reason,
        "source_sha": source_sha,
        "created_at": created_at,
        "archive_path": archive_path,
        "archive_sha256": archive_sha256,
        "archive_size_bytes": archive_size_bytes,
        "database_name": database_name,
        "pg_restore_list_check": "passed",
        "backup_id": backup_id,
    }
    validate_receipt_payload(payload)
    return payload


def write_receipt_atomic(receipt_path: Path, payload: dict[str, Any]) -> None:
    validate_receipt_payload(payload)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = receipt_path.with_name(f".{receipt_path.name}.{uuid.uuid4().hex}.tmp")
    try:
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, receipt_path)
        os.chmod(receipt_path, 0o600)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def cmd_write_receipt(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--source-sha", default="")
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--archive-path", required=True)
    parser.add_argument("--archive-sha256", required=True)
    parser.add_argument("--archive-size-bytes", type=int, required=True)
    parser.add_argument("--database-name", required=True)
    parser.add_argument("--backup-id", required=True)
    args = parser.parse_args(argv)
    source: str | None
    if args.reason == "scheduled":
        source = None
    else:
        if not _SHA_SOURCE_RE.fullmatch(args.source_sha or ""):
            print("invalid source_sha", file=sys.stderr)
            return 1
        source = args.source_sha
    if args.reason not in _REASONS:
        print("invalid reason", file=sys.stderr)
        return 1
    try:
        validate_postgres_identifier(args.database_name, field="database_name")
        validate_backup_id(args.backup_id)
        validate_created_at_utc(args.created_at)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    payload = build_receipt_payload(
        reason=args.reason,
        source_sha=source,
        created_at=args.created_at,
        archive_path=args.archive_path,
        archive_sha256=args.archive_sha256,
        archive_size_bytes=args.archive_size_bytes,
        database_name=args.database_name,
        backup_id=args.backup_id,
    )
    out = Path(args.output)
    write_receipt_atomic(out, payload)
    return 0


def cmd_run_retention(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--archive-root", default=str(_DEFAULT_ARCHIVE_ROOT))
    parser.add_argument("--receipt-root", default=str(_DEFAULT_RECEIPT_ROOT))
    parser.add_argument("--backups-parent", default=str(_DEFAULT_BACKUPS_PARENT))
    args = parser.parse_args(argv)
    try:
        pairs = retention_candidates(
            archive_root=Path(args.archive_root),
            receipt_root=Path(args.receipt_root),
            retention_days=args.days,
            backups_parent=Path(args.backups_parent),
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    for archive_path, receipt_path in pairs:
        try:
            delete_retention_pair(archive_path, receipt_path)
        except OSError as exc:
            print(f"retention delete failed: {exc}", file=sys.stderr)
            return 1
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    return 0


def cmd_parse_db(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        name = parse_postgres_db_name(args.env_file)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(name)
    return 0


def cmd_parse_targets(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        user, db = parse_postgres_targets(args.env_file)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"POSTGRES_USER={user}")
    print(f"POSTGRES_DB={db}")
    return 0


def cmd_new_backup_identity(argv: list[str] | None = None) -> int:
    _ = argv
    try:
        backup_id, unique_suffix = generate_backup_identity()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"BACKUP_ID={backup_id}")
    print(f"UNIQUE_SUFFIX={unique_suffix}")
    return 0


def cmd_validate_run_artifact(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True, type=Path)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--kind", required=True, choices=("archive", "receipt"))
    args = parser.parse_args(argv)
    try:
        validate_run_artifact_path(args.path, args.root, args.kind)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


def cmd_verify_receipt(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--archive-root", default=str(_DEFAULT_ARCHIVE_ROOT))
    parser.add_argument("--receipt-root", default=str(_DEFAULT_RECEIPT_ROOT))
    parser.add_argument("--backups-parent", default=str(_DEFAULT_BACKUPS_PARENT))
    args = parser.parse_args(argv)
    if not args.receipt.is_absolute():
        print("receipt path must be absolute", file=sys.stderr)
        return 1
    try:
        verify_receipt_file(
            args.receipt,
            archive_root=Path(args.archive_root),
            receipt_root=Path(args.receipt_root),
            backups_parent=Path(args.backups_parent),
            check_archive_on_disk=True,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("subcommand required", file=sys.stderr)
        return 2
    cmd = argv[0]
    rest = argv[1:]
    if cmd == "write-receipt":
        return cmd_write_receipt(rest)
    if cmd == "run-retention":
        return cmd_run_retention(rest)
    if cmd == "verify-receipt":
        return cmd_verify_receipt(rest)
    if cmd == "parse-db":
        return cmd_parse_db(rest)
    if cmd == "parse-targets":
        return cmd_parse_targets(rest)
    if cmd == "new-backup-identity":
        return cmd_new_backup_identity(rest)
    if cmd == "validate-run-artifact":
        return cmd_validate_run_artifact(rest)
    print("unknown subcommand", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
