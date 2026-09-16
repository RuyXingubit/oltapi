# Manual do Desenvolvedor: Governança de Drivers & Arquitetura (OLTAPI)

Bem-vindo ao **Manual do Desenvolvedor do OLTAPI**! Este guia foi elaborado para desenvolvedores e arquitetos que queiram entender a arquitetura do projeto, contribuir com novas funcionalidades ou homologar novos fabricantes e modelos de OLT.

---

## 1. Visão Geral da Arquitetura

O **OLTAPI** foi projetado com os seguintes princípios:

- **API-First & Agnóstica de Fabricante:** O cliente da API (seja um ERP como IXC Soft, MK-Auth ou o Frontend Flutter NOC) nunca precisa saber a sintaxe de terminal (CLI) específica de cada marca. O tráfego ocorre estritamente sobre contratos REST JSON padronizados.
- **Inversão de Dependência Radical (Ports & Adapters):** Os serviços de negócio conversam exclusivamente com métodos polimórficos da interface `BaseOLTDriver`. É terminantemente proibido utilizar `hasattr(driver, ...)` ou condicionais de fabricante (`if olt.vendor == ...`) nas camadas de serviço.
- **Isolamento entre Drivers:** Um driver jamais deve importar outro driver ou presumir formatos hardcoded.
- **Segurança em Primeiro Lugar:** Nenhuma entrada do usuário é passada sem sanitização para o terminal da OLT, prevenindo injeção de comandos CLI.

```
[ ERP / Postman / Frontend NOC ]
               │
               │  JSON + X-API-Key
               ▼
[ FastAPI Application (app/main.py) ]
               │
               │  Validação Pydantic v2 + Sanitização Regex
               ▼
[ API Routers (app/api/v1/*.py) ]
               │
               │  DriverFactory.get_driver(olt) -> DriverRegistry
               ▼
[ Driver Abstraction (BaseOLTDriver) ]
               ├──> FiberhomeTL1Driver (AN5516 / AN6000 TL1)
               └──> VSOLV1600Driver (V1600G / V1600GT CLI)
```

---

## 2. Estrutura de Diretórios

```
oltapi/
├── app/
│   ├── api/
│   │   └── v1/                      # Endpoints REST organizados por domínio
│   │       ├── endpoints_olts.py        # Cadastro, running-config, backups, audit e diff
│   │       ├── endpoints_backups.py     # Disparo em lote e auditoria global
│   │       ├── endpoints_diagnostics.py # Portas, ONUs e diagnóstico óptico
│   │       ├── endpoints_provision.py   # Provisionamento, ciclo de vida e autofind
│   │       ├── endpoints_onu_inventory.py# Inventário global e histórico TR-101
│   │       └── endpoints_bootstrap.py   # Inicialização zero-touch e preview
│   ├── core/
│   │   ├── config.py                # Pydantic Settings (.env, retenção, timeouts)
│   │   ├── security.py              # Sanitizadores regex e validação de API Key
│   │   └── uuid.py                  # Gerador e validador nativo de UUIDv7 (RFC 9562)
│   ├── db/                          # Modelos SQLAlchemy e sessão PostgreSQL
│   ├── drivers/
│   │   ├── base.py                  # Interface abstrata BaseOLTDriver
│   │   ├── registry.py              # DriverRegistry com registro dinâmico via decorador
│   │   ├── factory.py               # DriverFactory integrada ao Registry
│   │   ├── fiberhome/               # Fiberhome AN5516 (TL1 Bellcore)
│   │   └── vsol/                    # V-SOL série V1600 (CLI)
│   ├── models/                      # Schemas Pydantic v2 tipados
│   ├── services/                    # Orquestradores de negócio desacoplados
│   └── main.py                      # Ponto de entrada FastAPI 100% REST JSON
├── docs/                            # Documentação técnica MkDocs Material
├── frontend/                        # Central de Operações NOC em Flutter (Desktop/Web)
├── tests/
│   └── unit/                        # Suíte de 219 testes unitários e de conformidade
├── docker-compose.yml               # Orquestração local e produção com PostgreSQL 16
├── requirements.txt                 # Dependências Python
└── mkdocs.yml                       # Configuração do site de documentação
```

