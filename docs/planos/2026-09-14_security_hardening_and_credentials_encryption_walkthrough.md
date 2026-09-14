# Walkthrough: Hardening de Segurança, Criptografia AES-256 e Rate Limiting

## Resumo da Execução
Implementamos e validamos com 100% de sucesso o pacote completo de segurança e hardening do OLTAPI, protegendo credenciais em repouso, prevenindo ataques de força bruta, resguardando as controladoras de OLTs contra saturação e adicionando cabeçalhos de defesa OWASP.

---

## 1. Criptografia Reversível em Repouso (AES-256 Fernet)
- **Implementação**:
  - Módulo [app/core/security.py](file:///Volumes/240/Code/oltapi/app/core/security.py): funções `get_fernet()`, `encrypt_password()` e `decrypt_password()`.
  - Repositórios [app/storage/sql/olt_repository.py](file:///Volumes/240/Code/oltapi/app/storage/sql/olt_repository.py) e [app/storage/sql/ftp_repository.py](file:///Volumes/240/Code/oltapi/app/storage/sql/ftp_repository.py): senhas são automaticamente cifradas ao salvar (`create`/`update`) e decifradas em memória ao carregar para conectar via Telnet/SSH/FTP.
  - Migração Automática em [app/db/init_db.py](file:///Volumes/240/Code/oltapi/app/db/init_db.py): a função `encrypt_existing_plain_passwords()` detecta senhas legadas em texto puro e as cifra no banco PostgreSQL.
- **Validação no Banco PostgreSQL**:
  - A coluna `olts.password` da OLT VTX foi migrada de `nocProserv12#` para o ciphertext `gAAAAABqp5Q7twjQrIiXdDX4ZzCl3QnT_xrVHcJWrsVDS3Fd2iyXRcfOcqH1whvZ-6RLe11PdZ7eZ5xB_F_DGNWmgtaaerR5iA==`.

---

## 2. Revelação Segura de Credenciais para Administradores
- **Endpoint**: `POST /api/v1/olts/{id}/reveal-credentials`
  - Restrito a perfis com escopo `olts:admin` (`SUPER_ADMIN` ou `TENANT_ADMIN` para sua respectiva OLT).
  - Emite log de auditoria com nível `WARNING`:
    `[SECURITY AUDIT] Usuário 'admin@provedor.com.br' (Role: SUPER_ADMIN) revelou as credenciais da OLT 'VTX' a partir do IP 192.168.1.50.`
  - Rate limit de 5 requisições por minuto.
- **Interface Web**:
  - Botão "🔑 Senha" visível para administradores na tabela de OLTs.
  - Modal com detalhes da OLT, botão de copiar senha e temporizador regressivo de 30 segundos que fecha o modal e limpa a senha automaticamente.

---

## 3. Rate Limiting (`slowapi`)
- Integrado em [app/main.py](file:///Volumes/240/Code/oltapi/app/main.py) com handler para HTTP 429 Too Many Requests.
- Rotas protegidas:
  - `POST /api/v1/auth/login`: 5 req/min por IP (prevenção contra força bruta).
  - `POST /api/v1/olts/{id}/sync`: 10 req/min (proteção de hardware).
  - `POST /api/v1/olts/{id}/enrich-vlans`: 5 req/min.
  - `POST /api/v1/olts/{id}/telemetry`: 10 req/min.
  - `POST /api/v1/olts/{id}/test-connection`: 15 req/min.
  - `POST /api/v1/olts/{id}/reveal-credentials`: 5 req/min.

---

## 4. Defesas OWASP e Hardening HTTP
- Middleware em [app/main.py](file:///Volumes/240/Code/oltapi/app/main.py) injetando:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: SAMEORIGIN`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `X-XSS-Protection: 1; mode=block`
  - `Permissions-Policy: geolocation=(), microphone=(), camera=()`
- Restrição de CORS via configuração `CORS_ORIGINS`.
- Validação no startup (`lifespan`) impedindo que o sistema suba em produção com segredos default.

---

## 5. Testes e Contratos OpenAPI
- **Testes Unitários**: 220/220 testes passando com 100% de sucesso (`pytest tests/unit/`).
- **Contrato OpenAPI**: Sincronizado em `docs/api_contracts/` com 66 endpoints e 80 esquemas.
