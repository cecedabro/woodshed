# Build and run the image locally (for the human)

Try the production image on the Mac (Docker Desktop) before CI and the cluster. Run from the
repo root.

1. Build (arm64 on Apple Silicon is fine for testing; `--platform linux/amd64` builds what
   the cluster runs, slower):
   ```bash
   docker build -t woodshed:local .
   ```
2. Network and database:
   ```bash
   docker network create ws-test
   ```
   ```bash
   docker run -d --name ws-db --network ws-test -e POSTGRES_USER=woodshed -e POSTGRES_PASSWORD=woodshed -e POSTGRES_DB=woodshed postgres:16.15
   ```
3. Migrations (the cluster does this in an initContainer; wait a few seconds for Postgres first):
   ```bash
   docker run --rm --network ws-test -e DATABASE_URL=postgresql+psycopg://woodshed:woodshed@ws-db:5432/woodshed woodshed:local alembic upgrade head
   ```
4. Run it like the cluster (read-only root, only `/tmp` and `/data` writable):
   ```bash
   docker run -d --name ws-app --network ws-test --read-only --tmpfs /tmp --tmpfs /data:uid=10001 -p 8000:8000 -e DATABASE_URL=postgresql+psycopg://woodshed:woodshed@ws-db:5432/woodshed woodshed:local
   ```
   Open http://localhost:8000 (development password: `dev-password`). Logs: `docker logs -f ws-app`.
   Recording needs HTTPS or `localhost`, so test the microphone on `localhost`, not a LAN IP.
5. Check:
   ```bash
   curl -s localhost:8000/healthz && curl -s localhost:8000/readyz
   ```
6. Clean up (deletes the test data):
   ```bash
   docker rm -f ws-app ws-db && docker network rm ws-test
   ```
