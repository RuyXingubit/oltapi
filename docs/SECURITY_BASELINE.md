# Baseline de Segurança & Hardening: OLTAPI

## 1. Princípio Fundamental: Segurança em Primeiro Lugar
Seguindo a diretriz mandatória do projeto e do [System Design & Specification Document (`docs/SDD.md`)](SDD.md), toda funcionalidade implementada é avaliada quanto ao seu impacto na segurança da aplicação e da infraestrutura óptica do provedor. Acesso não autorizado a uma OLT pode comprometer a operação de telecomunicações de cidades inteiras.

---

## 2. Controles de Segurança Ativos

### 2.1. Prevenção contra Injeção de Comandos CLI (CLI Command Injection)
Como os drivers montam comandos para execução em terminais de gerência (SSH/Telnet/TL1), todos os parâmetros fornecidos por ERPs ou operadores são sanitizados em [`app/core/security.py`](file:///Volumes/240/Code/oltapi/app/core/security.py) antes de chegarem ao driver:
- **Porta PON (`sanitize_port`):** Aceita exclusivamente formatos canônicos seguros de porta (`0/1`, `1/1/1`, `gpon 0/1`, `gpon1/1`), rejeitando ponto-e-vírgula, pipes e subshells.
- **Serial da ONU (`sanitize_serial`):** Validação alfanumérica estrita (`^[A-Za-z0-9\-]{4,24}$`). Rejeita espaços, `;`, `|`, `&`, redirecionamentos (`>`, `<`), backticks e caracteres de controle.
- **VLAN (`sanitize_vlan`):** Validação numérica estrita no intervalo IEEE 802.1Q (`1 <= vlan <= 4094`).
- **Strings Gerais e Descrições (`sanitize_safe_string` / `sanitize_description`):** Rejeita metacaracteres de terminal (`;`, `|`, `&`, `` ` ``, `$`, `>`, `<`, `\r`, `\n`, aspas) prevenindo quebra de contexto CLI.

### 2.2. Autenticação Dual, RBAC Multi-Tenant e Prevenção de Elevação de Privilégio
O controle de acesso em [`app/api/deps.py`](file:///Volumes/240/Code/oltapi/app/api/deps.py) opera sob arquitetura **Zero Trust Multi-Tenant** (suportando tanto provedores proprietários `PROVIDER_OWNER` quanto locatários de Rede Neutra `WHOLESALE_TENANT`):
- **Autenticação por Chave Master ou API Key de Tenant (`X-API-Key`):**
  - A chave master de infraestrutura é validada em tempo constante via `hmac.compare_digest` (inclusive no bootstrap inicial `/api/v1/setup/init`), prevenindo *timing attacks*.
  - Chaves de API emitidas para ERPs/integrações nunca são salvas em texto plano: apenas o **hash SHA-256 (`key_hash`)** e o prefixo identificador são armazenados na tabela `api_keys`.
- **Autenticação por Token JWT (`Authorization: Bearer <token>`):**
  - Assinado com `HMAC-SHA256` (`JWT_SECRET`), validando expiração (`exp`) e status ativo do usuário e do tenant.
- **Enforçamento Granular de Escopos e Isolamento de Recursos (`AuthContext`):**
  - `ctx.enforce_scope(scope)`: Exigido em todas as rotas de leitura, provisionamento, backup, configuração, VLANs, políticas PON, servidores FTP, scanner e administração (`olts:read`, `olts:admin`, `onus:discover`, `onus:provision`, `onus:operate`, `onus:delete`, `backups:read`, `backups:create`, `api_keys:manage`, `users:manage`, `tenants:manage`, `webhooks:manage`).
  - `ctx.enforce_olt(olt_id)` e `ctx.enforce_vlan(vlan_id)`: Impede que um tenant locatário acesse concentradores OLT ou provisione clientes em VLANs fora de sua lista de permissão (`allowed_olt_ids` / `allowed_vlans`).
  - **Bloqueio de Elevação de Privilégio em API Keys:** Na rota `POST /api/v1/api-keys`, além de exigir o escopo `api_keys:manage`, o sistema valida que todos os escopos solicitados para a nova chave são estritamente um subconjunto dos escopos que o próprio criador possui.

### 2.3. Criptografia de Credenciais em Repouso (Fernet AES)
Nenhum segredo operacional de terceiros permanece em texto aberto no banco de dados relacional:
- **Credenciais Cifradas:**
  - Senhas de acesso SSH/Telnet das OLTs (`olts.password`)
  - Comunidades SNMP (`olts.snmp_ro_community`)
  - Senhas de servidores FTP remotos (`ftp_servers.password`)
  - Segredos de assinatura HMAC de Webhooks (`webhooks.secret`)
- **Mecanismo:** Cifragem simétrica autenticada **Fernet (AES-128-CBC + HMAC-SHA256)** via `encrypt_password` e `decrypt_password` em [`app/core/security.py`](file:///Volumes/240/Code/oltapi/app/core/security.py), com rotina automática de migração de segredos na inicialização (`init_db.py`).
- **Omissão em Respostas HTTP:** Os schemas de saída (`OLTResponse`, `FTPServerResponse`, `WebhookSubscriptionResponse`) jamais expõem senhas de equipamentos em consultas `GET`.

### 2.4. Prevenção contra SSRF em Webhooks (`sanitize_webhook_url`)
Para impedir que o motor de entrega de Webhooks seja explorado como vetor de *Server-Side Request Forgery (SSRF)* contra a rede interna do servidor:
- Todas as URLs cadastradas em `POST /api/v1/webhooks` passam por `sanitize_webhook_url`:
  - Permite exclusivamente esquemas `http://` e `https://` (bloqueando `file://`, `ftp://`, `gopher://`, etc.).
  - Bloqueia destinos de loopback (`localhost`, `127.0.0.0/8`, `::1`), endereços não-roteáveis (`0.0.0.0`) e redes link-local / Cloud Metadata (`169.254.0.0/16`).

### 2.5. Prevenção de Path Traversal e Isolamento de Rede em Containers
- **Confinamento de Arquivos de Backup:** O download de backups (`/backups/{backup_id}/download`) valida que `backup_id` é um UUID estrito e verifica com `Path.resolve()` que o arquivo reside estritamente dentro do diretório autorizado da OLT.
- **Blindagem de Porta do Banco de Dados:** Tanto em [`docker-compose.yml`](file:///Volumes/240/Code/oltapi/docker-compose.yml) quanto em [`docker-compose.prod.yml`](file:///Volumes/240/Code/oltapi/docker-compose.prod.yml), o serviço PostgreSQL 16 faz bind estrito em loopback (`127.0.0.1:${POSTGRES_PORT:-5432}:5432`), impedindo exposição externa direta da porta 5432 na internet.
- **Execução Non-Root:** O container da API executa sob usuário sem privilégios de superusuário (`UID 1000`).