---

## 3. Governança de Drivers: Inversão de Dependência & Dynamic Registry

Cada driver se registra de forma autônoma no `DriverRegistry` utilizando o decorador `@DriverRegistry.register`:

```python
from app.drivers.registry import DriverRegistry
from app.drivers.base import BaseOLTDriver

@DriverRegistry.register(vendor="vsol", model_prefix="v1600")
class VSOLV1600Driver(BaseOLTDriver):
    ...
```

Dessa forma:
1. Novos drivers se auto-declaram sem modificar o código da `DriverFactory`.
2. A resolução é feita dinamicamente combinando o fabricante (`vendor`) e o prefixo do modelo (`model_prefix`).
3. O driver é instanciado em cache de forma lazy e thread-safe.

---

## 4. Proibição de Fabricantes Teóricos & Homologação em Bancada

> [!CAUTION]
> **REGRA DE OURO DO PROJETO:** É TERMINANTEMENTE PROIBIDO adicionar novos drivers de fabricantes sem acesso a hardware físico de bancada para homologação real.

Drivers criados apenas na teoria ou a partir de suposições de IA foram completamente removidos da árvore do projeto. Novos drivers só entram na árvore após:
1. Ter acesso à OLT física conectada e energizada.
2. Homologação com tráfego real nos modos Bridge e Router (PPPoE).
3. Aprovação explícita em todos os testes da suíte de conformidade.

---

## 5. Como Adicionar e Homologar um Novo Driver de OLT

### Passo 1: Implementar a Interface `BaseOLTDriver`
Crie o novo driver herdando de `BaseOLTDriver` e decorando a classe:

```python
from app.drivers.registry import DriverRegistry
from app.drivers.base import BaseOLTDriver
from app.models.olt import OLTInDB
from app.models.onu import ONUDetails, UnauthorizedONU
from app.models.provision import ProvisionRequest, ProvisionResponse

@DriverRegistry.register(vendor="novo_fabricante", model_prefix="modelo_x")
class NovoFabricanteDriver(BaseOLTDriver):
    def handles_primary_ftp_upload(self) -> bool:
        return True  # True se suportar upload nativo por FTP, False se for captura de terminal

    def get_running_config(self, olt: OLTInDB) -> str:
        ...

    def backup_config(self, olt: OLTInDB, ftp_destination: Optional[FTPDestinationConfig] = None) -> str:
        ...

    def list_unauthorized_onus(self, olt: OLTInDB) -> List[UnauthorizedONU]:
        ...

    def get_onu_details(self, olt: OLTInDB, serial_or_id: str) -> ONUDetails:
        ...

    def provision_onu(self, olt: OLTInDB, req: ProvisionRequest) -> ProvisionResponse:
        ...
```

---

## 6. Padrão Canônico de Backup & Disaster Recovery

Todo driver ativo deve seguir o padrão canônico em duas etapas:
1. **Prioridade 1 (Nativo por FTP):** Se a OLT suportar comando nativo de upload (ex: `copy startup-config ftp://...` ou upload via TL1), o driver deve enviar diretamente ao servidor FTP configurado.
2. **Prioridade 2 (Fallback Gracioso):** Caso nenhum servidor FTP esteja vinculado ou o upload falhe, o driver DEVE capturar o `running-config` pelo terminal (SSH/Telnet) e salvar com criptografia local Fernet AES-256 e hash SHA-256.

---

## 7. Suíte de Conformidade Obrigatória (`BaseDriverComplianceTest`)

Todo driver ativo deve passar na suíte de conformidade em `tests/unit/test_driver_compliance.py`. Os 12 métodos obrigatórios são:

