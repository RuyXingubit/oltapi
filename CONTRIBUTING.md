# Guia de Contribuição: OLT Provisioning & Diagnostics Unified API

Seja muito bem-vindo ao projeto **OLTAPI**! 🎉

Nosso objetivo é construir uma camada unificada, aberta e agnóstica para automação, provisionamento e telemetria de OLTs de múltiplos fabricantes (Intelbras, Huawei, Fiberhome, Parks, ZTE, Datacom, Nokia, etc.), permitindo que qualquer **ERP de Provedor** ou **técnico com Postman/cURL** opere a rede óptica com simplicidade e segurança.

---

## 🧭 Manuais Disponíveis

Antes de começar, consulte os nossos manuais dedicados:
- 🛠️ **[Manual do Desenvolvedor](docs/MANUAL_DESENVOLVEDOR.md)**: Arquitetura detalhada, fluxo de dados, padrão de drivers e como escrever parsers com regex puras.
- 📡 **[Manual Operacional & Guia de Integração de ERP](docs/MANUAL_OPERACIONAL.md)**: Guia prático de uso com cURL, Python, PHP, Node.js e endpoints da API.

---

## 📋 Índice
1. [Diretrizes de Arquitetura](#-diretrizes-de-arquitetura)
2. [Como Adicionar um Novo Fabricante / Driver de OLT](#-como-adicionar-um-novo-fabricante--driver-de-olt)
3. [Boas Práticas de Segurança](#-boas-práticas-de-segurança)
4. [Como Escrever Testes com Parsers Puros](#-como-escrever-testes-com-parsers-puros)
5. [Fluxo de Trabalho Git e Pull Requests](#-fluxo-de-trabalho-git-e-pull-requests)

---

## 🏛️ Diretrizes de Arquitetura

O projeto utiliza o padrão **Driver / Adapter Pattern**:
- O núcleo da API (`FastAPI`) conhece apenas o contrato genérico `BaseOLTDriver`.
- Toda particularidade de sintaxe de terminal (VRP, CLIOS, Broadcom, G-Series, TL1) fica estritamente isolada dentro do respectivo driver do fabricante em `app/drivers/<fabricante>/`.
- **Zero Dependências do ERP com Fabricantes:** O ERP nunca envia comandos de terminal. Ele envia apenas payloads padronizados com `serial`, `port`, `vlan` e `profile`.

---

## 🔌 Como Adicionar um Novo Fabricante / Driver de OLT

Para adicionar suporte a um novo equipamento (ex: *Huawei MA5800*, *Fiberhome AN5516*, *Parks*, *ZTE*, *Datacom*), siga estes 4 passos:

### Passo 1: Criar o arquivo do Driver
Crie o arquivo na pasta correspondente em `app/drivers/<fabricante>/<modelo>.py` herdando de `BaseOLTDriver`:

```python
from typing import List
from app.drivers.base import BaseOLTDriver
from app.models.olt import OLTInDB
from app.models.onu import ONUSummary, ONUDetails, UnauthorizedONU
from app.models.provision import ProvisionRequest, ProvisionResponse
from app.models.bootstrap import BootstrapRequest

class MeuFabricanteDriver(BaseOLTDriver):
    def get_running_config(self, olt: OLTInDB) -> str:
        # Envia comandos de leitura (ex: display current-configuration)
        ...

    def backup_config(self, olt: OLTInDB) -> str:
        return self.get_running_config(olt)

    def list_unauthorized_onus(self, olt: OLTInDB) -> List[UnauthorizedONU]:
        # Coleta e faz o parse de ONUs não autorizadas
        ...

    def get_port_onus(self, olt: OLTInDB, port: str) -> List[ONUSummary]:
        # Lista ONUs da porta informada
        ...

    def get_onu_details(self, olt: OLTInDB, serial_or_id: str) -> ONUDetails:
        # Consulta potência óptica (dBm) e status
        ...

    def provision_onu(self, olt: OLTInDB, req: ProvisionRequest) -> ProvisionResponse:
        # Executa comandos de provisionamento e salva memória
        ...

    def generate_bootstrap_commands(self, req: BootstrapRequest) -> List[str]:
        # Gera o script CLI para configuração inicial da OLT virgem
        ...

    def apply_bootstrap(self, olt: OLTInDB, req: BootstrapRequest) -> int:
        commands = self.generate_bootstrap_commands(req)
        # Executa comandos via SSH/CLI
        return len(commands)
```

### Passo 2: Registrar o Driver na Factory
No arquivo `app/drivers/factory.py`, conecte o novo driver no método `get_driver`:

```python
elif vendor == "meufabricante":
    driver = MeuFabricanteDriver()
    cls._drivers_cache[key] = driver
    return driver
```

### Passo 3: Criar Métodos Estáticos de Parsing
Sempre separe a lógica de leitura de texto (parsers regex) em métodos estáticos puros:
- `parse_unauthorized_onus(output: str) -> List[UnauthorizedONU]`
- `parse_port_onus(output: str, port: str) -> List[ONUSummary]`
- `parse_optical_info(output: str) -> Tuple[Optional[float], Optional[float]]`

*Por que fazer isso?* Isso permite que a comunidade teste 100% dos seus parsers sem precisar que outra pessoa tenha uma OLT de R$ 50.000 ligada na bancada!

---

## 🔒 Boas Práticas de Segurança

Ao submeter código, certifique-se de seguir os pilares obrigatórios do projeto:
1. **Prevenção contra CLI Command Injection:**
   - Nunca concatene strings cruas fornecidas pelo usuário em comandos de terminal.
   - Use os sanitizadores disponíveis em `app.core.security`:
     - `sanitize_port(port)`
     - `sanitize_serial(serial)`
     - `sanitize_vlan(vlan)`
     - `sanitize_safe_string(text, field_name)`
     - `sanitize_description(desc)`
2. **Identificadores UUIDv7:**
   - Todos os novos identificadores temporais devem utilizar `app.core.uuid.generate_uuid7()`.
3. **Credenciais Protegidas:**
   - As senhas da OLT nunca devem ser expostas em nenhum endpoint de leitura (`GET`).

---

## 🧪 Como Escrever Testes com Parsers Puros

1. Capture saídas reais de CLI do seu equipamento (`show ...`, `display ...`).
2. Adicione os cenários de teste em `tests/unit/test_<fabricante>_<modelo>.py`.
3. Valide o script de bootstrap e a resolução na `DriverFactory`.
4. Execute a suite localmente:

```bash
# Ative o ambiente virtual
source .venv/bin/activate

# Execute a suite completa
pytest tests/ -v
```

---

## 🚀 Fluxo de Trabalho Git e Pull Requests

1. Faça um **Fork** do projeto.
2. Crie uma branch para sua funcionalidade ou driver:
   ```bash
   git checkout -b feature/driver-huawei-ma5800
   ```
3. Garanta que **100% dos testes unitários estejam passando**:
   ```bash
   pytest tests/ -v
   ```
4. **Sincronização Obrigatória do OpenAPI (Mandatório antes de Commit & Push):**
   ```bash
   python -m scripts.export_openapi
   git add docs/api_contracts/
   ```
   *(Dica: execute `python scripts/install_git_hooks.py` para instalar os hooks locais que automatizam essa etapa no `pre-commit` e `pre-push`).*
5. Faça o commit com mensagens claras seguindo o padrão de commits semânticos:
   ```bash
   git commit -m "feat(driver): add Huawei MA5800 driver and optical diagnostic parser"
   ```
6. Envie para o seu Fork e abra um **Pull Request** detalhando:
   - Modelo da OLT testada e versão de firmware.
   - Exemplos de saídas de CLI utilizadas nos testes.
   - Casos cobertos.

Obrigado por ajudar a democratizar a automação de telecomunicações! 🌐
