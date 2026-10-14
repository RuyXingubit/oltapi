# Walkthrough: Migração e Alinhamento SDD (`oltapi`)

**Data:** 2026-10-14  
**Plano Relacionado:** [`2026-10-14_migracao_e_alinhamento_sdd_plan.md`](2026-10-14_migracao_e_alinhamento_sdd_plan.md)

---

## 1. Resumo da Entrega

Todo o repositório **OLTAPI** foi migrado e alinhado para o padrão **SDD (Spec-Driven Development / System Design & Specification Document)** conforme as decisões aprovadas na sessão `/grill-me`:

1. **Fonte Única da Verdade ([`docs/SDD.md`](file:///Volumes/240/Code/oltapi/docs/SDD.md)):**
   - Criado o documento mestre `docs/SDD.md` consolidando os 5 pilares de engenharia, diagrama de topologia em 4 camadas, tabela de stacks e licenciamento AGPL-3.0, mapa completo dos 16 routers REST (`app/api/v1/`), matriz dos 3 concentradores homologados em bancada física (**Fiberhome**, **V-SOL** e **Parks Fiberlink**), suíte de conformidade (`BaseDriverComplianceTest`), histórico das 6 migrações canônicas do Alembic, arquitetura de segurança RBAC Multi-Tenant/Fernet/SSRF e matriz de implementação do `frontend/` (Flutter NOC) com as **3 Ondas Subsequentes Sob Demanda** (Ondas A, B e C).
   - Adicionado `📐 Especificação SDD: SDD.md` no topo da barra de navegação do [`mkdocs.yml`](file:///Volumes/240/Code/oltapi/mkdocs.yml).

2. **Saneamento de Drift Documental e Padronização de Métricas:**
   - **[`docs/PRD.md`](file:///Volumes/240/Code/oltapi/docs/PRD.md) e [`docs/ROADMAP.md`](file:///Volumes/240/Code/oltapi/docs/ROADMAP.md):** Removidas todas as menções a drivers teóricos antigos (Intelbras, Huawei, ZTE) como implementados, mantendo exclusivamente os 3 fabricantes homologados em bancada física (`Fiberhome`, `V-SOL` e `Parks`), movendo o Autofind Scanner para os marcos concluídos e estruturando o backlog nas 3 Ondas do Flutter NOC.
   - **[`docs/SECURITY_BASELINE.md`](file:///Volumes/240/Code/oltapi/docs/SECURITY_BASELINE.md):** Expandido para documentar autenticação dual (`X-API-Key` SHA-256 + `Bearer JWT`), RBAC Multi-Tenant (Rede Neutra), prevenção contra elevação de privilégio em chaves de API (`enforce_scope`, `enforce_olt`, `enforce_vlan`), criptografia Fernet AES em repouso (OLTs, FTP, SNMP e Webhooks), anti-SSRF (`sanitize_webhook_url`) e isolamento de porta do PostgreSQL em `127.0.0.1:5432`.
   - **[`docs/QA_AUDIT_REPORT.md`](file:///Volumes/240/Code/oltapi/docs/QA_AUDIT_REPORT.md):** Atualizado para refletir os **253 testes automatizados** distribuídos nos 25 módulos reais de `tests/unit/`, removendo referências aos antigos testes de drivers teóricos e cobrindo `test_driver_compliance.py`, `test_parks_driver.py`, `test_vsol_onboard_wizard.py`, `test_rbac_multi_tenant.py`, `test_pon_policies.py`, `test_ftp_endpoints.py` e `test_security_audit_fixes.py`.
   - **[`docs/MANUAL_OPERACIONAL.md`](file:///Volumes/240/Code/oltapi/docs/MANUAL_OPERACIONAL.md), [`docs/MANUAL_DESENVOLVEDOR.md`](file:///Volumes/240/Code/oltapi/docs/MANUAL_DESENVOLVEDOR.md), [`docs/index.md`](file:///Volumes/240/Code/oltapi/docs/index.md), [`docs/referencia-api.md`](file:///Volumes/240/Code/oltapi/docs/referencia-api.md), [`docs/frontend_noc.md`](file:///Volumes/240/Code/oltapi/docs/frontend_noc.md) e [`docs/HOMOLOGACAO_PARKS_FIBERLINK.md`](file:///Volumes/240/Code/oltapi/docs/HOMOLOGACAO_PARKS_FIBERLINK.md):** Sincronizados com os 3 drivers reais, 16 routers REST, **253 testes unitários** e **75 rotas (96 operações HTTP) / 96 esquemas OpenAPI**.
   - **[`README.md`](file:///Volumes/240/Code/oltapi/README.md) e [`CONTRIBUTING.md`](file:///Volumes/240/Code/oltapi/CONTRIBUTING.md):** Incluída a **Parks Fiberlink 10008S / Série 21000** na Matriz de Concentradores Homologados e no diagrama de arquitetura, atualizado o badge para `253 backend + 8 flutter passed`, adicionado link para o `docs/SDD.md` e atualizado o guia de contribuição para usar `@DriverRegistry.register` e `BaseDriverComplianceTest`.

3. **Higiene do Repositório, Docker e CI/CD:**
   - Removidos da árvore Git os 15 scripts temporários na raiz (`auto_deploy*.sh`, `patch_*.py`, `wait_and_deploy*.sh`, `test_dropdown.dart`, `test_registry.py`), o arquivo `frontend/lib/core/network/api_client.dart.patch`, arquivos `.bak` em `frontend/lib/` e o diretório `scratch/`.
   - Atualizados [`.gitignore`](file:///Volumes/240/Code/oltapi/.gitignore) e [`.dockerignore`](file:///Volumes/240/Code/oltapi/.dockerignore) com `*.bak`, `*.patch`, `site` e `frontend`.
   - Blindado o [`docker-compose.prod.yml`](file:///Volumes/240/Code/oltapi/docker-compose.prod.yml#L11) restringindo o bind da porta do PostgreSQL para `127.0.0.1:${POSTGRES_PORT:-5432}:5432`.
   - Adicionado o passo `Verify OpenAPI Contract Sync` em [`.github/workflows/release.yml`](file:///Volumes/240/Code/oltapi/.github/workflows/release.yml#L48-L51).

---

## 2. Validação Executada
- **Sincronia de Contratos OpenAPI:** `python -m scripts.export_openapi` (`75 rotas`, `96 operações`, `96 schemas` sincronizados sem drift).
- **Suíte de Testes Backend (`pytest`):** `253 passed` (100% de aprovação).
