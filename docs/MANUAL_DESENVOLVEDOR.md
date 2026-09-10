# Manual do Desenvolvedor: Arquitetura & Criação de Drivers (OLTAPI)

Bem-vindo ao **Manual do Desenvolvedor do OLTAPI**! Este guia foi elaborado para qualquer pessoa da comunidade open-source que queira entender a arquitetura do projeto, contribuir com novas funcionalidades ou adicionar suporte a novos fabricantes e modelos de OLT (como Huawei, Fiberhome, ZTE, Datacom, Parks, Nokia, etc.).

---

## 🧭 Sumário

1. [Visão Geral da Arquitetura](#1-visão-geral-da-arquitetura)
2. [Estrutura de Diretórios](#2-estrutura-de-diretórios)
3. [O Padrão de Drivers (Driver / Adapter Pattern)](#3-o-padrão-de-drivers-driver--adapter-pattern)
4. [Passo a Passo: Como Adicionar um Novo Driver de OLT](#4-passo-a-passo-como-adicionar-um-novo-driver-de-olt)
5. [Boas Práticas de Parsing com Expressões Regulares Puras](#5-boas-práticas-de-parsing-com-expressões-regulares-puras)
6. [Segurança e Sanitização Defensiva](#6-segurança-e-sanitização-defensiva)
7. [Padrão de Identificadores: UUIDv7](#7-padrão-de-identificadores-uuidv7)
8. [Como Escrever Testes Unitários Sem Necessidade de Hardware Físico](#8-como-escrever-testes-unitários-sem-necessidade-de-hardware-físico)
9. [Executando o Ambiente Local](#9-executando-o-ambiente-local)

---

## 1. Visão Geral da Arquitetura

O **OLTAPI** foi projetado com os seguintes princípios:

- **API-First & Agnóstica de Fabricante:** O cliente da API (seja um ERP como IXC Soft, MK-Auth ou um script cURL) nunca precisa saber a sintaxe de terminal (CLI) específica de cada marca. O ERP envia e recebe apenas payloads JSON padronizados.
- **Isolamento de Complexidade de Terminal:** Toda a interação telnet/ssh, envio de comandos, paginação de terminal (`--More--` ou `terminal length 0`) e expressões regulares de parse residem estritamente dentro da camada de **Drivers**.
- **Segurança em Primeiro Lugar:** Nenhuma entrada do usuário é passada sem sanitização para o terminal da OLT, prevenindo injeção de comandos CLI.

```
[ ERP / Postman / cURL ]
           │
           │  JSON + X-API-Key
           ▼
[ FastAPI Application (app/main.py) ]
           │
           │  Validação Pydantic v2 + Sanitização Regex
           ▼
[ API Routers (app/api/v1/*.py) ]
           │
           │  DriverFactory.get_driver(vendor, model)
           ▼
[ Driver Abstraction (BaseOLTDriver) ]
           ├──> Intelbras8820Driver (Broadcom CLI)
           ├──> IntelbrasGSeriesDriver (G08 / G16 CLI)
           ├──> HuaweiMA5800Driver (VRP CLI) ────> [Roadmap]
           └──> FiberhomeAN5516Driver (TL1/CLI) ─> [Roadmap]
```

---

## 2. Estrutura de Diretórios

```
oltapi/
├── app/
│   ├── api/
│   │   └── v1/                  # Endpoints REST organizados por domínio
│   │       ├── olts.py          # Cadastro, consulta e running-config de OLTs
│   │       ├── diagnostics.py   # Consulta de portas, ONUs e diagnóstico óptico
│   │       ├── provisioning.py  # Provisionamento de ONUs e autofind
│   │       └── bootstrap.py     # Assistente de configuração inicial zero-touch
│   ├── core/
│   │   ├── config.py            # Configurações com Pydantic Settings
│   │   ├── security.py          # Sanitizadores regex e validação de API Key
│   │   └── uuid.py              # Gerador e validador nativo de UUIDv7 (RFC 9562)
│   ├── drivers/
│   │   ├── base.py              # Interface abstrata BaseOLTDriver
│   │   ├── factory.py           # DriverFactory com cache e resolução dinâmica
│   │   └── intelbras/
│   │       ├── intelbras_8820.py    # Driver 8820 / 8820i (Broadcom CLI)
│   │       └── intelbras_gseries.py # Driver G08 e G16 (G-Series CLI)
│   ├── models/                  # Schemas Pydantic v2 tipados
│   │   ├── olt.py
│   │   ├── onu.py
│   │   ├── provision.py
│   │   └── bootstrap.py
│   ├── storage/                 # Repositórios de dados e persistência
│   │   ├── olt_repository.py    # Repositório de OLTs
│   │   └── backup_storage.py    # Gerenciamento de backups com SHA-256 e UUIDv7
│   └── main.py                  # Ponto de entrada FastAPI e middlewares
├── docs/                        # Documentação técnica, arquitetura e PRD
├── tests/
│   └── unit/                    # Testes unitários com parsers regex puros
├── .github/workflows/ci.yml     # Pipeline GitHub Actions otimizado
├── Dockerfile                   # Build multi-stage seguro (não-root)
├── docker-compose.yml           # Orquestração local
└── requirements.txt             # Dependências Python
```

---

## 3. O Padrão de Drivers (Driver / Adapter Pattern)

Todo driver de OLT deve herdar da classe abstrata `BaseOLTDriver` (`app/drivers/base.py`):

```python
from abc import ABC, abstractmethod
from typing import List, Tuple, Optional
from app.models.olt import OLTInDB
from app.models.onu import ONUSummary, ONUDetails, UnauthorizedONU
from app.models.provision import ProvisionRequest, ProvisionResponse
from app.models.bootstrap import BootstrapRequest

class BaseOLTDriver(ABC):
    @abstractmethod
    def get_running_config(self, olt: OLTInDB) -> str:
        """Coleta a configuração ativa (running-config) da OLT."""
        pass

    @abstractmethod
    def backup_config(self, olt: OLTInDB) -> str:
        """Gera e retorna o backup completo da OLT."""
        pass

    @abstractmethod
    def list_unauthorized_onus(self, olt: OLTInDB) -> List[UnauthorizedONU]:
        """Varre e lista as ONUs pendentes de autorização (autofind)."""
        pass

    @abstractmethod
    def get_port_onus(self, olt: OLTInDB, port: str) -> List[ONUSummary]:
        """Lista todas as ONUs vinculadas a uma porta PON."""
        pass

    @abstractmethod
    def get_onu_details(self, olt: OLTInDB, serial_or_id: str) -> ONUDetails:
        """Coleta detalhes e potências ópticas (Rx/Tx dBm) de uma ONU."""
        pass

    @abstractmethod
    def provision_onu(self, olt: OLTInDB, req: ProvisionRequest) -> ProvisionResponse:
        """Executa a autorização da ONU com VLAN e perfil na OLT."""
        pass

    @abstractmethod
    def generate_bootstrap_commands(self, req: BootstrapRequest) -> List[str]:
        """Gera a lista de comandos CLI para inicialização da OLT virgem."""
        pass

    @abstractmethod
    def apply_bootstrap(self, olt: OLTInDB, req: BootstrapRequest) -> int:
        """Executa os comandos de bootstrap na OLT e retorna a quantidade executada."""
        pass
```

---

## 4. Passo a Passo: Como Adicionar um Novo Driver de OLT

Exemplo: Adicionando suporte à **Huawei MA5800** (`huawei_ma5800.py`).

### Passo 1: Criar o arquivo do Driver
Crie `app/drivers/huawei/huawei_ma5800.py` herdando de `BaseOLTDriver`:

```python
from typing import List, Tuple, Optional
import re
from app.drivers.base import BaseOLTDriver
from app.models.olt import OLTInDB
from app.models.onu import ONUSummary, ONUDetails, UnauthorizedONU
from app.models.provision import ProvisionRequest, ProvisionResponse
from app.models.bootstrap import BootstrapRequest
from app.core.security import (
    sanitize_port, sanitize_serial, sanitize_vlan, sanitize_safe_string, sanitize_description
)

class HuaweiMA5800Driver(BaseOLTDriver):
    def get_running_config(self, olt: OLTInDB) -> str:
        # 1. Conecta via SSH (Paramiko)
        # 2. Desativa paginação: "smart" e "scroll"
        # 3. Executa "display current-configuration"
        ...

    @staticmethod
    def parse_unauthorized_onus(output: str) -> List[UnauthorizedONU]:
        # Regex puro sobre a saída do comando "display ont autofind all"
        results = []
        pattern = re.compile(
            r"F/S/P\s*:\s*(?P<fsp>\d+/\d+/\d+).*?Ont SN\s*:\s*(?P<sn>[A-Za-z0-9]+)",
            re.DOTALL
        )
        for match in pattern.finditer(output):
            results.append(UnauthorizedONU(
                port=match.group("fsp"),
                serial=match.group("sn"),
                discovered_at="now"
            ))
        return results
```

### Passo 2: Registrar na Factory
Edite `app/drivers/factory.py` para instanciar o driver quando `vendor == "huawei"`:

```python
elif vendor == "huawei":
    driver = HuaweiMA5800Driver()
    cls._drivers_cache[key] = driver
    return driver
```

---

## 5. Boas Práticas de Parsing com Expressões Regulares Puras

Para garantir alta testabilidade e manutenibilidade:

1. **Métodos Estáticos Puros (`@staticmethod`):**
   - Nunca misture o envio de comandos SSH com o parseamento de texto.
   - O método `parse_*` deve receber apenas uma string `output: str` e retornar modelos Pydantic tipados.
2. **Defensividade contra espaços e quebras de linha:**
   - Terminais de OLT sofrem com quebras de linha arbitrárias dependendo da largura do terminal.
   - Use flags `re.MULTILINE` e `re.IGNORECASE` quando apropriado.
   - Use `\s+` em vez de espaços fixos para tolerar variações de tabulação entre versões de firmware.
3. **Conversão Segura de Tipos:**
   - Potências ópticas devem ser convertidas com `try: float(val) except ValueError: None`.

---

## 6. Segurança e Sanitização Defensiva

O **OLTAPI** adota uma política rigorosa de **Zero Confiança em Entradas de Usuário** para mitigar riscos de **CLI Command Injection**.

Em `app/core/security.py`, você encontrará sanitizadores pré-construídos:

```python
from app.core.security import (
    sanitize_port,          # Garante formato seguro como "0/1", "1/1/1", "gpon 0/1"
    sanitize_serial,        # Garante alfanumérico seguro (ex: "ITBS12345678", "HWTC12345678")
    sanitize_vlan,          # Garante range numérico válido 1 a 4094
    sanitize_safe_string,   # Rejeita caracteres perigosos como ; | & ` $ > < \r \n
    sanitize_description,   # Limita tamanho e caracteres de descrição
    verify_api_key          # Comparação em tempo constante (hmac.compare_digest)
)
```

> [!IMPORTANT]
> **NUNCA** concatene strings diretamente em comandos CLI sem passar pelo respectivo sanitizador. Qualquer tentativa de injeção deve disparar `HTTPException(status_code=400)`.

---

## 7. Padrão de Identificadores: UUIDv7

Seguindo a **RFC 9562**, o OLTAPI utiliza **UUID versão 7** para todas as entidades persistidas (OLTs, Backups, Tarefas de Provisionamento):

- Os primeiros 48 bits contêm o timestamp Unix em milissegundos.
- Garante ordenação temporal nativa (ótimo para indexação em B-Tree no PostgreSQL/SQLite).
- No código Python:

```python
from app.core.uuid import generate_uuid7, is_valid_uuid7

novo_id = generate_uuid7() # Ex: '018e3c45-6789-7abc-def0-123456789abc'
assert is_valid_uuid7(novo_id) is True
```

---

## 8. Como Escrever Testes Unitários Sem Necessidade de Hardware Físico

Ninguém na comunidade precisa ter uma OLT física de R$ 50.000 para contribuir ou validar código!

Basta capturar a saída textual real de um comando da OLT e criar um teste unitário em `tests/unit/`:

```python
# tests/unit/test_huawei_ma5800.py
from app.drivers.huawei.huawei_ma5800 import HuaweiMA5800Driver

MOCK_AUTOFIND_OUTPUT = """
-----------------------------------------------------------------------------
Number F/S/P   Autofind   Password           Vendor-ID Equipment-ID Ont
               Time                                                 SN
-----------------------------------------------------------------------------
1      0/1/0   2026-09-10 0000000000         HWTC      5678         HWTC12345678
-----------------------------------------------------------------------------
"""

def test_parse_unauthorized_onus_huawei():
    onus = HuaweiMA5800Driver.parse_unauthorized_onus(MOCK_AUTOFIND_OUTPUT)
    assert len(onus) == 1
    assert onus[0].serial == "HWTC12345678"
    assert onus[0].port == "0/1/0"
```

Execute os testes com:
```bash
pytest tests/ -v
```

---

## 9. Executando o Ambiente Local

### Via Docker:
```bash
docker compose up -d --build
```

### Via Python venv:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Documentação OpenAPI interativa:
- `http://localhost:8000/api/v1/docs` (Swagger)
- `http://localhost:8000/api/v1/redoc` (ReDoc)
