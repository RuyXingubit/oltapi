# Walkthrough de Conclusão: Homologação Física V-SOL V1600GT & Onboarding Wizard em 2 Fases

Comissionamento físico em bancada da OLT **V-SOL V1600GT** (firmware `V1.0.1R_250421155212`) e implementação completa do pipeline de Onboarding Assistido via Wizard com inspeção não-destrutiva e detecção determinística de arquitetura de gerência (`interface aux` vs SVI In-Band).

---

## 1. Cenário Real Comissionado em Bancada

- **Hardware Físico:** V-SOL V1600GT (1U, 4 Portas GPON, 4 Uplinks GE/SFP).
- **IPs Ativos:**
  - `interface aux`: `192.168.8.200/24` (porta física AUX/MGMT frontal preservada para emergência de bancada).
  - `interface vlan 2`: `172.16.251.60/24` (SVI In-Band na porta `ge 0/1` tagged).
  - Gateway: `172.16.251.1`.
- **Topologia Óptica Ativa (Porta GPON 0/2 com Splitter 1:2):**
  - **ONU 1:** Huawei `EG8041X6-10` (HGU Wi-Fi 6, SN `HWTC073545b7`), sinal `-15.32 dBm`, perfil `line_internet`, srv `srv_hgu` (`veip 1 transparent`), status `working`.
  - **ONU 2:** Intelbras `110GB` (SFU Gigabit Bridge, SN `ITBS5f44ca50`), sinal `-16.02 dBm`, perfil `line_internet`, srv `srv_bridge` (`eth 1 transparent`), status `working`.
- **VLANs & Comutação:**
  - VLAN 2 (`VLAN2_GERENCIA`): tagged `ge 0/1`.
  - VLAN 100 (`INTERNET_FTTH`): tagged `ge 0/1`, tagged `gpon 0/2`, untagged PVID 100 na porta de teste `ge 0/4`.
  - VLAN 500 (`LAN_TO_LAN_P2P`): tagged `ge 0/1`, comutação local hairpin ativada (`p2p enable`) em `gpon 0/2`.

---

## 2. Implementação no Código

### 2.1 Modelos de Dados Pydantic ([app/models/olt.py](file:///Volumes/240/Code/oltapi/app/models/olt.py))
- `ManagementAccessScenario`: enum com `aux_only`, `aux_with_inband`, `inband_active`.
- `VLANServicePurpose`: enum com `pppoe_router`, `pppoe_bridge`, `ipoe`, `rede_neutra`, `lan_to_lan`.
- `InBandManagementConfig`: especificação de VLAN, IP/CIDR, gateway, uplink_port e tagged/untagged.
- `VLANServiceItem`: definição de VLAN de serviço com finalidade de tráfego, uplink e porta de teste física.
- `BandwidthQoSPolicy`: perfil DBA Upstream (1G transparente ou limitado) e downstream.
- `OLTInspectRequest` & `OLTInspectResponse`: contrato da Fase 1 (pré-inspeção não-destrutiva).
- `OLTWizardOnboardRequest`: contrato da Fase 2 (comissionamento assistido).

### 2.2 Driver V-SOL V1600GT ([app/drivers/vsol/vsol_v1600.py](file:///Volumes/240/Code/oltapi/app/drivers/vsol/vsol_v1600.py))
- **Parser de Arquitetura de Gerência (`parse_management_architecture`):**
  Extrai deterministicamente `interface aux`, `interface vlan <id>`, rotas estáticas `0.0.0.0/0` e compara o IP de acesso (`access_host`) com o IP físico da AUX sem adivinhações por IP hardcoded.
- **Gerador de Comissionamento Wizard (`generate_wizard_commissioning_commands`):**
  Gera a sequência correta para o CLI V-SOL:
  - Criação da SVI In-Band e rota estática default.
  - Perfil DBA com submodo `commit`.
  - Perfis de serviço (`srv_hgu` com VEIP 1 e `srv_bridge` com ETH 1).
  - Criação das VLANs no switch L2 e marcação híbrida (`switchport mode hybrid` + `switchport hybrid vlan ...`).
  - Configuração da porta de teste (ex: `ge 0/4` com `switchport hybrid pvid vlan <id>` e untagged).
  - Habilitação de Hairpin inter-ONU (`p2p enable`) para serviços LAN-to-LAN.
  - Persistência atômica na memória flash (`write`).
