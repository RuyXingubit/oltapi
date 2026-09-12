# Comparativo e Arquitetura: Versionamento de Banco de Dados no Python (Flyway vs Alembic) (v2)

## 1. O Paralelo: Do Flyway (Java/Spring Boot) para o Mundo Python

No ecossistema Java com Spring Boot, o **Flyway** é a ferramenta padrão:
- Ele lê arquivos SQL versionados (`V1__initial_schema.sql`, `V2__add_customer_index.sql`).
- Mantém a tabela `flyway_schema_history` no banco para saber quais scripts já foram executados e seu checksum SHA-256.
- Roda automaticamente na inicialização da aplicação (`spring.flyway.enabled=true`).

No ecossistema Python moderno com **SQLAlchemy**, o equivalente direto e padrão absoluto da indústria é o **Alembic** (criado pelo mesmo autor do SQLAlchemy, Mike Bayer).

---

## 2. Tabela Comparativa: Flyway vs Alembic

| Aspecto | Flyway (Java/Spring Boot) | Alembic (Python/SQLAlchemy) |
|---|---|---|
| **Tabela de Controle** | `flyway_schema_history` (guarda versão, script, checksum, data) | `alembic_version` (guarda o hash da revisão atual) |
| **Formato das Migrações** | Arquivos `.sql` puros (`V1__create_tables.sql`) | Arquivos Python (`0001_create_tables.py`) que executam comandos DDL ou SQL puro |
| **Geração de Migrações** | 100% manual (você escreve todo o DDL SQL) | **Autogerada ou Manual** (`alembic revision --autogenerate` compara os models com o banco e gera o script) |
| **Rollback (Downgrade)** | Apenas na versão paga (Teams/Enterprise via `U__undo.sql`) | **Nativo e Gratuito** (todo script possui função `upgrade()` e `downgrade()`) |
| **Dialeto Multi-Banco** | Scripts específicos por dialeto (Postgres vs Oracle vs SQLite) | Agnóstico via SQLAlchemy DDL (`op.create_table`, `op.add_column`) ou SQL puro (`op.execute()`) |
| **Execução no Startup** | Automática pelo Spring Boot | Automática via script no `lifespan` do FastAPI ou no entrypoint Docker |

---

## 3. Como o Alembic Funciona na Prática

### A) Estrutura no Projeto
```text
oltapi/
├── alembic.ini                   # Arquivo de configuração de conexão e caminhos
├── alembic/
│   ├── env.py                    # Script que carrega os models SQLAlchemy e a DATABASE_URL
│   ├── script.py.mako            # Template para novas migrações
│   └── versions/                 # Onde ficam as migrações versionadas
│       ├── 0001_initial_schema.py
│       └── 0002_add_tr101_index.py
```

### B) Anatomia de um Arquivo de Migração (`versions/0001_initial_schema.py`)
```python
"""initial_schema

Revision ID: 0001
Revises: 
Create Date: 2026-09-12 10:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0001'
down_revision = None

def upgrade() -> None:
    # Cria a tabela olts
    op.create_table(
        'olts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(64), nullable=False, unique=True),
        sa.Column('vendor', sa.String(32), nullable=False),
        sa.Column('model', sa.String(32), nullable=False),
        sa.Column('host', sa.String(128), nullable=False),
        sa.Column('port', sa.Integer(), nullable=False),
        sa.Column('protocol', sa.String(16), nullable=False),
        sa.Column('username', sa.String(64), nullable=False),
        sa.Column('password', sa.String(256), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_olts_name', 'olts', ['name'])

def downgrade() -> None:
    op.drop_index('ix_olts_name', table_name='olts')
    op.drop_table('olts')
```

*(Nota: Se preferir escrever em SQL puro exatamente como no Flyway, o Alembic também permite executar `op.execute("CREATE TABLE ...")` dentro de `upgrade()`)*.

---

## 4. Como se dá a Execução Automática (Estilo Flyway)

Para que o desenvolvedor ou o operador em produção não precise rodar comandos manuais no terminal toda vez que atualizar a versão do container:

### Opção 1: No Startup da Aplicação FastAPI (Idêntico ao Spring Boot)
No `lifespan` de `app/main.py`:
```python
from alembic import command
from alembic.config import Config

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Roda as migrações automaticamente antes de aceitar conexões (como o Flyway)
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    
    yield
```

### Opção 2: No Entrypoint do Docker (`docker-entrypoint.sh`)
```bash
#!/bin/sh
set -e

echo "Executando migrações do banco de dados (Alembic)..."
alembic upgrade head

echo "Iniciando Uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## 5. Outra Alternativa no Python: Yoyo-Migrations

Existe uma biblioteca chamada **yoyo-migrations**:
- Ela é ainda mais parecida sintaticamente com o Flyway clássico, pois usa arquivos `.sql` puros com anotações de rollback (`-- step 1: apply`, `-- step 1: rollback`).
- **Porém:** Não possui integração nativa com os tipos e modelos do SQLAlchemy, perde o recurso de auto-geração e é menos utilizada no mercado do que o Alembic.

---

## 6. Recomendação

Adotar o **Alembic**:
1. É a ferramenta oficial do ecossistema SQLAlchemy (padrão ouro em Python).
2. Permite migração automática no startup via `command.upgrade(cfg, "head")` (comportamento 100% equivalente ao `spring.flyway.enabled=true`).
3. Suporta tanto DDL tipado do SQLAlchemy quanto SQL puro.
4. Funciona de forma idêntica e transparente tanto no **SQLite local** quanto no **PostgreSQL de produção**.
