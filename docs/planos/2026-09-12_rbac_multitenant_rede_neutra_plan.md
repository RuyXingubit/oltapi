# Plano de Implementação Consolidado: Autenticação Híbrida, RBAC Granular & Rede Neutra

## Resumo das Decisões Confirmadas com o Usuário
1. **Inquilinos e Usuários criados pelo Admin:**
   - O Admin cadastra o Inquilino (`Tenant`), define se é o Provedor ou Operadora de Rede Neutra, e cria seus respectivos usuários/chaves.
   - Cada usuário/chave possui **acesso total** (NOC / ERP central) OU **acesso restrito a uma ou mais OLTs com VLANs estritamente restritas**.
2. **Descoberta Flexível de ONUs (Web & API):**
   - Suporte a listagem geral da porta/OLT E filtro direto por serial (`GET /api/v1/olts/{olt_id}/unauthorized?serial=...`).
   - Tanto via API (ERP fazendo polling) quanto na futura Web UI (técnico aguardando o serial sincronizar), o operador localiza a ONU e a autoriza escolhendo:
     - Modo de operação: **Router** (PPPoE/IPv4/IPv6) ou **Bridge**;
     - Perfil: Padrão ou Fabricante terceiro (ex: perfil VEIP no caso de Fiberhome);
     - VLAN: Escolhida dentre as VLANs contratadas/alocadas para seu inquilino.
3. **Escopos Granulares:**
   - Chaves de API podem ser limitadas por escopos finos (`onus:read`, `onus:discover`, `onus:provision`, `onus:deprovision`, `onus:actions`, `diagnostics:read`, `olts:read`, `backups:read`, `api_keys:manage`).

---

## User Review Required

> [!IMPORTANT]
> **Segurança e Isolamento L2 Garantidos:**
> A alteração fecha qualquer brecha de uso indevido de VLANs de outros clientes ou de acesso a OLTs não contratadas. Chaves de terceiros ou técnicos de campo nunca conseguirão disparar comandos fora de seu escopo geográfico e de VLAN.
>
> **Chave Mestra do .env Preservada:**
> A chave atual continua funcionando com permissões totais `["*"]` como Super Admin de contingência.

---

## Ordem de Implementação Proposta

