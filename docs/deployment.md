# Deployment (k3s homelab)

The app runs on Cédric's k3s cluster, deployed by Flux from the **homelab** repo. This repo
builds the image and keeps *draft* manifests in `deploy/`; the homelab chat copies them into
`homelab/apps/woodshed/` and adds the NetworkPolicy, ExternalSecrets and Ingress. You never
touch the cluster or the homelab repo.

## Human-owned checks (do not edit)
| File | What |
| --- | --- |
| `Dockerfile`, `.dockerignore` | The image (python 3.12 slim, uv, uid 10001, port 8000, `MEDIA_DIR=/data/media`) |
| `.github/workflows/ci.yml` | `make setup && make check` on PRs and pushes |
| `.github/workflows/migrations.yml`, `tests/ci/check-migrations.sh`, `tests/ci/migcheck.py` | Migration check: one head, empty → head, `alembic check`, no-op re-run, downgrade/upgrade, data survives (seeded through `/api/items`) |
| `.github/workflows/image.yml`, `tests/ci/smoke-image.sh` | Builds the image, runs migrations in it, runs it read-only as uid 10001, curls `/healthz`, `/readyz`, `/login` |

There is no Docker in the devbox: you cannot build or run the image. CI does.

## How a change reaches the cluster (release task)
1. A PR is merged into `main`.
2. `.github/workflows/release.yml` runs the checks (`uses:` ci.yml, migrations.yml and image.yml
   as reusable workflows, or the same steps), computes the next version with
   `backend/scripts/next_version.py`, builds and pushes `ghcr.io/cecedabro/woodshed:X.Y.Z` and
   `:sha-<short>`, then pushes the tag `vX.Y.Z`. All in one workflow: tags pushed with
   `GITHUB_TOKEN` do not trigger other workflows.
3. Flux image automation sees the new tag and rolls it out.

## Runtime facts (agreed with the homelab side)
| What | Value |
| --- | --- |
| Port | container 8000, Service `woodshed` port 80 |
| Probes | liveness `GET /healthz`, readiness `GET /readyz` |
| Env (Secret `woodshed-app`) | `DATABASE_URL`, `APP_PASSWORD`, `SESSION_SECRET` |
| Env (plain) | `APP_ENV=production`, `MEDIA_DIR=/data/media` |
| DB Secret `woodshed-db` | `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` |
| DB host | Service `woodshed-db:5432` |
| Media | PVC `woodshed-media`, 20 Gi, `storageClassName: longhorn`, ReadWriteOnce, mounted at `/data` |
| Postgres | StatefulSet `woodshed-db`, `postgres:16.15`, 5 Gi Longhorn volumeClaimTemplate, `PGDATA` in a subdirectory |
| Resources | app 25m / 128Mi request, 384Mi limit; Postgres 50m / 256Mi, 512Mi limit |
| Security | runAsNonRoot, uid 10001, fsGroup 10001, readOnlyRootFilesystem, drop ALL caps, seccomp RuntimeDefault, emptyDir on `/tmp` |
| Rollout | replicas 1, strategy `Recreate` (RWO volume; migrations never run twice at once) |
| Placement | avoid node `k3s-gpu-01` (node affinity `NotIn`) |
| Hostname | `guitar.home.cedricschippers.dev` (Traefik Ingress + the home wildcard cert; LAN and Tailscale only) |
| Upload size | Traefik must allow bodies up to 100 MB (the homelab side sets this) |

Migrations run in an initContainer with the same image (`alembic upgrade head`, from `/app`),
after a `pg_isready` wait initContainer. Migrations must be safe to auto-deploy: add, don't
drop or rename in the same release that stops using something.

## Layout of `deploy/` (later tasks)
```
deploy/
  Makefile             # validate: kustomize build . | kubeconform -strict -summary
  kustomization.yaml   # namespace: woodshed
  namespace.yaml
  app.yaml             # Deployment (initContainers wait-for-db, migrate) + Service + media PVC
  postgres.yaml        # StatefulSet + Service
  ingress.yaml         # Ingress for guitar.home.cedricschippers.dev (entrypoint websecure)
  secret.example.yaml  # both Secrets with REPLACE_ME values; NOT in the kustomization
```
The image line in `app.yaml` is `ghcr.io/cecedabro/woodshed:0.1.0` with the marker comment
`# {"$imagepolicy": "flux-system:woodshed"}`. Workflows are linted with
`uvx --from actionlint-py actionlint`.
