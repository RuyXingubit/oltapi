# Plano de Implementação Aprovado: Onboarding Wizard da OLT V-SOL V1600GT e Gestão Dinâmica de VLANs

Implementar o assistente de onboarding guiado (*Wizard*) e comissionamento automatizado para a OLT V-SOL V1600GT (e compatíveis com o padrão V1600), com detecção determinística de porta auxiliar vs in-band via inspeção do `running-config`, catálogo dinâmico de VLANs com propósitos específicos (Router, Bridge, Rede Neutra, LAN-to-LAN), políticas de banda (DBA / Traffic-Limit) e sincronização do inventário com Circuit ID TR-101.

## User Review Required

> [!IMPORTANT]
> **Fluxo em Duas Fases (Inspecionar ➔ Comissionar):**
> 1. **Fase 1 (Inspeção Pré-Onboarding - `POST /api/v1/olts/inspect`):** O sistema conecta na OLT, obtém o `running-config` e retorna o diagnóstico factual da OLT:
>    - Se o IP de conexão é a porta física `aux` (ex: `192.168.8.200` ou outro IP configurado em `interface aux`).
>    - Se já existe ou não gerência In-Band ativa (`interface vlan <id>` com IP e rota padrão).
>    - Lista de VLANs e ONUs já existentes.
> 2. **Fase 2 (Comissionamento Wizard - `POST /api/v1/olts/onboard-wizard`):** O técnico/sistema envia as escolhas:
>    - Gerência In-Band (se deseja criar ou manter).
>    - Lista de VLANs com propósito declarado (`pppoe_router`, `pppoe_bridge`, `ipoe`, `rede_neutra`, `lan_to_lan`).
>    - Política de banda (1 Gbps transparente ou planos customizados).
>    - O driver executa todas as etapas com comandos nativos com `commit` e `write`, seguido da ingestão de inventário e telemetria.

---

## Proposed Changes

### Componente 1: Driver V-SOL V1600 (`app/drivers/vsol/vsol_v1600.py`)

#### [MODIFY] vsol_v1600.py
* **Autenticação em Modo Enable:** Tratar o prompt `Password:` ao enviar `enable\n`, fornecendo a senha da OLT caso solicitado.
* **Parser de Arquitetura de Gerência (`parse_management_architecture`):**
  - Analisar o `running-config` e extrair:
    - IP da `interface aux`.
    - Lista de interfaces SVI `interface vlan <id>` com seus IPs, máscaras e rotas (`ip route 0.0.0.0/0`).
    - Classificar o status de acesso: `AUX_ONLY` (Cenário 1), `AUX_WITH_INBAND` (Cenário 2), `INBAND_ACTIVE` (Cenário 3).
* **Comissionamento In-Band (`configure_inband_management`):**
  - Configurar `vlan <id>`, `interface vlan <id>`, `ip address X.X.X.X/M`, `ip route 0.0.0.0/0 X.X.X.X` e portas uplink em modo hybrid/trunk.
* **Provisionamento de VLANs e Serviços com `commit` nativo:**
  - Criação de VLANs e tagging em portas de uplink (GE/XE) e GPON.
  - Compilação dos perfis GPON com o comando obrigatório `commit`:
    - DBA: `profile dba id <id> name <name>` -> `type 4 maximum <kbps>` -> `commit`.
    - Line Profile: T-CONT -> GEM Port -> Service / Service-port -> `commit`.
    - Service Profile: `portvlan veip 1 mode transparent` (para HGU) ou `portvlan eth 1 mode transparent` (para SFU/Bridge) -> `commit`.
  - Habilitação de comutação local intra-PON para LAN-to-LAN: `p2p enable` na interface GPON.
  - Configuração de portas de teste GE (ex: `ge 0/4` com `pvid 100` e `untagged 100`).
  - Gravação persistente na flash: `write` (`/mnt/config/usrcfg.conf`).
* **Parsers Aprimorados:**
  - `parse_onu_state`: extrair `OnuIndex`, `Admin State`, `OMCC State`, `Phase State` (`working`, `syncMib`, etc.), `Serial Number`.
  - `parse_onu_info`: extrair `Model`, `Profile`, `AuthInfo`.
  - `parse_optical_diagnostics`: extrair `Rx optical level`, `Tx optical level`, `Temperature`, `Laser bias`.

---

### Componente 2: Modelos e Schemas (`app/models/olt.py`)

