# Walkthrough: Auditoria de Segurança e Blindagem RBAC (Test-First)

## Resumo da Entrega
Execução completa da blindagem de segurança do **OLTAPI** seguindo o fluxo **Test-First (TDD)**:
1. **Red Phase**: Criação de 6 testes de segurança em [`tests/unit/test_security_audit_fixes.py`](file:///Volumes/240/Code/oltapi/tests/unit/test_security_audit_fixes.py) reproduzindo os vetores identificados na auditoria (elevação de privilégios via API Keys, bypass de RBAC/isolamento de OLT em backups/config/VLANs/políticas/scanner/FTP, SSRF e segredos planos em Webhooks, e `NameError` em `decrypt_password`).
2. **Green Phase**: Implementação cirúrgica das correções sem quebrar nenhum comportamento existente.
3. **Validação de Regressão e Contratos**: Todos os **253 testes unitários** (247 originais + 6 novos) passando com 0 falhas, e contratos OpenAPI (`openapi.yaml` e `openapi.json`) devidamente sincronizados.

---

## Principais Correções Implementadas

### 1. Prevenção de Elevação de Privilégio em Chaves de API (`endpoints_api_keys.py`)
- Exigência explícita de `ctx.enforce_scope("api_keys:manage")` nas rotas `GET /api-keys`, `POST /api-keys` e `DELETE /api-keys/{key_id}`.
- Validação de subconjunto de escopos: um chamador que não possua o escopo curinga `*` só pode emitir chaves cujos escopos sejam estritamente um subconjunto dos seus próprios escopos (`ctx.scopes`), bloqueando escalação horizontal/vertical.

### 2. Enforçamento de Escopos (`enforce_scope`) e Isolamento Multi-OLT (`enforce_olt`)
- **[`app/api/v1/endpoints_olts.py`](file:///Volumes/240/Code/oltapi/app/api/v1/endpoints_olts.py)**:
  - `test_connection` e `get_olt_config`: `ctx.enforce_scope("olts:read")` + `ctx.enforce_olt(olt_id)`.
  - `list_backups`, `download_backup`, `audit_olt_backups`, `compare_olt_backups`: `ctx.enforce_scope("backups:read")` + `ctx.enforce_olt(olt_id)`.
  - `trigger_backup`, `purge_olt_backups`: `ctx.enforce_scope("backups:create")` + `ctx.enforce_olt(olt_id)`.
  - `sync_olt`, `enrich_olt_vlans`: `ctx.enforce_scope("olts:admin")` + `ctx.enforce_olt(olt_id)`.
- **[`app/api/v1/endpoints_backups.py`](file:///Volumes/240/Code/oltapi/app/api/v1/endpoints_backups.py)**:
  - `run_all_backups` e `purge_all_backups`: `ctx.enforce_scope("backups:create")`.
  - `audit_all_backups`: `ctx.enforce_scope("backups:read")`.
- **[`app/api/v1/endpoints_bootstrap.py`](file:///Volumes/240/Code/oltapi/app/api/v1/endpoints_bootstrap.py)**:
  - `preview_bootstrap` e `apply_bootstrap`: `ctx.enforce_scope("olts:admin")` + `ctx.enforce_olt(olt_id)`.
- **[`app/api/v1/endpoints_vlans.py`](file:///Volumes/240/Code/oltapi/app/api/v1/endpoints_vlans.py)**:
  - Consultas (`list_olt_vlans`, `get_vlan_metrics`, `get_vlan_history`, `list_olt_profiles`, `get_provisioning_schema`): `ctx.enforce_scope("olts:read")` + `ctx.enforce_olt(olt_id)`.
  - Criação (`create_olt_vlan`): `ctx.enforce_scope("olts:admin")` + `ctx.enforce_olt(olt_id)`.
- **[`app/api/v1/endpoints_pon_policies.py`](file:///Volumes/240/Code/oltapi/app/api/v1/endpoints_pon_policies.py)**:
  - Consultas (`GET`): `ctx.enforce_scope("olts:read")` + `ctx.enforce_olt(olt_id)`.
  - Escrita e Tasks de Cutover (`PUT`, `DELETE`, `POST`): `ctx.enforce_scope("onus:provision")` + `ctx.enforce_olt(olt_id)`.
- **[`app/api/v1/endpoints_ftp.py`](file:///Volumes/240/Code/oltapi/app/api/v1/endpoints_ftp.py)**:
  - Consultas (`GET`): `ctx.enforce_scope("backups:read")` (e `ctx.enforce_olt(olt_id)` em rotas por OLT).
  - Mutação e Teste (`POST`, `PUT`, `DELETE`): `ctx.enforce_scope("olts:admin")`.
- **[`app/api/v1/endpoints_scanner.py`](file:///Volumes/240/Code/oltapi/app/api/v1/endpoints_scanner.py)**:
  - `get_scanner_status`: `ctx.enforce_scope("onus:discover")`.
  - Controle do daemon (`start`, `stop`, `run-now`, `interval`): `ctx.enforce_scope("olts:admin")`.
- **[`app/api/v1/endpoints_onu_inventory.py`](file:///Volumes/240/Code/oltapi/app/api/v1/endpoints_onu_inventory.py)**:
  - Histórico (`list_global_history`, `get_onu_history`): `ctx.enforce_scope("onus:read")` + verificação de `enforce_olt`.
  - Escrita/Reconciliação (`register_onu`, `reconcile_field_event`, `update_onu`): `ctx.enforce_scope("onus:provision")` + `enforce_olt`/`enforce_vlan`.

### 3. Proteção SSRF e Criptografia Fernet em Webhooks
- **[`app/core/security.py`](file:///Volumes/240/Code/oltapi/app/core/security.py)** e **[`app/models/webhook.py`](file:///Volumes/240/Code/oltapi/app/models/webhook.py)**:
  - Adicionado validador `sanitize_webhook_url` bloqueando esquemas não-HTTP/HTTPS (`file://`, `ftp://`, `gopher://`), endereços de loopback (`localhost`, `127.0.0.0/8`, `::1`), redes link-local/cloud metadata (`169.254.0.0/16`) e IPs não-roteáveis (`0.0.0.0`).
- **[`app/storage/sql/webhook_repository.py`](file:///Volumes/240/Code/oltapi/app/storage/sql/webhook_repository.py)** e **[`app/db/init_db.py`](file:///Volumes/240/Code/oltapi/app/db/init_db.py)**:
  - O segredo HMAC (`secret`) agora é cifrado em repouso com Fernet (`encrypt_password`) antes de persistir no SQLite/PostgreSQL e decifrado transparentemente (`decrypt_password`) na leitura, além de incluído na rotina de migração automática de segredos na inicialização.

### 4. Correção de `logger` em `decrypt_password` e Time-Safe Compare no Setup
- **[`app/core/security.py`](file:///Volumes/240/Code/oltapi/app/core/security.py)**: Inicializado `logger = logging.getLogger(__name__)`, eliminando o `NameError` caso um token Fernet corrompido ou assinado com chave antiga seja lido do banco.
- **[`app/api/v1/endpoints_setup.py`](file:///Volumes/240/Code/oltapi/app/api/v1/endpoints_setup.py)**: Substituída comparação direta de string por `hmac.compare_digest(api_key, settings.API_KEY)`.

### 5. Higiene de Repositório e Isolamento de Porta no Docker
- Removidos do controle de versão 6 arquivos residuais de merge (`.orig` e `.rej`) e adicionadas as regras `*.orig` e `*.rej` ao [`.gitignore`](file:///Volumes/240/Code/oltapi/.gitignore) e [`.dockerignore`](file:///Volumes/240/Code/oltapi/.dockerignore).
- No [`docker-compose.yml`](file:///Volumes/240/Code/oltapi/docker-compose.yml), o bind da porta do PostgreSQL foi restrito a `127.0.0.1:${POSTGRES_PORT:-5432}:5432`.
