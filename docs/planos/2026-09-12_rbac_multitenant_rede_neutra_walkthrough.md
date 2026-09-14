# Walkthrough: Implementação de RBAC Hierárquico, Multi-Tenancy & Rede Neutra

Concluímos com sucesso a reformulação completa da camada de autenticação e controle de acesso da `oltapi`. O sistema agora oferece suporte a múltiplos inquilinos com isolamento geográfico de técnicos por OLT, segregação estrita de VLANs para parceiros de Rede Neutra e emissão de chaves de API secundárias granulares.

---

## 1. O que foi Implementado

### 1.1. Modelos de Dados & Migração Alembic (UUIDv7)
- **Tabela `tenants`:** Organizações do sistema com segregação de tipo (`PROVIDER_OWNER` vs `NEUTRAL_OPERATOR`).
- **Tabela `users`:** Usuários e técnicos para acesso Web UI com senhas criptografadas em **Bcrypt**.
- **Tabela `user_olt_permissions`:** Amarração de técnicos a OLTs específicas (ex: Técnico de VTX só opera em VTX).
- **Tabela `tenant_vlan_allocations`:** Alocação de VLANs autorizadas por Tenant e por OLT `(tenant_id, olt_id, vlan_id)`.
- **Tabela `api_keys`:** Chaves de API secundárias para ERPs externos, armazenando hash **SHA-256**, prefixo visível (`olt_live_...`) e escopos granulares em JSON.
- **Tabela `onus_inventory`:** Coluna `tenant_id` adicionada para titularidade direta de cada ONU no inventário.
- **Migração Alembic:** [a38c91d4e5f0_add_rbac_and_multitenant_tables.py](file:///Volumes/240/Code/oltapi/alembic/versions/a38c91d4e5f0_add_rbac_and_multitenant_tables.py) com suporte a batch mode para SQLite e PostgreSQL.
- **First-Run Setup Wizard (Sem Seed Estático / Zero Dados Falsos):**
  - O banco de dados inicia 100% limpo, sem credenciais hardcoded nem provedores fictícios.
  - O endpoint `GET /api/v1/setup/status` orienta se o sistema já está configurado (`is_configured: bool`).
  - O endpoint `POST /api/v1/setup/init` é protegido pela Master API Key do `.env` e permite ao administrador cadastrar seu Provedor real e sua conta Super Admin com senha forte.
  - Uma vez inicializado, o endpoint `/setup/init` é bloqueado permanentemente com `403 Forbidden` por segurança.
- **Proteção do Histórico Local (`docs/brainstorming/`):**
  - A pasta `docs/brainstorming/` foi desindexada do Git (`git rm -r --cached`) e incluída no `.gitignore`, permanecendo estritamente no disco local durante o desenvolvimento sem ir para o GitHub.

### 1.2. Motor de Segurança & RBAC
- **[app/core/security.py](file:///Volumes/240/Code/oltapi/app/core/security.py):**
  - Funções `get_password_hash` e `verify_password` usando Bcrypt.
  - Funções `create_access_token` e `decode_access_token` usando JWT (HS256).
  - Funções `generate_api_key` e `hash_api_key` gerando tokens seguros com prefixo e hash SHA-256.
- **[app/core/rbac.py](file:///Volumes/240/Code/oltapi/app/core/rbac.py):**
  - Classe `SecurityContext` com métodos defensivos:
    - `enforce_scope(scope)`: Bloqueia ações não autorizadas com `403 Forbidden`.
    - `enforce_olt(olt_id)`: Bloqueia técnicos de acessar OLTs fora do seu POP.
    - `enforce_vlan(olt_id, vlan)`: Bloqueia parceiros de rede neutra de provisionar fora das suas VLANs contratadas.
- **[app/api/deps.py](file:///Volumes/240/Code/oltapi/app/api/deps.py):**
  - Dependência `get_security_context` avaliando `X-API-Key` (Master Key do `.env` ou Chave Dinâmica do banco) e `Authorization: Bearer <JWT>`.

### 1.3. Novos Endpoints REST
- **`/api/v1/setup` ([endpoints_setup.py](file:///Volumes/240/Code/oltapi/app/api/v1/endpoints_setup.py)):**
  - `GET /setup/status`: Consulta se o sistema já teve seu setup inicial concluído.
  - `POST /setup/init`: Setup inicial via Master API Key com bloqueio anti-reinicialização.
- **`/api/v1/auth` ([endpoints_auth.py](file:///Volumes/240/Code/oltapi/app/api/v1/endpoints_auth.py)):**
  - `POST /auth/login`: Autentica login/senha e retorna JWT.
  - `GET /auth/me`: Retorna perfil, permissões de OLT e VLANs alocadas.
- **`/api/v1/tenants` ([endpoints_tenants.py](file:///Volumes/240/Code/oltapi/app/api/v1/endpoints_tenants.py)):**
  - `GET /tenants`, `POST /tenants`, `GET /tenants/{id}`.
  - `POST /tenants/{id}/vlans`, `DELETE /tenants/{id}/vlans/{vlan_id}`.
- **`/api/v1/users` ([endpoints_users.py](file:///Volumes/240/Code/oltapi/app/api/v1/endpoints_users.py)):**
  - `GET /users`, `POST /users`, `GET /users/{id}`, `PATCH /users/{id}`, `DELETE /users/{id}`.
- **`/api/v1/api-keys` ([endpoints_api_keys.py](file:///Volumes/240/Code/oltapi/app/api/v1/endpoints_api_keys.py)):**
  - `GET /api-keys`, `POST /api-keys` (retorna chave pura uma única vez), `DELETE /api-keys/{id}` (revogação instantânea).

### 1.5. Interface Web de Bancada & First-Run Setup Wizard (Opção 3)
- **Tecnologia & Arquitetura:**
  - Single Page Application em Vanilla HTML5, Modern Vanilla JS e CSS Tokens com design *Dark Glassmorphism*.
  - Zero dependências de build pesadas (Node/Webpack) para deploy enxuto em produção.
  - Servida nativamente pelo FastAPI na rota raiz `/` e `/static`.
- **First-Run Setup Wizard:**
  - Ao detectar o banco limpo (`is_configured == false`), apresenta a tela de configuração inicial para preenchimento da Master Key do `.env`, Razão Social e dados do Super Admin real.
  - Bloqueio permanente pós-inicialização (`403 Forbidden`).
- **Bancada de Laboratório & Radar:**
  - Seletor dinâmico de OLTs autorizadas para o operador.
  - Radar de ONUs não autorizadas com busca por serial e polling automático a cada 10s.
  - Modal inteligente de provisionamento (Router vs Bridge, seleção de VLAN e perfil de fabricante).
  - Terminal em tempo real exibindo o retorno dos comandos CLI aplicados na OLT.
  - Inventário com consulta óptica (RX/TX Power) e ações de ciclo de vida (Reboot, Suspend, Resume, Deprovision).

![Tela do Setup Inicial na Web](/Users/ruy/.gemini/antigravity-ide/brain/bed2a7b0-ad67-4590-a8dc-ef89f43427ec/setup_wizard_screen_1789264630449.png)

---

## 2. Resultados dos Testes Automatizados

Executamos a suíte completa de testes unitários com pytest:

```bash
.venv/bin/pytest tests/ -v
```

### Destaques dos Testes:
1. `test_setup_wizard_first_run_and_lockdown`: ✅ Validação do setup inicial com Master Key e bloqueio pós-configuração (`403`).
2. `test_serve_ui_root_endpoint` & `test_serve_static_css_and_js`: ✅ Entrega correta da Interface Web e assets estáticos via FastAPI.
3. `test_master_admin_access_everything`: ✅ Acesso irrestrito com a chave mestra do `.env` mantido.
4. `test_login_and_get_profile`: ✅ Emissão de JWT e perfil via `/auth/me`.
5. `test_neutral_operator_vlan_and_scope_isolation`: ✅ Operadora Neutra isolada na sua VLAN alocada.
6. `test_field_tech_olt_restriction`: ✅ Técnico restrito por POP/OLT.
7. `test_dynamic_api_key_revocation`: ✅ Revogação instantânea de credenciais dinâmicas.

```
======================= 173 passed, 2 warnings in 43.33s =======================
```

**Total: 173 testes aprovados com 100% de sucesso.**
Zero dados falsos. Zero credenciais hardcoded.