1. `get_running_config`: Retorna a configuração sem truncamento.
2. `backup_config` (com FTP): Realiza upload com sucesso.
3. `backup_config` (sem FTP / fallback): Captura texto completo do terminal.
4. `get_chassis_interfaces`: Lista interfaces físicas reais sem dados falsos.
5. `get_onu_details`: Extrai potências ópticas reais em dBm (Rx OLT, Rx ONU, Tx ONU).
6. `provision_onu`: Provisiona com VLAN e perfil sem injeção de comandos.
7. `deprovision_onu`: Desprovisiona a ONU e libera a porta PON.
8. `suspend_onu`: Bloqueia tráfego por inadimplência.
9. `resume_onu`: Desbloqueia a ONU.
10. `reboot_onu`: Envia comando de reinício remoto.
11. `list_all_authorized_onus`: Lista o inventário da OLT.
12. `inspect_management_arch`: Classifica o cenário de gerência (AUX_ONLY, INBAND, etc.).

---

## 8. Boas Práticas de Parsing com Expressões Regulares Puras

1. **Métodos Estáticos Puros (`@staticmethod`):** Nunca misture o envio de comandos SSH com o parseamento de texto. O método `parse_*` deve receber apenas uma string `output: str` e retornar modelos Pydantic tipados.
2. **Defensividade contra quebras de linha de terminal:** Use flags `re.MULTILINE`, `re.IGNORECASE` e `\s+` em vez de espaços fixos.
3. **Conversão Segura de Tipos:** Potências ópticas devem ser convertidas com tratamento de exceções:
   ```python
   try:
       rx_power = float(raw_val)
   except (ValueError, TypeError):
       rx_power = None
   ```

---

## 9. Segurança e Sanitização Defensiva

O **OLTAPI** adota uma política rigorosa de **Zero Confiança em Entradas de Usuário** para mitigar riscos de **CLI Command Injection**:

```python
from app.core.security import (
    sanitize_port,          # Garante formato seguro como "0/1", "1/1/1", "gpon 0/1"
    sanitize_serial,        # Garante alfanumérico seguro (ex: "VSOL12345678")
    sanitize_vlan,          # Garante range numérico válido 1 a 4094
    sanitize_safe_string,   # Rejeita caracteres perigosos como ; | & ` $ > < \r \n
    verify_api_key          # Comparação em tempo constante (hmac.compare_digest)
)
```

---

## 10. Padrão de Identificadores: UUIDv7

Seguindo a **RFC 9562**, o OLTAPI utiliza **UUID versão 7** para todas as entidades persistidas:
- Os primeiros 48 bits contêm o timestamp Unix em milissegundos.
- Garante ordenação temporal nativa no banco de dados relacional.
- Gerador implementado em `app/core/uuid.py`:
  ```python
  from app.core.uuid import generate_uuid7
  novo_id = generate_uuid7()
  ```

---

## 11. Frontend NOC em Flutter: Estrutura e Execução

A Central de Operações de Rede está localizada em `frontend/`:
- **Design System NOC:** Cores semânticas de alto contraste (`AppColors`) e tema escuro (`AppTheme`).
- **Gerenciamento de Estado:** Reativo via `provider` (`SettingsProvider` e `AppState`).
- **Execução:**
  ```bash
  cd frontend
  flutter pub get
  flutter run -d macos  # Modo Desktop macOS
  flutter run -d chrome # Modo Web
  ```
- **Testes:**
  ```bash
  flutter analyze # Análise estática
  flutter test    # Suíte de testes unitários e de widgets
  ```

---

## 12. Executando o Ambiente Local e Testes

### Executar Testes do Backend (Pytest):
```bash
source .venv/bin/activate
pytest tests/unit -v
```

### Sincronização Obrigatória do OpenAPI antes de Commit & Push:
```bash
python -m scripts.export_openapi
```

### Executar Stack Completa via Docker Compose:
```bash
docker compose up -d --build
```
- **API REST & Healthcheck:** `http://localhost:8000/health`
- **Swagger UI:** `http://localhost:8000/api/v1/docs`
- **ReDoc:** `http://localhost:8000/api/v1/redoc`
