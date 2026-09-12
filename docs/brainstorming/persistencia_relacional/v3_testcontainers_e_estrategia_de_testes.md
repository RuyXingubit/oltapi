# Estratégia de Testes: Testcontainers em Python vs SQLite vs GitHub Actions Services

Este documento registra a análise técnica sobre o uso do **Testcontainers** no ecossistema Python para o **OLTAPI**, comparando fidelidade com produção, velocidade de execução, dependências locais (Docker) e comportamento no GitHub Actions.

---

## 1. O que é o Testcontainers no Python (`testcontainers-python`)?

No mundo Java/Spring Boot, o Testcontainers é o padrão de excelência para testes de integração fidedignos. No ecossistema Python, existe a biblioteca oficial correspondente:
- **Pacote:** `testcontainers[postgres]`
- **Como funciona:**
  1. A fixture do Pytest instancia `PostgresContainer("postgres:16-alpine")`.
  2. O container é iniciado via Docker SDK (`/var/run/docker.sock`).
  3. A biblioteca obtém dinamicamente a porta mapeada e monta a URL de conexão:
     `postgresql+psycopg2://test:test@localhost:{random_port}/test`
  4. Executa as migrações do **Alembic** (`alembic upgrade head`) na base Postgres real.
  5. O Pytest executa os testes contra o PostgreSQL 100% real de produção.
  6. Ao final da suite (`fixture scope="session"`), o container é encerrado e destruído automaticamente.

---

## 2. Diagnóstico do Ambiente Atual (Local vs GitHub Actions)

Realizamos a verificação do daemon Docker localmente nesta máquina:
- **Comando:** `docker info`
- **Resultado:**
  ```text
  Cannot connect to the Docker daemon at unix:///Users/ruy/.docker/run/docker.sock. Is the docker daemon running?
  ```
- **Fato Importante:** O Docker Desktop não está em execução no momento na máquina local do desenvolvedor.

---

## 3. Matriz Comparativa: Estratégias de Testes

| Critério | SQLite WAL (Em Disco/Memória Temporária) | Testcontainers (`testcontainers-python`) | GitHub Actions Service Container (`services: postgres`) |
| :--- | :--- | :--- | :--- |
| **Fidelidade com Produção** | Média-Alta (SQLAlchemy abstrai a maioria das queries, mas dialetos diferem em constraints específicas e lock de tabelas) | **100% Idêntico** (Roda PostgreSQL real 16 com todos os tipos, constraints e índices) | **100% Idêntico** (Roda PostgreSQL real 16) |
| **Velocidade de Execução** | Ultrarrápida (~100ms a 3s para toda a suite) | Razoável (~5 a 10s para pull e boot do container + testes) | Razoável (~10 a 20s para inicialização do container) |
| **Dependência do Docker Local** | **Nenhuma** (roda em qualquer SO sem Docker ativo) | **Obrigatória** (falha se o Docker Desktop não estiver aberto) | **Nenhuma local** (o runner do GitHub Actions já tem Docker nativo) |
| **Execução no GitHub Actions** | Simples (`pytest tests/ -v`) | Simples (Docker nativo do runner Ubuntu) | Simples e declarativa no YAML do workflow |
| **Consumo de Memória / CPU** | Mínimo | Moderado (consome RAM do daemon Docker) | Isolado no runner do CI |

---

## 4. Arquitetura Recomendada: O Melhor dos Dois Mundos (Híbrida & Resiliente)

Para garantir que o ambiente local do desenvolvedor seja leve e rápido (mesmo sem abrir o Docker) e que o pipeline de integração e o CI tenham **100% de paridade com o PostgreSQL de produção**, recomendamos uma estratégia de **Testes em Duas Camadas**:

### Camada 1: Testes Unitários Rápidos (Fast Unit Tests)
- **Onde:** `tests/unit/`
- **Engine:** SQLite com WAL mode.
- **Objetivo:** Feedback instantâneo no dia a dia, TDD, validação de regras de negócio, parsers de fabricantes, regex e lógicas de reconcliação sem precisar abrir o Docker Desktop.

### Camada 2: Testes de Integração com Postgres Real (Integration Tests)
- **Onde:** `tests/integration/` (ou fixture inteligente com detecção de Docker / flag `--postgres`).
- **Engine:** `testcontainers[postgres]` com imagem oficial `postgres:16-alpine`.
- **Comportamento inteligente:**
  - Se o Docker estiver rodando ou estiver no GitHub Actions: sobe o container PostgreSQL, aplica migrações Alembic e roda a validação fidedigna.
  - Se o desenvolvedor estiver sem o Docker aberto: os testes unitários continuam passando normalmente, sem travar o commit por falta do daemon do Docker.