### Etapa 1: Modelos e Migração de Banco de Dados
1. Criar modelos SQLAlchemy em [app/db/models.py](file:///Volumes/240/Code/oltapi/app/db/models.py):
   - `TenantModel`
   - `UserModel`
   - `UserOLTPermissionModel`
   - `TenantVLANAllocationModel`
   - `APIKeyModel`
   - Coluna `tenant_id` em `ONUInventoryModel`
2. Criar schemas Pydantic em `app/models/tenant.py`, `app/models/user.py`, `app/models/api_key.py`, `app/models/setup.py`.
3. Criar migração Alembic em `alembic/versions/`.
4. **Remoção do Seed Estático & Implementação do First-Run Setup Wizard**:
   - Zero dados falsos e sem senhas padrão: remover `seed_default_tenant_and_admin` de [app/db/init_db.py](file:///Volumes/240/Code/oltapi/app/db/init_db.py).
   - Criar `GET /api/v1/setup/status`: retorna se o sistema já possui o Tenant Provedor cadastrado (`is_configured: bool`).
   - Criar `POST /api/v1/setup/init`: exige `X-API-Key` mestra do `.env`, cadastra a empresa real e o admin real, e bloqueia chamadas futuras permanentemente (403 Forbidden).

### Etapa 2: Motor de Segurança & RBAC
1. Adicionar em [app/core/security.py](file:///Volumes/240/Code/oltapi/app/core/security.py):
   - Hash de senhas (Bcrypt via `passlib` ou `bcrypt`).
   - Geração e verificação de JWT tokens (`PyJWT`).
   - Geração e hash SHA-256 de chaves de API dinâmicas com prefixo `olt_live_`.
2. Criar [app/core/rbac.py](file:///Volumes/240/Code/oltapi/app/core/rbac.py):
   - Classe `SecurityContext` com métodos defensivos:
     - `enforce_scope(scope)`
     - `enforce_olt(olt_id)`
     - `enforce_vlan(olt_id, vlan)`
3. Atualizar dependências em [app/api/deps.py](file:///Volumes/240/Code/oltapi/app/api/deps.py) para resolver o `SecurityContext` a partir de `X-API-Key` (mestre ou banco) ou `Authorization: Bearer <JWT>`.

### Etapa 3: Endpoints Administrativos & Gestão de Acessos
1. [app/api/v1/endpoints_auth.py](file:///Volumes/240/Code/oltapi/app/api/v1/endpoints_auth.py):
   - `POST /auth/login` (gera JWT para Web UI).
   - `GET /auth/me` (perfil do usuário, OLTs e VLANs permitidas).
2. [app/api/v1/endpoints_tenants.py](file:///Volumes/240/Code/oltapi/app/api/v1/endpoints_tenants.py):
   - CRUD de Inquilinos (`tenants`) e alocação de VLANs por OLT.
3. [app/api/v1/endpoints_users.py](file:///Volumes/240/Code/oltapi/app/api/v1/endpoints_users.py):
   - CRUD de Usuários e vinculação de permissões por OLT.
4. [app/api/v1/endpoints_api_keys.py](file:///Volumes/240/Code/oltapi/app/api/v1/endpoints_api_keys.py):
   - Geração de API Keys com escopos e revogação imediata.

### Etapa 4: Blindagem dos Endpoints Existentes
1. Atualizar [app/api/v1/endpoints_provision.py](file:///Volumes/240/Code/oltapi/app/api/v1/endpoints_provision.py):
   - `GET /olts/{olt_id}/unauthorized`: Checa `enforce_olt` e suporta `?serial=...`.
   - `POST /olts/{olt_id}/onus`: Checa `enforce_olt`, `enforce_scope("onus:provision")` e `enforce_vlan(olt_id, req.vlan)`.
   - `DELETE /olts/{olt_id}/onus/{serial}`: Checa `enforce_olt` e `enforce_scope("onus:deprovision")`.
   - `POST /olts/{olt_id}/onus/{serial}/reboot|suspend|resume`: Checa `enforce_olt` e `enforce_scope("onus:actions")`.
2. Atualizar [app/api/v1/endpoints_onu_inventory.py](file:///Volumes/240/Code/oltapi/app/api/v1/endpoints_onu_inventory.py):
   - Isolar inventário de ONUs para que operadoras neutras vejam apenas as suas ONUs.
3. Atualizar [app/api/v1/endpoints_olts.py](file:///Volumes/240/Code/oltapi/app/api/v1/endpoints_olts.py) e [app/api/v1/endpoints_diagnostics.py](file:///Volumes/240/Code/oltapi/app/api/v1/endpoints_diagnostics.py):
   - Aplicar `enforce_olt` e checagem de escopos respectivos.

### Etapa 5: Testes Unitários de Cobertura Rigorosa
- Criar `tests/unit/test_rbac_multi_tenant.py` com cobertura de 100% dos fluxos de autorização (concluído com 171 testes passando).

### Etapa 6: Interface Web de Bancada & First-Run Wizard (Opção 3)
1. **Estrutura Estática & Montagem FastAPI:**
   - Criar diretório `app/static/` com `index.html`, `css/style.css` e `js/app.js`.
   - No `app/main.py`, montar `StaticFiles(directory=settings.BASE_DIR / "app" / "static", html=True)` na rota `/app` ou `/`.
2. **Fluxo First-Run Setup Wizard:**
   - Ao carregar, verifica `GET /api/v1/setup/status`.
   - Se `is_configured: false`, redireciona imediatamente para o Wizard de Setup Inicial.
   - O administrador insere a Master API Key do `.env`, o nome real do seu provedor, seu nome, e-mail e senha.
   - Envia `POST /api/v1/setup/init` e bloqueia o setup permanentemente.
3. **Fluxo de Autenticação & Sessão:**
   - Tela de Login (`/login`) para técnicos e administradores (`POST /api/v1/auth/login`).
   - Armazenamento de JWT em `sessionStorage` e hidratação de perfil via `GET /api/v1/auth/me`.
4. **Radar de Bancada & Provisionamento Ágil:**
   - Seletor de OLTs ativas autorizadas para o usuário.
   - Radar de ONUs não autorizadas (`GET /api/v1/olts/{id}/unauthorized?serial=...`) com busca em tempo real.
   - Modal de provisionamento rápido:
     - Modo Router (PPPoE/IPv4/IPv6) vs Bridge.
     - Perfil de Fabricante (Padrão ou Terceiro/VEIP).
     - Seleção de VLANs (filtradas pelas VLANs autorizadas para o inquilino logado).
     - Disparo com feedback visual imediato e registro no terminal de execução.
5. **Diagnósticos & Ciclo de Vida da ONU:**
   - Consulta de RX/TX Power com badge de status visual.
   - Ações rápidas de ciclo de vida: Reiniciar, Suspender, Reativar e Desprovisionar.
6. **Gestão Administrativa (Apenas Super Admin):**
   - Gestão de Inquilinos / Rede Neutra e alocação de VLANs por OLT.
   - Gestão de Usuários e amarração de técnicos a POPs específicos.
   - Emissão e revogação imediata de API Keys.

---

## Plano de Verificação
- Rodar a suíte completa de testes com `pytest tests/ -v` (171 testes).
- Iniciar o servidor local e validar o carregamento da UI via browser/curl.
- Validar o fluxo completo do Setup Wizard, Login, Descoberta e Provisionamento na interface.
