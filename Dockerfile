# Human-owned (SPEC 11.1). The image smoke test (tests/ci/smoke-image.sh) runs it in CI.
# ---- builder ----
# The uv image only holds the uv binary, so copy uv into a Python image that matches the
# runtime: the venv's interpreter path must exist in both stages.
FROM python:3.12.16-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=/usr/local/bin/python3.12

WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# ---- runtime ----
FROM python:3.12.16-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    MEDIA_DIR=/data/media

WORKDIR /app
COPY --from=builder /app/.venv .venv
COPY backend .

RUN useradd --no-create-home --uid 10001 app
USER 10001
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
