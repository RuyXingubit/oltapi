# Plano de Implementação: Ajustes Finais de Integração & Infraestrutura do MVP

**Data:** 2026-10-16  
**Status:** Aprovado e Concluído

## Objetivo
Alinhar os **3 pontos de integração entre Frontend NOC, Proxy Reverso Caddy, Docker Compose e CI/CD** para que o MVP rode 100% integrado em containers (tanto em ambiente local via `docker compose up -d --build` quanto em produção via `docker-compose.prod.yml` e GitHub Actions), eliminando qualquer atrito operacional.

## Alterações Aprovadas
1. **`frontend/Caddyfile`:** Adicionado `/health` ao matcher `@api` (`path /api/* /health /docs* /openapi.json`) para que o healthcheck do NOC (`ApiClient.checkHealth()`) seja encaminhado ao container `oltapi:8000`.
2. **`docker-compose.yml` & `.env.example`:** Adicionada a variável `JWT_SECRET`, a porta `FRONTEND_PORT` e o serviço `frontend` com build local (`./frontend/Dockerfile`) e volumes `caddy_data` / `caddy_config`.
3. **`.github/workflows/release.yml` & `.github/workflows/ci.yml`:**
   - Separação em jobs paralelos de falha rápida (`test-backend` + `test-frontend` executando `flutter analyze` e `flutter test` com `cache: true`).
   - Isolamento de escopo no cache GHA do Docker Buildx (`scope=backend` e `scope=frontend`).
   - Eliminação de gatilho duplicado na branch `master` entre `ci.yml` e `release.yml`.
