# Plano de Implementação: Blindagem de Segurança (Test-First)

## Objetivo
Corrigir as vulnerabilidades de segurança identificadas na auditoria do **OLTAPI** seguindo uma abordagem estritamente **Test-First (TDD)**: primeiro escreveremos a suíte de testes de regressão e segurança comprovando os vetores e garantindo que os 247 testes existentes continuam intactos; em seguida, aplicaremos as correções cirúrgicas até que 100% da suíte passe.

---

## Etapa 1: Criação da Suíte de Testes de Segurança (`tests/unit/test_security_audit_fixes.py`)
Antes de alterar qualquer linha de código da aplicação, criaremos o arquivo `tests/unit/test_security_audit_fixes.py` cobrindo:

1. **Bloqueio de Elevação de Privilégio em Chaves de API (`/api/v1/api-keys`)**:
   - Usuário sem escopo `api_keys:manage` (ex: `FIELD_TECH` ou `NOC`) deve receber `403 Forbidden` ao tentar criar ou revogar chaves de API.
   - Usuário com `api_keys:manage` (ex: `TENANT_ADMIN`) **não pode** emitir uma chave contendo escopos que ele próprio não possui (ex: `*`).
2. **Isolamento RBAC e Multi-Tenant em Endpoints de OLT, Backups, Bootstrap, VLANs, FTP e Scanner**:
   - Técnico restrito à `OLT-A` (`allowed_olt_ids={"OLT-A"}`) deve receber `403 Forbidden` ao tentar acessar `GET /olts/{OLT-B}/config`, `GET /olts/{OLT-B}/backups`, `POST /olts/{OLT-B}/backups`, `GET /olts/{OLT-B}/vlans` ou `GET /olts/{OLT-B}/pon-policies`.
   - Usuário sem escopo administrativo (`olts:admin` / `backups:create`) deve receber `403 Forbidden` em rotas destrutivas ou de escrita (`POST /olts/{id}/bootstrap/apply`, `POST /olts/{id}/vlans`, `POST /backups/purge-all`, `POST /ftp-servers`, `DELETE /ftp-servers/{id}`, `POST /scanner/start`, `POST /scanner/stop`).
3. **Prevenção de SSRF (Server-Side Request Forgery) e Criptografia em Webhooks**:
   - Tentativa de cadastrar webhook apontando para loopback (`http://127.0.0.1:...`, `http://localhost:...`), link-local/cloud metadata (`http://169.254.169.254/...`) ou esquemas não-HTTP(S) (`file://`, `ftp://`) deve ser bloqueada com `400/422`.
   - O segredo HMAC (`secret`) do webhook deve ser cifrado em repouso no banco de dados (`gAAAAA...` via Fernet) e decifrado transparentemente no momento do disparo.
4. **Resiliência do Fallback de Decifragem (`app/core/security.py`)**:
   - Quando `decrypt_password` recebe um token Fernet corrompido ou assinado com chave desconhecida, deve registrar aviso no logger sem levantar `NameError` e retornar o valor de forma segura.
5. **Proteção contra Timing Attack no Setup Inicial (`/api/v1/setup/init`)**:
   - Validação constante via `hmac.compare_digest`.

---

## Etapa 2: Implementação das Correções no Código

### 1. Correção do `logger` e Comparação Time-Safe
- **`app/core/security.py`**: Importar `logging` e instanciar `logger = logging.getLogger(__name__)` para evitar `NameError` no bloco `except` de `decrypt_password`.
- **`app/api/v1/endpoints_setup.py`**: Substituir `api_key != settings.API_KEY` por `not hmac.compare_digest(api_key, settings.API_KEY)`.

### 2. Blindagem contra Elevação de Privilégio em API Keys
- **`app/api/v1/endpoints_api_keys.py`**:
  - Exigir `ctx.enforce_scope("api_keys:manage")` em `list_api_keys`, `create_dynamic_api_key` e `revoke_api_key`.
  - Validar que, se `"*"` não estiver em `ctx.scopes`, todos os escopos requisitados em `req.scopes` devem ser um subconjunto de `ctx.scopes` (impedindo que qualquer chave ou usuário crie uma chave mais poderosa que si mesmo).

