# Dockerização para Produção & Docker Compose (v1)

## 1. Contexto e Objetivos

Para viabilizar a implantação em provedores de internet (ISPs), datacenters e servidores locais sem atrito de dependências ou vulnerabilidades de execução privilegiada, a OLTAPI necessita de uma imagem de containerização de nível corporativo (*production-ready*).

### Objetivos:
1. **Multi-Stage Build (Python 3.13-slim):** Separação estrita entre o estágio de compilação de dependências C (`build-essential`, `libffi-dev`) e a imagem final enxuta, reduzindo a superfície de ataque e o tamanho da imagem.
2. **Usuário Não-Root (Non-Root User):** Execução do processo sob `appuser` (UID 1000 / GID 1000), prevenindo escape de container e acesso indevido ao kernel do host.
3. **Persistência de Dados e Backups (Volumes):** Mapeamento claro e seguro de volumes para `/app/data` (índice de OLTs e metadados) e `/app/backups` (arquivos brutos `.cfg`).
4. **Healthcheck Nativo Integrado:** Checagem periódica do endpoint `/health` utilizando exclusivamente a biblioteca padrão do Python (`urllib.request`), dispensando a instalação de pacotes extras como `curl` ou `wget`.
5. **Políticas de Log e Recursos no Docker Compose:** Definição de limites de memória/CPU e controle de rotação de logs (`json-file` com `max-size: 10m` e `max-file: 3`) para impedir esgotamento de disco.
6. **Variáveis de Ambiente Documentadas (`.env.example`):** Modelo de configuração para administradores de rede e DevOps.

---

## 2. Arquitetura de Implantação

```
   ┌────────────────────────────────────────────────────────┐
   │                   Host Linux / Docker                  │
   │                                                        │
   │   ┌──────────────────────────────────────────────┐     │
   │   │             Container: oltapi                │     │
   │   │  (Python 3.13-slim / Non-Root: UID 1000)     │     │
   │   │                                              │     │
   │   │   [ Uvicorn (FastAPI) ] : Port 8000          │     │
   │   │              │                               │     │
   │   │              ├──────► /app/data              │     │
   │   │              └──────► /app/backups           │     │
   │   └──────────────────────┬───────────────┬───────┘     │
   │                          │               │             │
   │                          ▼               ▼             │
   │                  ┌──────────────┐ ┌──────────────┐     │
   │                  │ ./data (host)│ │./backups(host│     │
   │                  └──────────────┘ └──────────────┘     │
   └────────────────────────────────────────────────────────┘
```

---

## 3. Especificação do Dockerfile

- **Estágio 1 (`builder`):**
  - Imagem base: `python:3.13-slim`.
  - Instalação de ferramentas de compilação essenciais.
  - Instalação das dependências do `requirements.txt` no prefixo `/install`.
- **Estágio 2 (`runner`):**
  - Imagem base: `python:3.13-slim`.
  - Cópia limpa de `/install` para `/usr/local`.
  - Criação do grupo `appgroup` (GID 1000) e usuário `appuser` (UID 1000).
  - Configuração de permissões nas pastas `/app/data` e `/app/backups`.
  - `USER appuser`.
  - `HEALTHCHECK` via `python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"`.
  - Ponto de entrada: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers`.