#### [MODIFY] olt.py
* Adicionar modelos de dados para o Wizard:
  - `ManagementAccessScenario(str, Enum)`: `AUX_ONLY`, `AUX_WITH_INBAND`, `INBAND_ACTIVE`.
  - `InBandManagementConfig`: `vlan_id`, `uplink_port`, `ip_cidr`, `gateway`, `mode` (`tagged`/`untagged`).
  - `VLANServicePurpose(str, Enum)`: `PPPOE_ROUTER`, `PPPOE_BRIDGE`, `IPOE`, `REDE_NEUTRA`, `LAN_TO_LAN`.
  - `VLANServiceItem`: `vlan_id`, `name`, `purpose`, `uplink_port`, `tagged` (bool), `test_port` (opcional).
  - `BandwidthQoSPolicy`: `policy_type` (`TRANSPARENT_1G`, `CUSTOM_LIMITS`), `upstream_kbps`, `downstream_kbps`.
  - `OLTInspectRequest`: `host`, `username`, `password`, `port` (opcional).
  - `OLTInspectResponse`: `vendor`, `model`, `access_scenario`, `aux_ip`, `existing_svis`, `existing_vlans`, `total_onus_detected`, `prompt_message`.
  - `OLTWizardOnboardRequest`: Dados de acesso base + `inband_config` (opcional) + `services` (lista de `VLANServiceItem`) + `qos_policy`.

---

### Componente 3: Serviços (`app/services/olt_onboarding_service.py`)

#### [MODIFY] olt_onboarding_service.py
* **Método `inspect_olt(request: OLTInspectRequest)`:**
  1. Conecta na OLT via SSH/Telnet.
  2. Executa fingerprint do fabricante (V-SOL / Fiberhome / Huawei).
  3. Coleta o `running-config` e invoca `driver.parse_management_architecture()`.
  4. Retorna `OLTInspectResponse` indicando o cenário exato e orientando o assistente.
* **Método `execute_wizard_onboarding(request: OLTWizardOnboardRequest)`:**
  1. Conexão e Baseline v0 prévio com SHA-256.
  2. Execução da configuração In-Band (se solicitada).
  3. Criação das VLANs de serviço e mapeamento de Uplinks.
  4. Geração dos perfis de Linha e Serviço com `commit`.
  5. Ativação de `p2p enable` nas portas GPON para serviços do tipo `LAN_TO_LAN`.
  6. Configuração de porta de teste untagged (se informada).
  7. Persistência na flash (`write`).
  8. Ingestão de inventário e cálculo de Circuit ID TR-101 para todas as ONUs detectadas.

---

### Componente 4: API Endpoints (`app/api/v1/endpoints_olts.py`)

#### [MODIFY] endpoints_olts.py
* `POST /api/v1/olts/inspect`: Rota pública/protegida para pré-inspeção da OLT antes do comissionamento.
* `POST /api/v1/olts/onboard-wizard`: Rota para execução do comissionamento assistido em lote.

---

### Componente 5: Testes Unitários e Contratos

#### [MODIFY] test_vsol_driver.py
* Adicionar testes para os novos métodos de parsing de running-config (aux vs vlan), diagnósticos ópticos e geração de comandos com `commit`.

#### [NEW] test_vsol_onboard_wizard.py
* Testes do fluxo de inspeção prévia (`inspect_olt`) nos 3 cenários (bancada pura, in-band existente, produção).
* Testes do pipeline completo de onboarding wizard (`execute_wizard_onboarding`).

#### [SYNC] OpenAPI Contracts
* Executar `python -m scripts.export_openapi` e sincronizar `docs/api_contracts/openapi.yaml` e `.json`.

---

## Verification Plan

### Automated Tests
1. Rodar os testes unitários do driver V-SOL e do wizard:
   ```bash
   .venv/bin/pytest tests/unit/test_vsol_driver.py tests/unit/test_vsol_onboard_wizard.py -v
   ```
2. Rodar a suíte completa de testes para garantir regressão zero:
   ```bash
   .venv/bin/pytest tests/unit/
   ```
3. Exportar e validar os contratos OpenAPI:
   ```bash
   python -m scripts.export_openapi
   ```

### Manual Verification (Live Hardware na Bancada)
1. Executar a inspeção prévia (`POST /api/v1/olts/inspect`) contra a OLT física da bancada em `192.168.8.200` e verificar o retorno do cenário.
2. Executar o onboarding wizard completo via script de teste local, verificando:
   - Registro da OLT no banco de dados.
   - Preservação da porta AUX e validação da SVI VLAN 2.
   - Detecção e ingestão no inventário das 2 ONUs ativas na bancada (Huawei `HWTC073545b7` e Intelbras `ITBS5f44ca50`) com geração de seus respectivos Circuit IDs TR-101.
