# Planejamento da Migração para Testcontainers com PostgreSQL Real

## 1. Contexto e Objetivo
Garantir paridade de 100% entre o ambiente de testes/desenvolvimento e o ambiente de produção empresarial, eliminando completamente fixtures em JSON ou diferenças de dialeto de banco de dados.

Com o Docker Desktop ativo localmente, a suite de testes automatizados do Pytest passará a:
1. Subir sob demanda um container real oficial `postgres:16-alpine` via biblioteca `testcontainers[postgres]`.
2. Executar as migrações canônicas de DDL do **Alembic** (`alembic upgrade head`) contra o PostgreSQL real.
3. Configurar os repositórios `SQLOLTRepository`, `SQLONUInventoryRepository`, `SQLWebhookRepository` e `SQLBackupStorage` para operarem sobre o PostgreSQL efêmero.
4. Aplicar estratégia de isolamento por teste (limpeza rápida de tabelas via TRUNCATE / DELETE CASCADE ou transações aninhadas com rollback) para garantir idempotência.
5. Derrubar e destruir o container automaticamente ao término dos testes.

---

## 2. Arquitetura da Fixture do Testcontainers (`tests/conftest.py`)

### 2.1 Ciclo de Vida da Sessão (`scope="session"`)
- Inicia o container PostgreSQL:
  ```python
  with PostgresContainer("postgres:16-alpine") as postgres:
      db_url = postgres.get_connection_url()
  ```
- Aplica o schema mais recente via Alembic:
  ```python
  alembic_cfg = Config("alembic.ini")
  alembic_cfg.set_main_option("sqlalchemy.url", db_url)
  command.upgrade(alembic_cfg, "head")
  ```
- Cria o `engine` e o `sessionmaker(bind=engine)` para o banco PostgreSQL de teste.

### 2.2 Isolamento entre Testes (`autouse=True, scope="function"`)
Para evitar que os 134 testes se contaminem mutualmente (ex: cadastrar uma OLT com mesmo nome ou ONU com mesmo serial):
- Antes ou depois de cada teste, executa a limpeza das tabelas relacionais em ordem reversa de dependência (ou `TRUNCATE TABLE olts, onus_inventory, onus_history, webhook_subscriptions, webhook_deliveries, backups_metadata CASCADE;`).
- Garante estado 100% limpo e previsível a cada método de teste.

---

## 3. Substituição das Fixtures Legadas no `tests/conftest.py`

Atualmente, `conftest.py` faz:
```python
test_olt_repo = OLTRepository(data_file=test_data_dir / "olts.json")
test_backup_storage = BackupStorage(base_dir=test_backup_dir, data_file=test_data_dir / "backups.json")
test_onu_repo = ONUInventoryRepository(...)
test_webhook_repo = WebhookRepository(...)
```

Com a migração, passará a fazer:
```python
test_olt_repo = SQLOLTRepository(session_factory=test_session_factory)
test_backup_storage = SQLBackupStorage(session_factory=test_session_factory, base_dir=test_backup_dir)
test_onu_repo = SQLONUInventoryRepository(session_factory=test_session_factory)
test_webhook_repo = SQLWebhookRepository(session_factory=test_session_factory)
```
Todos os serviços (`ONUReconciliationService`, `AutofindScannerService`, `BackupService`) e as injeções de dependência do FastAPI (`app.dependency_overrides`) receberão as instâncias SQL conectadas ao PostgreSQL do Testcontainers.

---

## 4. Dependências Necessárias
- `testcontainers[postgres]>=4.0.0`
- `psycopg2-binary>=2.9.9`

---

## 5. Próximos Passos de Execução (Pós-Aprovação)
1. Instalar dependências no ambiente virtual (`.venv`) e atualizar `requirements.txt`.
2. Refatorar `tests/conftest.py` com a fixture `session` do `PostgresContainer` e `function` para limpeza de dados.
3. Atualizar `tests/unit/test_sql_repositories.py` para utilizar o container PostgreSQL de sessão.
4. Executar os 134 testes do Pytest e certificar 100% de aprovação no PostgreSQL real.
5. Documentar a estratégia no Manual e no Relatório de QA.
