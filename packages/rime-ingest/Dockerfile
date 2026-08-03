# Build stage
FROM ghcr.io/astral-sh/uv:python3.13-bookworm AS builder

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev

# Runtime stage
FROM python:3.13-slim

# Release identity comes from the git tag via CI --build-arg (default: local/dev).
ARG VERSION=dev
ENV RIME_INGEST_VERSION=${VERSION}

WORKDIR /app
COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:${PATH}"
ENV CONTAINER_ENVIRONMENT=true

CMD ["python", "src/rime_ingest/main.py"]
