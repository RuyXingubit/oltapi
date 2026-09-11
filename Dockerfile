# ------------------------------------------------------------------------------
# Multi-stage Dockerfile para OLTAPI (FastAPI + Python 3.13-slim)
# Seguro (non-root UID 1000), enxuto, com healthcheck e pronto para produção
# ------------------------------------------------------------------------------

# Estágio 1: Builder / Compilação de dependências
FROM python:3.13-slim AS builder

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
# Estágio 2: Runtime Final de Produção
# ------------------------------------------------------------------------------
FROM python:3.13-slim AS runner

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app"

# Copia pacotes compilados da etapa builder
COPY --from=builder /install /usr/local

# Cria grupo e usuário não-privilegiado (UID/GID 1000) e pastas de dados
RUN groupadd -g 1000 appgroup && \
    useradd -u 1000 -g appgroup -s /bin/sh -m appuser && \
    mkdir -p /app/data /app/backups && \
    chown -R appuser:appgroup /app

# Copia código-fonte da aplicação com permissões adequadas
COPY --chown=appuser:appgroup . /app

# Healthcheck nativo utilizando a biblioteca padrão do Python (sem dependência de curl/wget)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()" || exit 1

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]

