#!/usr/bin/env bash
# Human-owned image smoke test (SPEC 11.4), run by .github/workflows/image.yml.
# Builds nothing: expects the image IMAGE to exist locally and a Postgres at DB_URL
# reachable from containers on the host network.
set -euo pipefail

: "${IMAGE:?set IMAGE, e.g. woodshed:ci}"
: "${DB_URL:?set DB_URL, e.g. postgresql+psycopg://smoke:smoke@localhost:5432/smoke}"
NAME=woodshed-smoke
PASSWORD=smoke-password-not-default

cleanup() { docker logs "$NAME" 2>&1 | tail -n 50 || true; docker rm -f "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

echo "== migrations in the image"
docker run --rm --network host -e DATABASE_URL="$DB_URL" "$IMAGE" alembic upgrade head

echo "== production refuses the development password"
if docker run --rm --network host -e APP_ENV=production -e DATABASE_URL="$DB_URL" \
    "$IMAGE" python -c "from app.main import create_app; create_app()" >/dev/null 2>&1; then
  echo "APP_ENV=production started with default secrets"; exit 1
fi

echo "== run like the cluster does (read-only root, uid 10001, /tmp and /data writable)"
docker run -d --name "$NAME" --network host --read-only --tmpfs /tmp --tmpfs /data:uid=10001 \
  --user 10001 -e APP_ENV=production -e DATABASE_URL="$DB_URL" -e MEDIA_DIR=/data/media \
  -e APP_PASSWORD="$PASSWORD" -e SESSION_SECRET=smoke-session-secret-0123456789abcdef \
  "$IMAGE" >/dev/null

for _ in $(seq 1 30); do
  if curl -fsS http://localhost:8000/healthz >/dev/null 2>&1; then break; fi
  sleep 1
done

echo "== probes and pages"
curl -fsS http://localhost:8000/healthz
curl -fsS http://localhost:8000/readyz
code=$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/login)
if [ "$code" != "200" ] && [ "$code" != "404" ]; then  # 404 until the login task exists
  echo "/login returned $code"; exit 1
fi
echo
echo "image smoke test passed"