### 3. Enforçamento de RBAC (`enforce_scope` e `enforce_olt`) nas Rotas
- **`app/api/v1/endpoints_olts.py`**:
  - `test_connection`: exigir `ctx.enforce_scope("olts:read")` e `ctx.enforce_olt(olt_id)`.
  - `get_olt_config`: exigir `ctx.enforce_scope("olts:read")` e `ctx.enforce_olt(olt_id)`.
  - `list_backups`, `download_backup`, `audit_olt_backups`, `compare_olt_backups`: exigir `ctx.enforce_scope("backups:read")` e `ctx.enforce_olt(olt_id)`.
  - `trigger_backup`, `purge_olt_backups`: exigir `ctx.enforce_scope("backups:create")` e `ctx.enforce_olt(olt_id)`.
  - `sync_olt`, `enrich_olt_vlans`: exigir `ctx.enforce_scope("olts:admin")` e `ctx.enforce_olt(olt_id)`.
- **`app/api/v1/endpoints_backups.py`**:
  - `run_all_backups`, `purge_all_backups`: exigir `ctx.enforce_scope("backups:create")`.
  - `audit_all_backups`: exigir `ctx.enforce_scope("backups:read")`.
- **`app/api/v1/endpoints_bootstrap.py`**:
  - `preview_bootstrap`, `apply_bootstrap`: exigir `ctx.enforce_scope("olts:admin")` e `ctx.enforce_olt(olt_id)`.
- **`app/api/v1/endpoints_vlans.py`**:
  - `list_olt_vlans`, `get_vlan_metrics`, `get_vlan_history`, `list_olt_profiles`, `get_provisioning_schema`: exigir `ctx.enforce_scope("olts:read")` e `ctx.enforce_olt(olt_id)`.
  - `create_olt_vlan`: exigir `ctx.enforce_scope("olts:admin")` e `ctx.enforce_olt(olt_id)`.
- **`app/api/v1/endpoints_ftp.py`**:
  - Consultas (`GET`): exigir `ctx.enforce_scope("backups:read")` (e `ctx.enforce_olt(olt_id)` em `/olts/{olt_id}/ftp-servers`).
  - Escrita/Teste (`POST`, `PUT`, `DELETE`): exigir `ctx.enforce_scope("olts:admin")`.
- **`app/api/v1/endpoints_pon_policies.py`**:
  - Consultas (`GET`): exigir `ctx.enforce_scope("olts:read")` e `ctx.enforce_olt(olt_id)`.
  - Escrita/Tasks (`PUT`, `DELETE`, `POST`): exigir `ctx.enforce_scope("onus:provision")` e `ctx.enforce_olt(olt_id)`.
- **`app/api/v1/endpoints_scanner.py`**:
  - `get_scanner_status`: exigir `ctx.enforce_scope("onus:discover")`.
  - `start_scanner`, `stop_scanner`, `run_scanner_now`, `update_scanner_interval`: exigir `ctx.enforce_scope("olts:admin")`.
- **`app/api/v1/endpoints_onu_inventory.py`**:
  - `list_global_history`, `get_onu_history`: exigir `ctx.enforce_scope("onus:read")`.
  - `register_onu`, `reconcile_field_event`, `update_onu`: exigir `ctx.enforce_scope("onus:provision")` (ou `onus:actions`) e `ctx.enforce_olt(...)` quando OLT for informada.

### 4. Proteção contra SSRF e Cifragem de Segredo em Webhooks
- **`app/models/webhook.py`** e **`app/core/security.py`**:
  - Validar que a URL do webhook utiliza esquema `http` ou `https` e não aponta para loopback (`localhost`, `127.0.0.0/8`, `::1`) ou link-local/metadata (`169.254.0.0/16`).
- **`app/storage/sql/webhook_repository.py`** e **`app/db/init_db.py`**:
  - Cifrar o campo `secret` com `encrypt_password` ao salvar no banco e decifrar com `decrypt_password` ao carregar.

### 5. Higiene de Repositório e Docker
- Remover do controle de versão os arquivos residuais `.orig` e `.rej` e adicionar `*.orig` e `*.rej` ao `.gitignore` e `.dockerignore`.
- Restringir o bind da porta do PostgreSQL no `docker-compose.yml` para `127.0.0.1:${POSTGRES_PORT:-5432}:5432`.

---

## Etapa 3: Verificação e Sincronização de Contratos
1. Executar `pytest` completo garantindo que todos os **247 testes atuais + os 6 novos testes de segurança** passem com 0 falhas.
2. Executar `python -m scripts.export_openapi` para atualizar `docs/api_contracts/openapi.yaml` e `docs/api_contracts/openapi.json` conforme diretriz mandatória do projeto.
