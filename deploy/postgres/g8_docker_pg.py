"""Run pg_isready / pg_dump / pg_restore inside the pinned CI service container."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import IO

from deploy.postgres.g8_disposable_constants import G8_BOOTSTRAP_PASSWORD, G8_BOOTSTRAP_USER

_CONTAINER_ID_RE = re.compile(r"^[0-9a-f]{12,64}$")


def validated_postgres_container_id() -> str:
    cid = (os.getenv("G8_POSTGRES_CONTAINER_ID") or "").strip().lower()
    if not _CONTAINER_ID_RE.fullmatch(cid):
        raise RuntimeError("invalid_postgres_container_id")
    return cid


def _docker_base_env() -> dict[str, str]:
    env = dict(subprocess.os.environ)
    env["PGPASSWORD"] = G8_BOOTSTRAP_PASSWORD
    return env


def docker_exec(
    argv: list[str],
    *,
    stdin: IO[bytes] | None = None,
    stdout: IO[bytes] | None = None,
    stderr: subprocess.PIPE | None = subprocess.PIPE,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    cid = validated_postgres_container_id()
    cmd = ["docker", "exec", "-i", "-e", f"PGPASSWORD={G8_BOOTSTRAP_PASSWORD}", cid, *argv]
    proc = subprocess.run(
        cmd,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        env=_docker_base_env(),
    )
    if check and proc.returncode != 0:
        raise RuntimeError(f"docker_exec_failed:{argv[0]}")
    return proc


def pg_isready_in_container(*, user: str, database: str) -> bool:
    proc = docker_exec(
        ["pg_isready", "-U", user, "-d", database],
        check=False,
    )
    return proc.returncode == 0


def pg_dump_custom_to_file(*, user: str, database: str, archive_path: Path) -> None:
    with archive_path.open("wb") as out:
        docker_exec(
            [
                "pg_dump",
                "-U",
                user,
                "-d",
                database,
                "--format=custom",
                "--no-password",
            ],
            stdout=out,
        )


def pg_restore_list_archive(archive_path: Path) -> None:
    with archive_path.open("rb") as src:
        docker_exec(["pg_restore", "--list"], stdin=src)


def pg_restore_into_database(
    *,
    user: str,
    database: str,
    archive_path: Path,
    role: str,
) -> None:
    with archive_path.open("rb") as src:
        docker_exec(
            [
                "pg_restore",
                "-U",
                user,
                "-d",
                database,
                "--no-owner",
                "--role",
                role,
                "--no-password",
            ],
            stdin=src,
        )


def pg_isready_host_fallback(
    *,
    user: str,
    database: str,
    host: str,
    port: int,
    env_password: str,
) -> bool:
    env = {**subprocess.os.environ, "PGPASSWORD": env_password}
    proc = subprocess.run(
        ["pg_isready", "-h", host, "-p", str(port), "-U", user, "-d", database],
        capture_output=True,
        env=env,
    )
    return proc.returncode == 0
