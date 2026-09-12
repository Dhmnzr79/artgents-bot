# G4 server-side deploy assets (documentation only — do not run from this repo checkout on a laptop)

These files are **templates** for future VPS installation. They are excluded from the production Docker image (see repository `.dockerignore`).

## Security model

- **GitHub Actions** runs `Deploy production` manually from `main` only after G3 published an immutable GHCR digest.
- The workflow validates commit ancestry, G3 publish receipt, and GHCR tag digest **before** any SSH step.
- **No GHCR token**, database password, SMTP credentials, or provider keys are sent over SSH.
- GHCR pull credentials live only in **root-owned Docker config on the VPS**, not in GitHub SSH secrets.
- SSH uses **OpenSSH on GitHub-hosted runners** with:
  - `StrictHostKeyChecking=yes`
  - `UserKnownHostsFile` from repository secret `PRODUCTION_SSH_KNOWN_HOSTS`
  - **No** `ssh-keyscan`, **no** `StrictHostKeyChecking=no`
  - **No** third-party SSH actions
- Remote grammar is fixed: `deploy-production <40-char-sha> sha256:<64-hex>` — no paths, URLs, or extra arguments.

## Users and privileges

| Role | Purpose |
|------|---------|
| **deploy** (example name) | SSH login with forced command only; **not** root; **not** in `docker` group |
| **root** | Runs `/opt/artgents/bin/deploy-production` via passwordless sudo for that path only |

Deploy user must **not** receive `ALL`, `/bin/sh`, or direct `docker` access.

## Future GitHub repository configuration (not created in G4)

Repository **variables** (names only):

- `PRODUCTION_SSH_HOST`
- `PRODUCTION_SSH_PORT`
- `PRODUCTION_SSH_USER`

Repository **secrets** (names only):

- `PRODUCTION_SSH_PRIVATE_KEY`
- `PRODUCTION_SSH_KNOWN_HOSTS`

Never paste real keys, hosts, or known_hosts lines into Git documentation or commits.

## Host key verification

Obtain the VPS host key through a **trusted out-of-band channel** (console provider, serial console, or admin session already on the machine). Store the line in `PRODUCTION_SSH_KNOWN_HOSTS`. Do **not** populate known_hosts by running `ssh-keyscan` from CI.

## Installation order (VPS — G10 and earlier gates required)

**Do not execute these steps until:** G7 backup utility exists, G8 PostgreSQL qualification is done, and G10 VPS/DNS/TLS baseline is complete. Until then, the GitHub workflow must remain unused even if merged to `main`.

1. Copy `deploy-production.sh` to `/opt/artgents/bin/deploy-production` (root:root, `0750`).
2. Copy `deploy-receiver.sh` to e.g. `/opt/artgents/bin/deploy-receiver` (root:root, `0750`; deploy user may execute via forced command path only).
3. Install sudoers fragment from `artgents-deploy.sudoers.example` using `visudo -cf` after substituting `DEPLOY_USER`.
4. Ensure `/etc/artgents/production.env` exists (root-owned, not world-readable).
5. Ensure `/opt/artgents/current` points at an extracted release tree containing `deploy/production/compose.yml`.
6. Install G7 `/opt/artgents/bin/backup-postgres` — **G4 deploy fails without it**. Backup receipts must be regular files under `/var/lib/artgents/backups/receipts/` (canonical path containment enforced by deploy script).
7. Configure root-owned GHCR credential for `docker pull` of `ghcr.io/dhmnzr79/artgents-bot@sha256:…` only on the server.
8. Add **one** SSH public key for the deploy user with forced command, for example:

```text
command="/opt/artgents/bin/deploy-receiver",no-port-forwarding,no-agent-forwarding,no-X11-forwarding,no-pty ssh-ed25519 AAAA...comment
```

Replace the public key material with your real key **outside** this repository. Never commit private keys.

## State and receipts

Deploy receipts are written under `/var/lib/artgents/deploy/`:

- `current.json` — last **fully successful** deploy only
- `previous.json` — prior successful receipt (atomic rotate)

Failed deploys do **not** update `current.json`. Rollback is **G5** (separate workflow and script).

## G5 — manual production rollback (repository only)

- Workflow **`Rollback production`** (`.github/workflows/rollback-production.yml`) appears in GitHub UI only after merge to **`main`**. **Do not run** until G7 backup utility, G8 PostgreSQL qualification, and G10 VPS baseline are complete.
- Operator supplies only **`expected_current_sha`** (from the last successful deploy receipt or deploy workflow run) and **`confirm_rollback: true`**. **No** workflow input for target SHA, digest, image, path, or DB restore.
- Target image is chosen **only** from root-owned **`previous.json`** on the server (`current.json` → `previous.json` → immutable digest).
- **Rollback is not DB restore** and **does not change PostgreSQL schema**. No `migrate`, no SQL downgrade, no automatic DB restore during rollback.
- **Migration bundle fingerprint** (`migration_bundle_sha256` in schema **2** receipts) must match across current receipt, previous receipt, and a fresh extraction from the target image. Any mismatch → **`automatic rollback blocked: migration bundle differs`** **before** backup and **before** stopping Caddy/bot/admin — production keeps serving the current version.
- Schema **1** receipts (if ever present on a VPS) block automatic rollback (fail-closed).
- Requires at least **two** successful deployment receipts (`current.json` + `previous.json`).
- Uses the same SSH hardening and **`production-deploy`** concurrency group as G4 deploy (deploy and rollback cannot overlap).
- Remote grammar: `rollback-production <40-char-lowercase-sha>` via `deploy-receiver.sh` → `sudo -n /opt/artgents/bin/rollback-production`.
- Install `rollback-production.sh` and `migration-bundle-fingerprint.py` to `/opt/artgents/bin/` (root-owned). Extend sudoers with rollback script only (see `artgents-deploy.sudoers.example`).
- After a failed rollback **post-maintenance**, Caddy stays down, **`current.json` is unchanged**, and there is **no** automatic roll-forward — manual recovery is a separate procedure.

## Fail-closed staging (root script)

Order enforced by `deploy-production.sh`:

1. Validate SHA/digest and root
2. Exclusive `flock`
3. Preflight: Docker, Compose v2, env, compose file, **backup utility executable**
4. `docker pull` immutable digest reference
5. PostgreSQL up + healthy
6. **Backup gate** (`backup-postgres --reason pre-deploy --source-sha …`) — must succeed before migration
7. Stop Caddy (public ingress down during maintenance)
8. Explicit `docker compose run --rm migrate`
9. Recreate bot + admin; wait Docker health
10. Internal bot readiness `http://127.0.0.1:8000/health/ready` (HTTP 200)
11. Start Caddy with `--profile public` only after readiness
12. Write deploy receipt; atomically rotate `current.json` / `previous.json`

Any failure leaves public ingress off after Caddy was stopped and does not publish a new successful receipt.
