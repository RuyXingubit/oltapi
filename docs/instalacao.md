# 🐳 Guia de Instalação & Configuração

Este guia orienta a inicialização do **OLTAPI** em ambiente local ou servidor de produção, utilizando **Docker Compose** com **PostgreSQL 16** oficial e migrações automatizadas via **Alembic**.

---

## 📋 Pré-requisitos

* **Docker:** versão 24.0+ e **Docker Compose:** versão 2.20+
* **Git:** para clonar o repositório
* *(Opcional)* **Python 3.11+** caso deseje executar fora do Docker.

---

## 🚀 Instalação via Docker Compose (Recomendada)

### 1. Clonar o Repositório

```bash
git clone https://github.com/RuyXingubit/oltapi.git
cd oltapi
```

---

### 2. Configurar Variáveis de Ambiente (`.env`)

Copie o arquivo de exemplo para criar o seu `.env`:

```bash
cp .env.example .env
```

Edite o arquivo `.env` ajustando as variáveis principais:

```ini
PROJECT_NAME="OLT Provisioning & Diagnostics API"
API_KEY="sua_chave_secreta_aqui"

# Chave Mestra Fernet AES-256 para Criptografia de Credenciais em Repouso no PostgreSQL
# Gere uma nova chave executando: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
DB_ENCRYPTION_KEY="sua_chave_fernet_aes256_base64_aqui"

# Credenciais do Banco Relacional PostgreSQL 16
POSTGRES_USER="oltuser"
POSTGRES_PASSWORD="sua_senha_do_banco_aqui"
POSTGRES_DB="oltapi"
POSTGRES_HOST="postgres"
POSTGRES_PORT=5432

PORT=8000
LOG_LEVEL="INFO"
```

> [!WARNING]
> Nunca comite o arquivo `.env` preenchido no Git! Ele já está protegido no `.gitignore`.

---

### 3. Iniciar a Stack de Produção

Execute o comando de inicialização com build dos containers:

```bash
docker compose up -d --build
```

A stack inicializará automaticamente:
1. **`oltapi_postgres`:** PostgreSQL 16 Alpine com volume persistente `postgres_data` e healthcheck nativo.
2. **`oltapi`:** FastAPI aguarda o banco estar saudável, aplica as migrações canônicas do Alembic (`alembic upgrade head`) e inicia o servidor HTTP na porta `8000`.

Para verificar o status dos serviços:
```bash
docker compose ps
```

---

### 4. Validar Conectividade & Healthcheck

Confirme se o serviço está saudável consultando o endpoint público:

```bash
curl http://localhost:8000/health
```

**Resposta esperada (`200 OK`):**
```json
{
  "status": "healthy",
  "service": "OLT Provisioning & Diagnostics API",
  "version": "1.0.0"
}
```

---

### 5. Interfaces Disponíveis

Com a aplicação rodando, acesse no navegador:

* 🖥️ **Interface Web de Bancada:** [http://localhost:8000](http://localhost:8000) (Dashboard operacional com dark glassmorphism e assistente de Onboarding Zero-Touch).
* 📑 **Documentação Interativa Swagger UI:** [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs)
* 📖 **Documentação Interativa ReDoc:** [http://localhost:8000/api/v1/redoc](http://localhost:8000/api/v1/redoc)

---

## 🐍 Instalação Alternativa (Python Virtualenv)

Para desenvolvedores que desejam executar diretamente no host:

```bash
# 1. Crie e ative o ambiente virtual
python3 -m venv .venv
source .venv/bin/activate

# 2. Instale as dependências
pip install -r requirements.txt

# 3. Inicie o servidor FastAPI com hot-reload
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
