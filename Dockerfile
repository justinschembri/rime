# Build stage — install uv via pip (avoids ghcr.io auth issues)
FROM python:3.13-bookworm AS builder

RUN pip install uv

WORKDIR /app
COPY . /app/
RUN uv sync --frozen

# Runtime stage — minimal image, no build tools
FROM python:3.13-slim

# git is needed by rime-ctrl for ops repo polling
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:${PATH}"

CMD ["python", "/app/src/rime/main.py"]
