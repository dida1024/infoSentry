---
name: release_package_deploy
description: Use when preparing a version release and deploying infoSentry with the repository packaging and deployment scripts.
---

# Release Package Deploy

Use this skill to publish a release with the built-in scripts in this repo.

## Scope
- Monorepo release based on Docker images.
- Package script: `scripts/pack.sh`
- Deploy script: `scripts/deploy.sh`

## Prerequisites
- Docker Engine is running.
- `docker compose` is available.
- Release env values are already prepared (no hardcoded secrets).
- Run from repo root.

## Standard Flow
1. Optional quality gate:
   - Backend: `uv run pytest` and `uv run mypy src`
   - Frontend: `npm run lint` and `npm run build`
2. Create release package:
   - Full build: `./scripts/pack.sh <release_name>`
   - Reuse existing images: `./scripts/pack.sh --no-build <release_name>`
3. Verify output archive exists:
   - `dist/<release_name>.tar.gz`
4. Deploy the archive:
   - `./scripts/deploy.sh dist/<release_name>.tar.gz`
5. Verify deployment:
   - `docker compose ps`
   - `docker compose logs -f api` (or target service)

## Example
```bash
./scripts/pack.sh release-20260214-v1
./scripts/deploy.sh dist/release-20260214-v1.tar.gz
docker compose ps
```

## Failure Handling
- If `pack.sh` reports missing images, re-run without `--no-build`.
- If `deploy.sh` cannot find package, pass an absolute path or check `dist/`.
- If services fail health checks, inspect logs before retrying:
  - `docker compose logs --tail=200 api`
  - `docker compose logs --tail=200 worker_agent`

