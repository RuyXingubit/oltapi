# Plano de Implementação: Migração e Alinhamento SDD (`oltapi`)

**Data:** 2026-10-14  
**Status:** Aprovado pelo Usuário (via `/grill-me`)

---

## 1. Objetivo
Migrar e consolidar a documentação e governança do projeto **OLTAPI** para o modelo **SDD (Spec-Driven Development / System Design & Specification Document)**, eliminando divergências documentais (drift), atualizando métricas e contratos, limpando artefatos temporários da árvore Git e reforçando a blindagem de produção e CI/CD.

---

## 2. Escopo das Alterações

### 2.1. Criação do Documento Mestre [`docs/SDD.md`](../SDD.md) e Navegação [`mkdocs.yml`](../../mkdocs.yml)
- Criar `docs/SDD.md` consolidando:
  1. Propósito, Escopo e Regras Inegociáveis de Engenharia (API-First OpenAPI 3.1.0, Proibição de Fabricantes Teóricos, Ports & Adapters com `BaseOLTDriver` + `@DriverRegistry.register`, Zero Dados Falsos, Segurança em Primeiro Lugar com UUIDv7, RBAC Multi-Tenant e Fernet AES).
  2. Topologia do Repositório (Diagrama Mermaid das camadas + Tabela de Componentes, Stacks e Licença AGPL-3.0).
  3. Governança de Contratos OpenAPI 3.1.0 (`75 rotas`, `96 operações HTTP`, `96 schemas`, `scripts/export_openapi.py`).
  4. Arquitetura do Backend (`app/`), Matriz dos 3 Concentradores Homologados em Hardware Físico (`Fiberhome`, `V-SOL`, `Parks`), Suíte de Conformidade (`BaseDriverComplianceTest`), Histórico das 6 Migrações Canônicas do Alembic e Arquitetura de Segurança/RBAC.
  5. Matriz de Implementação do `frontend/` (Flutter NOC) e Plano de Evolução em 3 Ondas Estritamente Sob Demanda (Ondas A, B e C).
- Adicionar `📐 Especificação SDD: SDD.md` no menu principal do `mkdocs.yml`.

### 2.2. Sincronização e Saneamento dos Documentos Existentes
- **[`docs/PRD.md`](../PRD.md):** Substituir menções a drivers teóricos pelos 3 fabricantes homologados em bancada física (`Fiberhome`, `V-SOL`, `Parks`), adicionar os módulos entregues (RBAC Multi-Tenant, Multi-FTP, Políticas PON/Cutover, Onboarding Wizard, Flutter NOC) e atualizar contagem para **253 testes unitários**.
- **[`docs/ROADMAP.md`](../ROADMAP.md):** Alinhar entregas concluídas com os 3 drivers reais, mover o Autofind Scanner para concluído, atualizar para **253 testes** e organizar o backlog com as 3 Ondas do Flutter NOC e futuras homologações físicas.
- **[`docs/SECURITY_BASELINE.md`](../SECURITY_BASELINE.md):** Expandir com RBAC Multi-Tenant/Rede Neutra, JWT Bearer, API Keys com hash SHA-256 e validação de subconjunto de escopos (`enforce_scope`, `enforce_olt`, `enforce_vlan`), criptografia Fernet AES em repouso (OLTs, FTP, Webhooks), proteção SSRF (`sanitize_webhook_url`) e bind local do PostgreSQL (`127.0.0.1:5432`).
- **[`docs/QA_AUDIT_REPORT.md`](../QA_AUDIT_REPORT.md):** Atualizar para os **253 testes automatizados** distribuídos nas 25 suítes reais em `tests/unit/`, removendo referências aos antigos testes de drivers teóricos e incluindo conformidade de drivers, Parks, Wizard V-SOL, RBAC multi-tenant, Políticas PON e Auditoria de Segurança.
- **[`docs/MANUAL_OPERACIONAL.md`](../MANUAL_OPERACIONAL.md):** Atualizar exemplos e lista de fabricantes suportados para `fiberhome`, `vsol` e `parks`, e contagem de testes para `253`.
- **[`docs/MANUAL_DESENVOLVEDOR.md`](../MANUAL_DESENVOLVEDOR.md), [`docs/index.md`](../index.md), [`docs/referencia-api.md`](../referencia-api.md) e [`docs/frontend_noc.md`](../frontend_noc.md):** Atualizar contagens (`253 testes`, `75 rotas / 96 operações / 96 schemas`), lista de routers em `app/api/v1/` e inclusão do fabricante `PARKS`.
- **[`README.md`](../../README.md) e [`CONTRIBUTING.md`](../../CONTRIBUTING.md):** Incluir a **Parks Fiberlink** na Matriz de Concentradores Homologados e no diagrama de arquitetura, atualizar badges (`253 backend tests`), linkar o `docs/SDD.md` e atualizar o guia de criação de drivers para usar `@DriverRegistry.register` e `BaseDriverComplianceTest`.

### 2.3. Higiene do Repositório, Docker e CI/CD
- Remover os 15 scripts temporários na raiz (`auto_deploy*.sh`, `patch_*.py`, `wait_and_deploy*.sh`, `test_dropdown.dart`, `test_registry.py`), `frontend/lib/core/network/api_client.dart.patch`, arquivos `.bak` em `frontend/lib/` e diretório `scratch/`.
- Atualizar [`.gitignore`](../../.gitignore) e [`.dockerignore`](../../.dockerignore) com `*.bak`, `*.patch`, `scratch/` e `site/`.
- Blindar [`docker-compose.prod.yml`](../../docker-compose.prod.yml) restringindo a porta do PostgreSQL a `127.0.0.1:${POSTGRES_PORT:-5432}:5432`.
- Adicionar verificação de sincronia do contrato OpenAPI em [`.github/workflows/release.yml`](../../.github/workflows/release.yml).

---

## 3. Verificação
- Executar `pytest` no backend (253 testes passando).
- Executar `flutter analyze` e `flutter test` no `frontend/`.
- Executar `python -m scripts.export_openapi` e verificar que não há drift em `docs/api_contracts/`.
