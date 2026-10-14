# Guia de Contribuição: OLT Provisioning & Diagnostics Unified API (`oltapi`)

Seja muito bem-vindo ao projeto **OLTAPI**! 🎉

Nosso objetivo é manter uma camada unificada, aberta e agnóstica para automação, provisionamento e telemetria de OLTs multi-fabricante (**Fiberhome**, **V-SOL**, **Parks Fiberlink** e novos concentradores homologados em bancada física), permitindo que qualquer **ERP de Provedor**, operadora de **Rede Neutra** ou operador via **Central NOC Flutter** opere a rede óptica com simplicidade e segurança.

---

## 🧭 Manuais e Especificação Oficial

Antes de começar, consulte a documentação oficial do projeto:
- 📐 **[System Design & Specification Document (`docs/SDD.md`)](docs/SDD.md)**: Fonte única da verdade de engenharia, arquitetura das stacks, contratos OpenAPI e regras de governança.
- 🛠️ **[Manual do Desenvolvedor (`docs/MANUAL_DESENVOLVEDOR.md`)](docs/MANUAL_DESENVOLVEDOR.md)**: Arquitetura detalhada, `DriverRegistry`, `BaseDriverComplianceTest` e como escrever parsers com regex puras.
- 📡 **[Manual Operacional & Guia de Integração de ERP (`docs/MANUAL_OPERACIONAL.md`)](docs/MANUAL_OPERACIONAL.md)**: Guia prático de uso com cURL, Python, PHP, Node.js e endpoints da API.

---

