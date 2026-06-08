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

EXPOSE 8080

CMD ["rime-server-http"]
