# 🐳 Guia de Instalação & Setup em Produção

Este guia orienta o comissionamento e a inicialização do **OLTAPI** em ambiente de produção utilizando a **imagem oficial do Docker Hub** ([`xingubit/oltapi`](https://hub.docker.com/r/xingubit/oltapi)), com **PostgreSQL 16**, migrações automatizadas via **Alembic**, criptografia AES-256 e proxy reverso seguro.

---

## 🎯 Arquitetura da Stack de Produção

Em ambiente de produção, a imagem oficial é 100% autossuficiente: não há necessidade de compilar código, instalar Python no host ou clonar repositórios inteiros.

```mermaid
graph TD
    subgraph Internet_Rede_Local["Rede Externa / Provedor"]
        ERP["ERP (IXC, MK-Auth, Voalle)"]
        NOC["Frontend NOC (Flutter)"]
        ADMIN["Administrador / NOC"]
    end

    subgraph Host_Servidor["Servidor de Produção / VPS"]
        REVERSE["Proxy Reverso (Nginx / Caddy)<br>Porta 80 / 443 (SSL/TLS)"]
        
        subgraph Docker_Network["Docker Bridge Network (oltapi-net)"]
            API["Container OLTAPI (xingubit/oltapi)<br>FastAPI + Uvicorn (Porta 8000)<br>Usuário não-root (UID 1000)"]
            DB["Container PostgreSQL 16 Alpine<br>(oltapi_postgres:5432)"]
            WT["Container Watchtower<br>(containrrr/watchtower)<br>Auto-Update às 03:30 da madrugada"]
        end
        
        VOL_DATA["Volume: ./data"]
        VOL_BACKUP["Volume: ./backups"]
        VOL_PG["Volume: postgres_data"]
    end

    subgraph Rede_PON["Rede de Telecom / Concentradores"]
        OLT_VSOL["OLT V-SOL (SSH / Telnet)"]
        OLT_FH["OLT Fiberhome (Telnet / TL1)"]
    end

    ERP -->|HTTPS / API-Key| REVERSE
    NOC -->|HTTPS / API-Key| REVERSE
    ADMIN -->|HTTPS / API-Key| REVERSE
    REVERSE -->|HTTP 8000| API
    API -->|SQLAlchemy / Alembic| DB
    API --> VOL_DATA
    API --> VOL_BACKUP
    DB --> VOL_PG
    API -->|Porta 22 / 23 / 3337| OLT_VSOL
    API -->|Porta 23 / 3337| OLT_FH
```

---

## 📋 Pré-requisitos do Servidor

* **Sistema Operacional:** Linux (Ubuntu 22.04 / 24.04 LTS, Debian 12 ou Rocky Linux 9).
* **Docker Engine:** versão `24.0.0` ou superior.
* **Docker Compose:** versão `v2.20.0` ou superior (plugin nativo `docker compose`).
* **Conectividade IP:** rota de rede/VLAN acessível entre o servidor e os IPs de gerência das OLTs (portas 22, 23 ou 3337).

---

## 🚀 Método 1: Implantação Rápida em Produção (Docker Compose)

Esta é a abordagem oficial e recomendada para servidores dedicados, instâncias em nuvem (AWS EC2, Lightsail, DigitalOcean) ou VMs locais.

### 1. Criar Diretório da Aplicação

No servidor de produção, crie a estrutura de pastas dedicada:

```bash
sudo mkdir -p /opt/oltapi/data /opt/oltapi/backups
cd /opt/oltapi
```

---

### 2. Criar o Arquivo `docker-compose.yml`

Crie o arquivo `/opt/oltapi/docker-compose.yml` utilizando a imagem oficial publicada no Docker Hub:

```yaml
services:
  postgres:
    image: postgres:16-alpine
    container_name: oltapi_postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-oltapi}
      POSTGRES_USER: ${POSTGRES_USER:-oltuser}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    ports:
      - "127.0.0.1:${POSTGRES_PORT:-5432}:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-oltuser} -d ${POSTGRES_DB:-oltapi}"]
      interval: 5s
      timeout: 5s
      retries: 5
      start_period: 5s
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  oltapi:
    image: xingubit/oltapi:latest
    container_name: oltapi
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
    ports:
      - "${PORT:-8000}:8000"
    env_file:
      - path: .env
        required: true
    volumes:
      - ./data:/app/data
      - ./backups:/app/backups
    logging:
      driver: "json-file"
      options:
        max-size: "20m"
        max-file: "5"
    healthcheck:
      test: ["CMD-SHELL", "python3 -c \"import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()\" || exit 1"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s

  watchtower:
    image: containrrr/watchtower
    container_name: oltapi_watchtower
    restart: unless-stopped
    environment:
      # Executa diariamente às 03:30 da madrugada (formato cron de 6 campos: s m h d m d)
      - WATCHTOWER_SCHEDULE=0 30 3 * * *
      - WATCHTOWER_CLEANUP=true
      - WATCHTOWER_ROLLING_RESTART=true
      - TZ=${TZ:-America/Sao_Paulo}
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    command: oltapi

volumes:
  postgres_data:
```

> [!TIP]
> **Watchtower Embutido:** O serviço `watchtower` monitora o registro Docker Hub e aplica automaticamente novas versões do container `oltapi` todas as noites às **03:30 da madrugada**, limpando imagens antigas (`WATCHTOWER_CLEANUP=true`) para poupar disco.
> Se preferir fixar uma versão e desativar o auto-update, basta comentar o serviço `watchtower` e fixar uma tag de versão (ex: `image: xingubit/oltapi:v1.0.0`).

---

### 3. Configurar as Variáveis de Ambiente (`.env`)

Crie o arquivo `/opt/oltapi/.env` com as configurações do seu ambiente:

```bash
nano /opt/oltapi/.env
```

Preencha com o seguinte modelo de produção:

```ini
# ==============================================================================
# OLTAPI - CONFIGURAÇÕES DE PRODUÇÃO
# ==============================================================================

# Nome e Ambiente
PROJECT_NAME="OLT Provisioning & Diagnostics API"
ENVIRONMENT="production"
PORT=8000
LOG_LEVEL="INFO"

# ------------------------------------------------------------------------------
# SEGURANÇA E AUTENTICAÇÃO (OBRIGATÓRIO PREENCHER)
# ------------------------------------------------------------------------------
# Chave de API para clientes HTTP e ERPs (cabeçalho X-API-Key)
API_KEY="coloque_aqui_uma_chave_longa_e_aleatoria"

# Segredo criptográfico para geração de tokens JWT
JWT_SECRET="coloque_aqui_um_hash_aleatorio_muito_seguro_minimo_32_caracteres"

# Chave Mestra Fernet AES-256 para criptografia de senhas de OLTs no PostgreSQL
# Instruções para gerar a chave estão logo abaixo
DB_ENCRYPTION_KEY="sua_chave_fernet_aes256_base64_gerada"

# Controle de Origens CORS (Defina as URLs do seu ERP ou Frontend NOC)
# Para permitir todas: * | Ou especifique: https://noc.meuprovedor.com.br
CORS_ORIGINS="*"

# ------------------------------------------------------------------------------
# BANCO DE DADOS POSTGRESQL 16
# ------------------------------------------------------------------------------
POSTGRES_USER="oltuser"
POSTGRES_PASSWORD="defina_uma_senha_forte_para_o_banco"
POSTGRES_DB="oltapi"
POSTGRES_HOST="postgres"
POSTGRES_PORT=5432

# Se utilizar banco gerenciado em nuvem (ex: AWS RDS, Supabase, Neon),
# comente as linhas POSTGRES_* acima e descomente DATABASE_URL:
# DATABASE_URL="postgresql+psycopg2://usuario:senha@meu-rds.amazonaws.com:5432/oltapi"

# ------------------------------------------------------------------------------
# POLÍTICAS DE TIMEOUT E DISASTER RECOVERY
# ------------------------------------------------------------------------------
# Timeout em segundos para comandos de rede com as OLTs (SSH / Telnet)
DEFAULT_SSH_TIMEOUT=15

# Política de Retenção de Backups
BACKUP_RETENTION_MAX=30
BACKUP_RETENTION_DAYS=60

# ------------------------------------------------------------------------------
# SUPERVISÃO AUTÔNOMA (AUTOFIND SCANNER)
# ------------------------------------------------------------------------------
# Iniciar a varredura automática em background na inicialização do container (true/false)
SCANNER_ENABLED_ON_STARTUP=false
SCANNER_INTERVAL_SECONDS=60
```

#### 🔑 Como Gerar Chaves Fortes Rapidamente

Execute os seguintes comandos no terminal do servidor para gerar chaves criptograficamente seguras:

1. **Gerar `API_KEY` e `JWT_SECRET`:**
   ```bash
   openssl rand -hex 32
   ```

2. **Gerar `DB_ENCRYPTION_KEY` (Chave Fernet AES-256):**
   ```bash
   # Via Docker (sem precisar de Python local):
   docker run --rm python:3.13-slim python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

> [!CAUTION]
> **Bloqueio de Inicialização Ativo:** Se a variável `ENVIRONMENT` estiver configurada como `production` e as variáveis `API_KEY` ou `JWT_SECRET` contiverem os valores de exemplo padrão, o OLTAPI **recusará a inicialização** por diretriz de segurança, interrompendo o container com erro explicativo no log.

---

### 4. Ajustar Permissões de Pastas

Como o container roda internamente sob o usuário não-privilegiado `appuser` (UID `1000`), garanta as permissões nos diretórios montados:

```bash
sudo chown -R 1000:1000 /opt/oltapi/data /opt/oltapi/backups
sudo chmod 600 /opt/oltapi/.env
```

---

### 5. Iniciar os Serviços

Execute o Docker Compose para baixar as imagens e iniciar os containers em segundo plano:

```bash
docker compose up -d
```

O processo de inicialização executa automaticamente:
1. Inicialização do banco relacional **PostgreSQL 16**.
2. O healthcheck do Postgres confirma prontidão do serviço (`pg_isready`).
3. O OLTAPI inicia e executa automaticamente as **migrações do Alembic** (`alembic upgrade head`), criando ou atualizando todas as tabelas.
4. Criptografa credenciais em repouso caso haja chave configurada.
5. Inicia o servidor HTTP de alta performance **Uvicorn** na porta `8000`.

---

### 6. Validar a Instalação

Verifique se os containers estão saudáveis:

```bash
docker compose ps
```

**Saída esperada:**
```text
NAME              IMAGE                    COMMAND                  SERVICE    CREATED          STATUS                    PORTS
oltapi            xingubit/oltapi:latest   "uvicorn app.main:ap…"   oltapi     10 seconds ago   Up 10 seconds (healthy)   0.0.0.0:8000->8000/tcp
oltapi_postgres   postgres:16-alpine       "docker-entrypoint.s…"   postgres   11 seconds ago   Up 11 seconds (healthy)   127.0.0.1:5432->5432/tcp
```

Consulte o endpoint de healthcheck:

```bash
curl -s http://localhost:8000/health | jq
```

**Resposta:**
```json
{
  "status": "healthy",
  "service": "OLT Provisioning & Diagnostics API",
  "version": "1.0.0"
}
```

---

## 🔒 Configuração de Proxy Reverso com HTTPS (Nginx & Caddy)

Em produção, nunca exponha a porta HTTP `8000` diretamente para a internet. Utilize um proxy reverso para terminação SSL/TLS com certificado Let's Encrypt.

=== "Nginx"

    Crie a configuração do site em `/etc/nginx/sites-available/oltapi`:

    ```nginx
    server {
        listen 80;
        server_name oltapi.meuprovedor.com.br;
        return 301 https://$host$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name oltapi.meuprovedor.com.br;

        ssl_certificate /etc/letsencrypt/live/oltapi.meuprovedor.com.br/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/oltapi.meuprovedor.com.br/privkey.pem;

        # Otimizações de segurança SSL
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;
        ssl_prefer_server_ciphers on;

        # Limite de tamanho de upload para backups de firmware/configurações
        client_max_body_size 50M;

        location / {
            proxy_pass http://127.0.0.1:8000;
            proxy_http_version 1.1;

            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # Suporte a WebSockets e Server-Sent Events (SSE)
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";

            # Timeouts para rotas de backup demoradas
            proxy_connect_timeout 60s;
            proxy_send_timeout 180s;
            proxy_read_timeout 180s;
        }
    }
    ```

    Ative o site e recarregue o Nginx:
    ```bash
    sudo ln -s /etc/nginx/sites-available/oltapi /etc/nginx/sites-enabled/
    sudo nginx -t && sudo systemctl reload nginx
    ```

=== "Caddy (SSL Automático)"

    Se preferir o **Caddy**, a configuração é extremamente enxuta e o certificado HTTPS Let's Encrypt é emitido e renovado de forma 100% automática:

    ```caddy
    oltapi.meuprovedor.com.br {
        reverse_proxy 127.0.0.1:8000 {
            header_up Host {host}
            header_up X-Real-IP {remote_host}
            header_up X-Forwarded-Proto {scheme}
        }
    }
    ```

---

## 🔄 Rotina de Atualização da Imagem

### 🕒 1. Atualizações Automáticas com Watchtower (Recomendado)

O arquivo `docker-compose.yml` de produção já vem configurado com o **Watchtower**, que atua de forma autônoma:

* **Janela Noturna Segura:** O agendamento é disparado diariamente às **03:30 da madrugada** (`WATCHTOWER_SCHEDULE: "0 30 3 * * *"`), horário de menor atividade operacional em provedores.
* **Fuso Horário Local:** A variável `TZ=America/Sao_Paulo` garante a execução precisa no horário de Brasília (ou no fuso configurado no servidor).
* **Escopo Cirúrgico:** O parâmetro `command: oltapi` restringe as atualizações exclusivamente ao container da aplicação, deixando o banco de dados PostgreSQL intacto.
* **Limpeza de Disco Automática:** O parâmetro `WATCHTOWER_CLEANUP=true` remove as camadas das imagens antigas do Docker após a atualização, prevenindo o esgotamento do armazenamento em servidores e VPS.
* **Migrações Automáticas pós-Deploy:** Na subida do novo container às 03:30, o OLTAPI executa o `alembic upgrade head`, atualizando o schema do banco antes de liberar as requisições na porta 8000.

---

### ⚡ 2. Atualização Manual Sob Demanda (Zero-Downtime)

Se você preferir antecipar uma atualização ou não utilizar o Watchtower, execute os comandos manuais:

```bash
cd /opt/oltapi

# 1. Baixar a imagem mais recente
docker compose pull oltapi

# 2. Recriar o container sem interromper o banco de dados
docker compose up -d oltapi
```

> [!NOTE]
> As migrações do banco relacional são aplicadas automaticamente pelo novo container no momento da subida. Seus dados persistem intactos no volume `postgres_data` e na pasta `/opt/oltapi/data`.

---

## 💾 Rotina de Backup de Segurança

Para criar um backup preventivo da sua base de dados e configurações de OLTs:

```bash
# 1. Backup do Banco de Dados PostgreSQL
docker compose exec -T postgres pg_dump -U oltuser oltapi | gzip > /opt/oltapi/backup_db_$(date +%Y%m%d).sql.gz

# 2. Backup dos arquivos de running-config e chaves de criptografia
tar -czvf /opt/oltapi/backup_files_$(date +%Y%m%d).tar.gz /opt/oltapi/backups /opt/oltapi/.env
```

---

## 🛠️ Método 2: Ambiente Local de Desenvolvimento (Build a Partir do Código)

Para desenvolvedores que desejam compilar localmente ou customizar drivers de OLT:

```bash
# 1. Clonar o repositório
git clone https://github.com/RuyXingubit/oltapi.git
cd oltapi

# 2. Configurar o ambiente
cp .env.example .env

# 3. Subir e compilar a stack local
docker compose up -d --build

# 4. Acompanhar os logs
docker compose logs -f oltapi
```

### Execução via Python Virtualenv (Sem Docker)

```bash
# 1. Criar e ativar o ambiente virtual
python3 -m venv .venv
source .venv/bin/activate

# 2. Instalar dependências
pip install --upgrade pip
pip install -r requirements.txt

# 3. Iniciar o servidor FastAPI com hot-reload
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 📑 Acesso às Interfaces

Com a stack operacional, os seguintes recursos ficam disponíveis:

| Interface | URL | Finalidade |
| :--- | :--- | :--- |
| **Status / Healthcheck** | `http://localhost:8000/health` | Verificação de integridade para monitoramento (Zabbix, Grafana, Uptime Kuma). |
| **API REST Root** | `http://localhost:8000` | Resposta com status do serviço e links de navegação HATEOAS. |
| **Documentação Interativa Swagger UI** | `http://localhost:8000/api/v1/docs` | Teste manual e documentação interativa de todos os endpoints. |
| **Documentação ReDoc** | `http://localhost:8000/api/v1/redoc` | Especificação técnica limpa do contrato OpenAPI 3.1.0. |
| **Central de Operações NOC (Flutter)** | Pasta `frontend/` | Interface desktop ou web para gerenciamento visual da rede GPON. |