## 📋 Índice
1. [Diretrizes de Arquitetura & Governança de Drivers](#-diretrizes-de-arquitetura--governança-de-drivers)
2. [Como Homologar e Adicionar um Novo Driver de OLT](#-como-homologar-e-adicionar-um-novo-driver-de-olt)
3. [Boas Práticas de Segurança](#-boas-práticas-de-segurança)
4. [Suíte de Conformidade e Testes Unitários](#-suíte-de-conformidade-e-testes-unitários)
5. [Fluxo de Trabalho Git e Pull Requests](#-fluxo-de-trabalho-git-e-pull-requests)

---

## 🏛️ Diretrizes de Arquitetura & Governança de Drivers

O projeto utiliza o padrão **Ports & Adapters (`BaseOLTDriver` + `@DriverRegistry.register`)**:
- O núcleo da API (`FastAPI`) e os serviços de negócio conversam exclusivamente com métodos polimórficos da interface [`BaseOLTDriver`](file:///Volumes/240/Code/oltapi/app/drivers/base.py).
- É terminantemente proibido usar `hasattr(driver, ...)` ou condicionais de fabricante (`if olt.vendor == ...`) nas camadas de serviço, bem como um driver importar outro driver.
- **Proibição de Fabricantes Teóricos:** Novos drivers só entram na árvore do projeto mediante acesso a **hardware físico real em bancada** para homologação completa (leitura, gravação atômica, backup FTP + fallback e provisionamento com tráfego real).

---

## 🔌 Como Homologar e Adicionar um Novo Driver de OLT

Para adicionar suporte a um novo equipamento físico homologado em bancada, siga estes 3 passos:

### Passo 1: Criar o Driver com Auto-Registro (`@DriverRegistry.register`)
Crie o arquivo na pasta correspondente em `app/drivers/<fabricante>/<modelo>.py` herdando de `BaseOLTDriver` e registrando-o dinamicamente via decorador (sem necessidade de editar `app/drivers/factory.py`):

```python
from typing import List, Optional
from app.drivers.base import BaseOLTDriver
from app.drivers.registry import DriverRegistry
from app.models.ftp import FTPDestinationConfig
from app.models.olt import OLTInDB
from app.models.onu import ONUSummary, ONUDetails, UnauthorizedONU
from app.models.provision import ProvisionRequest, ProvisionResponse

@DriverRegistry.register(vendor="novo_fabricante", model_prefix="modelo_x")
class NovoFabricanteDriver(BaseOLTDriver):
    def handles_primary_ftp_upload(self) -> bool:
        return True

    def get_running_config(self, olt: OLTInDB) -> str:
        ...

    def backup_config(self, olt: OLTInDB, ftp_destination: Optional[FTPDestinationConfig] = None) -> str:
        # Prioridade 1: Upload nativo via FTP da OLT; Prioridade 2: Fallback para get_running_config
        ...

    def list_unauthorized_onus(self, olt: OLTInDB) -> List[UnauthorizedONU]:
        ...

    def get_port_onus(self, olt: OLTInDB, port: str) -> List[ONUSummary]:
        ...

    def get_onu_details(self, olt: OLTInDB, serial_or_id: str) -> ONUDetails:
        ...

    def provision_onu(self, olt: OLTInDB, req: ProvisionRequest) -> ProvisionResponse:
        ...
```

### Passo 2: Criar Métodos Estáticos de Parsing
Sempre separe a lógica de leitura de texto (parsers regex) em métodos estáticos puros (`@staticmethod`):
- `parse_unauthorized_onus(output: str) -> List[UnauthorizedONU]`
- `parse_port_onus(output: str, port: str) -> List[ONUSummary]`
- `parse_optical_info(output: str) -> ...`

### Passo 3: Incluir na Suíte de Conformidade (`BaseDriverComplianceTest`)
Todo driver ativo deve passar nos 12 testes polimórficos obrigatórios em [`tests/unit/test_driver_compliance.py`](file:///Volumes/240/Code/oltapi/tests/unit/test_driver_compliance.py) (`get_running_config`, `backup_config` FTP + fallback, `get_chassis_interfaces`, `get_onu_details`, `provision_onu`, `deprovision_onu`, `suspend_onu`, `resume_onu`, `reboot_onu`, `configure_snmp`, `list_all_authorized_onus`, `inspect_management_arch` e `execute_wizard_commissioning`).

---

## 🔒 Boas Práticas de Segurança

Ao submeter código, certifique-se de seguir os pilares obrigatórios do projeto:
1. **Prevenção contra CLI Command Injection & SSRF:**
   - Nunca concatene strings cruas fornecidas pelo usuário em comandos de terminal.
   - Use os sanitizadores disponíveis em `app.core.security`: `sanitize_port`, `sanitize_serial`, `sanitize_vlan`, `sanitize_safe_string`, `sanitize_description` e `sanitize_webhook_url`.
2. **Controle de Acesso RBAC Multi-Tenant:**
   - Toda rota deve validar escopo (`ctx.enforce_scope(...)`) e isolamento de OLT/VLAN (`ctx.enforce_olt(olt_id)` / `ctx.enforce_vlan(vlan_id)`).
3. **Identificadores UUIDv7:**
   - Todos os identificadores devem utilizar `app.core.uuid.generate_uuid7()`.
4. **Credenciais Protegidas com Fernet AES:**
   - Senhas e segredos são armazenados cifrados com `encrypt_password` e jamais expostos em respostas `GET`.

---

## 🧪 Suíte de Conformidade e Testes Unitários

1. Capture saídas reais de CLI do equipamento homologado em bancada.
2. Adicione os cenários de teste em `tests/unit/test_<fabricante>_driver.py` e na `BaseDriverComplianceTest`.
3. Execute a suíte completa localmente:

```bash
source .venv/bin/activate
pytest tests/ -v
```

---

## 🚀 Fluxo de Trabalho Git e Pull Requests

1. Faça um **Fork** do projeto e crie uma branch para sua funcionalidade:
   ```bash
   git checkout -b feat/driver-novo-fabricante
   ```
2. Garanta que **100% dos testes unitários estejam passando**:
   ```bash
   pytest tests/ -v
   ```
3. **Sincronização Obrigatória do OpenAPI (Mandatório antes de Commit & Push):**
   ```bash
   python -m scripts.export_openapi
   git add docs/api_contracts/
   ```
   *(Dica: execute `python scripts/install_git_hooks.py` para instalar os hooks locais que automatizam essa etapa no `pre-commit` e `pre-push`).*
4. Faça o commit seguindo o padrão de commits semânticos e abra um **Pull Request** acompanhado do relatório de homologação em bancada física (`docs/HOMOLOGACAO_<FABRICANTE>.md`).

Obrigado por ajudar a evoluir a automação aberta de telecomunicações! 🌐