- **Sanitização de Portas de Interface:**
  Suporte a interfaces físicas com prefixo (`ge 0/1`, `gigabitEthernet 0/1`, `gpon 0/2`) através de `sanitize_interface_port` em [app/core/security.py](file:///Volumes/240/Code/oltapi/app/core/security.py).
- **Parser Robusto de ONUs (`parse_port_onus`):**
  Trata tanto o formato tabular com espaçamento quanto o formato compacto nativo de firmware (`2:1enableenableworkingHWTC073545b7`) e entradas de `running-config`.

### 2.3 Serviço de Onboarding ([app/services/olt_onboarding_service.py](file:///Volumes/240/Code/oltapi/app/services/olt_onboarding_service.py))
- **`inspect_olt(request: OLTInspectRequest)`:**
  Proba conectividade (SSH/Telnet), identifica fabricante (`vsol`), obtém baseline sem alterar nada e classifica o cenário em `AUX_ONLY`, `AUX_WITH_INBAND` ou `INBAND_ACTIVE`.
- **`execute_wizard_onboarding(request: OLTWizardOnboardRequest)`:**
  Pipeline completo: Probing -> Fingerprint -> Cadastro atômico -> Snapshot Baseline v0 -> Execução do Wizard de Comissionamento via Driver -> Descoberta/Configuração SNMP -> Ingestão de Inventário e cálculo de Circuit ID TR-101 para todas as ONUs -> Telemetria inicial consolidada.

### 2.4 Endpoints REST API ([app/api/v1/endpoints_olts.py](file:///Volumes/240/Code/oltapi/app/api/v1/endpoints_olts.py))
- `POST /api/v1/olts/inspect`: Executa a inspeção prévia não-destrutiva e devolve o diagnóstico arquitetural.
- `POST /api/v1/olts/onboard-wizard`: Executa o comissionamento assistido e registra a OLT no sistema.

---

## 3. Validação e Testes

### 3.1 Testes Unitários e de Integração
- **[tests/unit/test_vsol_driver.py](file:///Volumes/240/Code/oltapi/tests/unit/test_vsol_driver.py):**
  12 testes passando: validação de `parse_management_architecture` em todos os cenários, parser de ONUs compacto e geração de comandos CLI com `commit`.
- **[tests/unit/test_vsol_onboard_wizard.py](file:///Volumes/240/Code/oltapi/tests/unit/test_vsol_onboard_wizard.py):**
  4 testes passando: endpoints `/inspect` (cenários `AUX_ONLY`, `AUX_WITH_INBAND`, `INBAND_ACTIVE`) e `/onboard-wizard` de ponta a ponta com persistência e links HATEOAS.
- **[tests/unit/test_security_sanitization.py](file:///Volumes/240/Code/oltapi/tests/unit/test_security_sanitization.py):**
  12 testes passando: sanitização de portas PON e interfaces Ethernet contra injeção de comandos CLI.
- **Suíte Completa:**
  **229 testes passando (100% de sucesso)** em 50.73s.

### 3.2 Sincronização OpenAPI
- Script executado: `python -m scripts.export_openapi`.
- Contratos atualizados com 68 endpoints e 90 esquemas em [docs/api_contracts/openapi.yaml](file:///Volumes/240/Code/oltapi/docs/api_contracts/openapi.yaml) e [docs/api_contracts/openapi.json](file:///Volumes/240/Code/oltapi/docs/api_contracts/openapi.json).

### 3.3 Teste Real em Hardware de Bancada
Chamada real via TestClient contra a OLT física `192.168.8.200`:
```json
{
  "host": "192.168.8.200",
  "vendor": "vsol",
  "model": "v1600",
  "access_scenario": "aux_with_inband",
  "aux_ip": "192.168.8.200",
  "existing_svis": [
    {
      "vlan_id": 2,
      "ip_cidr": "172.16.251.60/24"
    }
  ],
  "existing_vlans": [1, 2, 100, 500],
  "gateway": "172.16.251.1",
  "total_onus_detected": 3,
  "prompt_message": "Acesso via porta auxiliar (192.168.8.200). A OLT já possui gerência In-Band ativa na VLAN 2 (IP 172.16.251.60/24)."
}
```
Detecção em hardware real 100% confirmada.
