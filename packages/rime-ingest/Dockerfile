# Build stage
FROM ghcr.io/astral-sh/uv:python3.13-bookworm AS builder

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN uv sync --frozen --no-dev

# Runtime stage
FROM python:3.13-slim

WORKDIR /app
COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:${PATH}"
ENV CONTAINER_ENVIRONMENT=true

CMD ["rime"]
