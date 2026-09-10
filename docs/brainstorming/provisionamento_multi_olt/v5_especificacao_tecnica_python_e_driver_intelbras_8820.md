# Brainstorming: API Unificada de Provisionamento Multi-OLT
**Versão:** v5 (Especificação Técnica da Stack Python e Arquitetura do Driver Intelbras 8820)  
**Data:** 2026-09-10  
**Autor:** Antigravity & Usuário  

---

## 1. Definições Selecionadas

1. **Stack:** **Python** (FastAPI + Pydantic v2 + Netmiko/Paramiko + Pytest).
2. **Piloto 1:** **Intelbras 8820** (GPON).
3. **Padrão de Identificadores:** **UUIDv7** (conforme diretriz global de segurança e ordenação temporal de registros).

---

## 2. Estrutura Proposta para o Projeto Python

```
oltapi/
├── app/
│   ├── api/
│   │   ├── v1/
│   │   │   ├── router.py
│   │   │   ├── endpoints_olts.py       # GET /olts, GET /olts/{id}/config, POST /olts/{id}/backups
│   │   │   ├── endpoints_diagnostics.py# GET /olts/{id}/ports/{port}/onus, GET /olts/{id}/onus/{serial}
│   │   │   └── endpoints_provision.py  # GET /olts/{id}/unauthorized, POST /olts/{id}/onus
│   │   └── deps.py                     # Autenticação (API Key) e injeção de dependência
│   ├── core/
│   │   ├── config.py                   # Variáveis de ambiente (PORT, BACKUP_DIR, API_KEY)
│   │   ├── security.py                 # Validação de API Key e sanitização de comandos
│   │   └── uuid.py                     # Gerador nativo de UUIDv7
│   ├── drivers/
│   │   ├── base.py                     # Interface abstrata (BaseOLTDriver)
│   │   ├── factory.py                  # DriverFactory (instancia driver por fabricante/modelo)
│   │   └── intelbras/
│   │       ├── __init__.py
│   │       └── intelbras_8820.py       # Driver especializado para Intelbras 8820
│   ├── models/
│   │   ├── olt.py                      # Modelos Pydantic (OLTInDB, OLTConfigResponse)
│   │   ├── backup.py                   # Modelos de Backup (BackupMetadata, UUIDv7)
│   │   ├── onu.py                      # Modelos de ONU (ONUSummary, OpticalSignal, UnauthorizedONU)
│   │   └── provision.py                # Modelos de Provisionamento (ProvisionRequest, ProvisionResult)
│   ├── storage/
│   │   ├── olt_repository.py           # Repositório de OLTs cadastradas (em memória/JSON/SQLite)
│   │   └── backup_storage.py           # Gestão de arquivos de backup em disco seguro
│   └── main.py                         # Ponto de entrada da aplicação FastAPI
├── backups/                            # Diretório local seguro para armazenar arquivos brutos de backup
├── tests/
│   ├── unit/
│   │   ├── test_uuid.py
│   │   ├── test_security_sanitization.py
│   │   ├── test_intelbras_8820_parser.py
│   │   └── test_api_endpoints.py
│   └── conftest.py
├── docs/
│   └── brainstorming/
├── requirements.txt
└── README.md
```

---

## 3. Detalhamento do Driver da Intelbras 8820

A Intelbras 8820 opera via terminal CLI (SSH/Telnet). O driver implementará as seguintes sequências de comandos:

### 3.1 Visualização de Configuração (Running-Config)
- **Comando CLI:** `show running-config` (ou `show current-configuration`).
- **Mecanismo:** Desabilita paginação no terminal de sessão (ex: `terminal length 0` ou envio de barra de espaço se necessário) e captura o output completo.

### 3.2 Rotina de Backup via API
- **Mecanismo:**
  1. O driver conecta à OLT via SSH/Telnet.
  2. Executa a leitura do running-config.
  3. Salva em disco em pasta segura: `backups/{olt_id}/{backup_id}.cfg` (onde `backup_id` é gerado via **UUIDv7**).
  4. Retorna metadados para a API (ID, timestamp, hash SHA-256 de integridade e tamanho do arquivo).
  5. O endpoint de download entrega o stream do arquivo com `Content-Disposition: attachment`.

### 3.3 Consulta de ONUs Não Autorizadas (Autofind / Unconfigured)
- **Comando CLI:** `show gpon onu uncfg` (ou `show gpon uncfg-onu`).
- **Parser Regex:** Extrai:
  - Porta PON (ex: `1/1` ou `0/1/1`)
  - Serial Number / MAC (ex: `INCL12345678`)
  - Modelo do equipamento (se reportado pelo OMCI)

### 3.4 Diagnóstico de ONU e Sinal Óptico
- **Comando CLI:** 
  - Status e alocação: `show gpon onu state gpon-olt_{port}` ou `show gpon onu detail-info`
  - Níveis de potência óptica: `show gpon onu optical-info gpon-onu_{port}:{onu_id}`
- **Parser Regex:** Converte as saídas de texto em formato estruturado:
  - `rx_power_dbm`: Potência recebida na OLT (ex: `-19.45`)
  - `tx_power_dbm`: Potência transmitida pela ONU
  - `status`: `online`, `offline`, `dying-gasp` ou `los` (loss of signal).

### 3.5 Provisionamento da ONU
- **Comando CLI:**
  ```text
  config
  interface gpon-olt_{port}
  onu {onu_id} type {model} sn {serial}
  exit
  interface gpon-onu_{port}:{onu_id}
  name {description}
  vlan {vlan_id}
  exit
  write memory
  ```
- **Retorno:** Status de sucesso, porta, ONU-ID e serial atribuído.

---

## 4. Segurança e Higienização de Comandos (CLI Command Injection)
Como o técnico ou ERP fornecerá strings como `description`, `serial` ou `port`, o módulo de segurança `app/core/security.py` aplicará validação rigorosa com regex defensivo:
- **Port:** apenas caracteres numéricos e barras (ex: `^[0-9]+(/[0-9]+)+$`).
- **Serial:** alfanumérico estrito (ex: `^[A-Za-z0-9]{8,16}$`).
- **Description:** apenas caracteres alfanuméricos, hífen e underscore (rejeitando aspas, ponto-e-vírgula, pipes ou caracteres de controle de shell).

---

## 5. Próximos Passos
1. Validar se o plano técnico atende plenamente.
2. Criar a estrutura inicial do projeto com testes unitários cobrindo o UUIDv7, modelos Pydantic e parsers do driver da Intelbras 8820.
