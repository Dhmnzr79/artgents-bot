# G8 — Disposable PostgreSQL qualification

G8 proves production migrations, role boundaries, RLS, and backup/restore on a **throwaway** PostgreSQL instance inside GitHub Actions. It is **not** production, not a VPS drill, and uses **static CI-only credentials** (never GitHub secrets, never clinic data).

## Scope

| In scope | Out of scope |
|----------|----------------|
| Pinned `postgres:16` image digest (same major as production) | Production hosts, SSH, DNS, deploy |
| `bot_migrator` / `bot_runtime` grants mirroring `roles_template.sql` | Real `POSTGRES_PASSWORD` / clinic DSNs |
| Full migration manifest + idempotent second run | Bot answer / Composer logic |
| 14 integration scenarios (real `psycopg` connections) | `test_pg_tenant_rls_integration.py` in offline CI |
| Custom-format `pg_dump` → `pg_restore --list` → full restore into **`g8_qual_restored`** | G7 VPS backup timer execution |

## CI job

Workflow: `.github/workflows/ci.yml` → job **`PostgreSQL qualification`** (separate from **Offline unit and contracts**).

Runner entrypoint: `python -m deploy.postgres.g8_qualification_runner`

`pg_isready`, `pg_dump`, and `pg_restore` run via `docker exec` against the pinned service container (`G8_POSTGRES_CONTAINER_ID` from CI job env). No `apt-get` client packages on the runner.

Pinned image (major **16**):

`postgres:16.8-bookworm@sha256:e75c0253ec375a157657c75bbb1705a8bbdd844d5f258973f9e3eb33cfcd9e33`

## Local runs

Requires Docker Desktop (or another host) with PostgreSQL 16 listening on `127.0.0.1:5432`, database `g8_qual_primary`, bootstrap user/password from `deploy/postgres/g8_disposable_constants.py`. Without that stack, treat the integration path as **UNKNOWN** locally; offline contracts (`tests/test_g8_postgres_qualification_contract.py`) still run in the standard offline CI job.

## Production image pin

Set `POSTGRES_IMAGE` on the VPS to the same major and a verified digest, for example:

`postgres:16.8-bookworm@sha256:e75c0253ec375a157657c75bbb1705a8bbdd844d5f258973f9e3eb33cfcd9e33`

(see `deploy/production/env.production.example`).
