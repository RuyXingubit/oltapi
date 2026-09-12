# Persistência de Dados Relacional & Migrações ACID (v1)

## 1. Contexto & Motivação

Atualmente, o **OLTAPI** utiliza repositórios em arquivos JSON atômicos (`data/olts.json`, `data/onus_inventory.json`, `data/onus_history.json`, `data/webhooks.json`, `data/webhook_deliveries.json`). Essa estratégia foi fundamental para garantir rapidez na prototipagem, portabilidade e zero dependência externa de infraestrutura.

No entanto, à medida que a plataforma cresce para gerenciar centenas de OLTs, dezenas de milhares de ONUs e múltiplos workers assíncronos no Uvicorn/Gunicorn em provedores de médio e grande porte, a persistência relacional com suporte a **transações ACID** torna-se necessária para:
1. **Concorrência Segura Multi-Worker:** Evitar conflitos de I/O em disco quando múltiplos workers FastAPI gravam simultaneamente no inventário.
2. **Consultas Indexadas de Alta Performance:** Busca imediata por serial, status de contrato, Circuit ID, OLT e range de datas na linha do tempo do NOC.
3. **Dualidade SQLite / PostgreSQL:**
   - **SQLite com WAL (Write-Ahead Logging):** Padrão local out-of-the-box (zero instalação externa, ideal para laboratório, pequenas operações e testes).
   - **PostgreSQL:** Produção corporativa de alta disponibilidade com pool de conexões.
4. **Preservação das Interfaces de Repositório (Repository Pattern):**
   - Os serviços (`ONUReconciliationService`, `AutofindScannerService`, `BackupService`, `WebhookDispatcher`) e os endpoints continuam consumindo as mesmas assinaturas de repositório, garantindo zero quebra de contratos existentes.

---

## 2. Tecnologias & Arquitetura

- **SQLAlchemy 2.0 / SQLModel:** Tipagem forte integrada com Pydantic v2.
- **Identificadores UUIDv7 (RFC 9562):** Chaves primárias universais e sequenciais no tempo.
- **Alembic:** Gerenciamento de versionamento de esquema e migrações incrementais (`alembic upgrade head`).
- **Configuração Flexível:** `DATABASE_URL` via variáveis de ambiente:
  - Default: `sqlite:///./data/oltapi.db` (com suporte a foreign keys e modo WAL).
  - Produção: `postgresql+psycopg://user:pass@host:5432/oltapi`.

---

## 3. Esquema de Tabelas Mapeado

1. **`olts`:**
   - `id` (VARCHAR(36), PK, UUIDv7)
   - `name` (VARCHAR(64), UNIQUE)
   - `vendor` (VARCHAR(32))
   - `model` (VARCHAR(32))
   - `host` (VARCHAR(128))
   - `port` (INTEGER)
   - `protocol` (VARCHAR(16))
   - `username` (VARCHAR(64))
   - `password` (VARCHAR(256))
   - `created_at` (TIMESTAMP)

2. **`onus_inventory`:**
   - `id` (VARCHAR(36), PK, UUIDv7)
   - `serial` (VARCHAR(32), UNIQUE, INDEX)
   - `contract_id` (VARCHAR(64), INDEX)
   - `subscriber_name` (VARCHAR(128))
   - `contract_status` (VARCHAR(32), INDEX) -- ACTIVE, SUSPENDED, IN_STOCK, CANCELLED
   - `current_olt_id` (VARCHAR(36), FK -> olts.id)
   - `current_port` (VARCHAR(32))
   - `current_onu_id` (INTEGER)
   - `circuit_id` (VARCHAR(128), INDEX)
   - `vlan` (INTEGER)
   - `profile` (VARCHAR(64))
   - `latitude` (FLOAT)
   - `longitude` (FLOAT)
   - `notes` (TEXT)
   - `created_at` (TIMESTAMP)
   - `updated_at` (TIMESTAMP)

3. **`onus_history`:**
   - `id` (VARCHAR(36), PK, UUIDv7)
   - `serial` (VARCHAR(32), INDEX)
   - `contract_id` (VARCHAR(64))
   - `subscriber_name` (VARCHAR(128))
   - `reason` (VARCHAR(128))
   - `from_olt_id` (VARCHAR(36))
   - `from_olt_name` (VARCHAR(64))
   - `from_port` (VARCHAR(32))
   - `from_onu_id` (INTEGER)
   - `from_circuit_id` (VARCHAR(128))
   - `to_olt_id` (VARCHAR(36))
   - `to_olt_name` (VARCHAR(64))
   - `to_port` (VARCHAR(32))
   - `to_onu_id` (INTEGER)
   - `to_circuit_id` (VARCHAR(128))
   - `status` (VARCHAR(32))
   - `details` (TEXT)
   - `timestamp` (TIMESTAMP, INDEX)

4. **`webhook_subscriptions`:**
   - `id` (VARCHAR(36), PK, UUIDv7)
   - `url` (VARCHAR(256))
   - `secret` (VARCHAR(128))
   - `events` (JSON / TEXT)
   - `is_active` (BOOLEAN)
   - `description` (VARCHAR(256))
   - `created_at` (TIMESTAMP)

5. **`webhook_deliveries`:**
   - `id` (VARCHAR(36), PK, UUIDv7)
   - `subscription_id` (VARCHAR(36), FK -> webhook_subscriptions.id)
   - `event` (VARCHAR(64))
   - `url` (VARCHAR(256))
   - `status_code` (INTEGER)
   - `success` (BOOLEAN)
   - `duration_ms` (FLOAT)
   - `error_message` (TEXT)
   - `timestamp` (TIMESTAMP, INDEX)

6. **`backups_metadata`:**
   - `backup_id` (VARCHAR(36), PK, UUIDv7)
   - `olt_id` (VARCHAR(36), FK -> olts.id)
   - `olt_name` (VARCHAR(64))
   - `filename` (VARCHAR(128))
   - `size_bytes` (INTEGER)
   - `sha256` (VARCHAR(64))
   - `created_at` (TIMESTAMP, INDEX)
   - `notes` (TEXT)
