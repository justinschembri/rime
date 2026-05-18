# Build stage with uv and build dependencies
FROM ghcr.io/astral-sh/uv:python3.13-bookworm AS builder

WORKDIR /app
COPY . /app/
RUN uv sync --frozen

# Runtime stage - slim final image
FROM python:3.13-slim

WORKDIR /app
COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:${PATH}"
RUN ls -R /app

CMD ["python", "/app/src/rime/main.py"]
