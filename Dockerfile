# ------------------------------------------------------------------------------
# Multi-stage Dockerfile para OLT API (FastAPI + Python 3.11)
# Seguro (non-root), enxuto e otimizado para produção
# ------------------------------------------------------------------------------

FROM python:3.11-slim AS builder

WORKDIR /build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ------------------------------------------------------------------------------
# Final Runtime Stage
# ------------------------------------------------------------------------------
FROM python:3.11-slim AS runner

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/install/bin:$PATH" \
    PYTHONPATH="/app"

# Copia pacotes compilados da etapa builder
COPY --from=builder /install /usr/local

# Cria usuário não-privilegiado para segurança
RUN groupadd -g 1000 appgroup && \
    useradd -u 1000 -g appgroup -s /bin/sh -m appuser && \
    mkdir -p /app/backups /app/data && \
    chown -R appuser:appgroup /app

COPY --chown=appuser:appgroup . /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
