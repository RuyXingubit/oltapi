# Walkthrough: Ajustes Finais de Integração & Infraestrutura do MVP

**Data:** 2026-10-16  
**Plano Relacionado:** `docs/planos/2026-10-16_mvp_infra_integration_plan.md`

## Resumo das Entregas

1. **Rota `/health` no Proxy Reverso Caddy (`frontend/Caddyfile`)**
   - Incluído `/health` no matcher `@api` (`path /api/* /health /docs* /openapi.json`), garantindo que o indicador de latência e disponibilidade (`Online • Xms`) na Topbar do NOC consulte diretamente o container `oltapi:8000`.
2. **Alinhamento da Stack Docker Local & Variáveis (`docker-compose.yml` e `.env.example`)**
   - Adicionada a variável `JWT_SECRET` no serviço `oltapi` do `docker-compose.yml` e documentada no `.env.example`.
   - Adicionado o serviço `frontend` no `docker-compose.yml` (compilando `./frontend/Dockerfile` localmente, aguardando `oltapi` ficar saudável via healthcheck e expondo `${FRONTEND_PORT:-8080}:80` com volumes `caddy_data` e `caddy_config`).
3. **Pipeline CI/CD Full-Stack & Economia de Minutos (`.github/workflows/release.yml` e `.github/workflows/ci.yml`)**
   - Criado o job paralelo `test-frontend` (`flutter pub get`, `flutter analyze`, `flutter test` com `subosito/flutter-action@v2` e `cache: true`, `timeout-minutes: 10`).
   - O job `release-and-publish` em `release.yml` agora exige `needs: [test-backend, test-frontend]` antes de publicar novas imagens no Docker Hub.
   - Isolado o cache GHA do Docker Buildx em `scope=backend` e `scope=frontend` para evitar sobrescrita de camadas entre as imagens `xingubit/oltapi` e `xingubit/oltapi-frontend`.
   - Removida a duplicidade de disparo na branch `master` em `ci.yml`.

## Validações Executadas
- `python -m scripts.export_openapi` -> `75 endpoints` e `96 schemas` sincronizados.
- `pytest tests/ -q` -> `253 passed`.
- `flutter analyze` -> `No issues found!`.
- `flutter test` -> `21/21 All tests passed!`.
- `docker compose config -q` & `docker compose -f docker-compose.prod.yml --env-file .env.example config -q` -> OK.
