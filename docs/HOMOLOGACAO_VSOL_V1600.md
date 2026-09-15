# Relatório de Homologação em Hardware Físico: V-SOL V1600GT (Série V1600)

Documento oficial de consolidação técnica e operacional do comissionamento em bancada física da OLT **V-SOL V1600GT** com tráfego óptico real e provisionamento de ONUs multi-fabricante.

---

## 1. Identificação do Hardware e Ambiente de Bancada

- **Equipamento:** V-SOL V1600GT (1U, 4 Portas GPON, 4 Uplinks GE/SFP)
- **Firmware:** `V1.0.1R_250421155212`
- **Hostname:** `OLT_BANCADA_VSOL`
- **Interfaces e Conectividade:**
  - **Porta AUX/MGMT Física:** IP `192.168.8.200/24` (preservada permanentemente para emergência e bancada de técnicos).
  - **Porta Uplink `ge 0/1`:** Operando em modo híbrido com as VLANs:
    - VLAN 2 (`VLAN2_GERENCIA`): Tagged, SVI `172.16.251.60/24`, Gateway default `172.16.251.1`.
    - VLAN 100 (`INTERNET_FTTH`): Tagged.
    - VLAN 500 (`LAN_TO_LAN_P2P`): Tagged.
  - **Porta de Teste em Bancada `ge 0/4`:** Operando com PVID 100 e VLAN 100 Untagged para validação direta de notebook sem necessidade de roteador.
  - **Porta GPON `gpon 0/2`:** Ativa com Splitter 1:2 balanceado e `p2p enable` ativado (hairpin switching intra-PON).

---

## 2. Topologia Óptica & ONUs Homologadas

Dois modelos de assinante foram testados e provisionados simultaneamente na mesma porta PON:

| ONU ID | Fabricante | Modelo | Tipo | Serial | Sinal Óptico RX | Perfil Linha | Perfil Serviço | Modo Portvlan |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | **Huawei** | `EG8041X6-10` | HGU (Wi-Fi 6) | `HWTC073545b7` | `-15.32 dBm` | `line_internet` (ID 10) | `srv_hgu` (ID 10) | `portvlan veip 1 mode transparent` |
| 2 | **Intelbras** | `110GB` | SFU (Bridge) | `ITBS5f44ca50` | `-16.02 dBm` | `line_internet` (ID 10) | `srv_bridge` (ID 20) | `portvlan eth 1 mode transparent` |

---

## 3. Particularidades Críticas do Firmware V-SOL (CLI Quirks)

Durante o processo de homologação, foram catalogadas particularidades mandatórias do CLI V-SOL implementadas no driver [`app/drivers/vsol/vsol_v1600.py`](file:///Volumes/240/Code/oltapi/app/drivers/vsol/vsol_v1600.py):

1. **Autenticação em Modo Enable:**
   Ao executar o comando `enable`, o equipamento solicita explicitamente `Password:`. O driver envia a senha cadastrada antes de continuar a sessão privilegiada.
2. **Submodo Obrigatório `commit` em Perfis:**
   Diferente de outros fabricantes que aplicam parâmetros imediatamente, na V-SOL a criação ou alteração de qualquer perfil (`profile dba`, `profile line`, `profile srv`) **só é compilada e salva na memória operacional se o comando `commit` for executado antes de sair do submodo (`exit`)**.
3. **Comutação Intra-PON Hairpin (`p2p enable`):**
   Por padrão de segurança GPON, a OLT bloqueia comunicação direta entre duas ONUs da mesma porta PON. Para viabilizar circuitos LAN-to-LAN ou Rede Neutra local, o comando `p2p enable` deve ser habilitado dentro da interface `interface gpon 0/{pon}`.
4. **Sintaxe de Rotas Estáticas:**
   A rota padrão deve ser declarada como `ip route 0.0.0.0/0 <gateway>` (notação `/0` com máscara CIDR).
5. **Gravação Permanente na Flash (`write`):**
   A configuração ativa é compilada em `/mnt/config/usrcfg.conf` através do comando `write`.
6. **Desbloqueio de Firewall/ACL para SNMP (`login-access-list`):**
   De fábrica, a V-SOL bloqueia consultas SNMP externas via `login-access-list deny snmp 0.0.0.0 0.0.0.0`. O driver remove essa restrição (`no login-access-list deny snmp 0.0.0.0 0.0.0.0`), aplica permissão explícita (`login-access-list permit snmp 0.0.0.0 0.0.0.0`) e inicia o serviço com `snmp-server start` e `snmp-server enable`.
7. **Ciclo de Vida de ONUs (Sintaxe Nativa GPON):**
   - Provisionamento: `onu add <id> profile default sn <serial>` com amarração de line profile e srv profile.
   - Desprovisionamento: `no onu <id>` (remove a instância e desassocia da porta PON).
   - Ações operacionais: `onu <id> reboot`, `onu <id> disable` (suspensão) e `onu <id> enable` (reativação). Validadas com sucesso em bancada.

---

## 4. Pipeline de Onboarding em Duas Fases

O OLTAPI disponibiliza o fluxo de onboarding assistido para novos equipamentos:

### Fase 1: Pré-Inspeção Não-Destrutiva (`POST /api/v1/olts/inspect`)
- Analisa deterministicamente o `running-config` e classifica o cenário:
  - `aux_only`: OLT virgem, apenas porta AUX física ativa.
  - `aux_with_inband`: Acesso via AUX com gerência In-Band já configurada na OLT.
  - `inband_active`: Acesso direto pelo IP de produção na rede do provedor.
- Devolve orientações em linguagem natural e lista factual de SVIs, VLANs e ONUs.

### Fase 2: Comissionamento Assistido (`POST /api/v1/olts/onboard-wizard`)
- Snapshot preventivo inicial Baseline v0 com hash criptográfico SHA-256.
- Aplicação das diretrizes de gerência In-Band e catálogo de VLANs de serviço.
- Compilação dos perfis com `commit` e persistência via `write`.
- Configuração dinâmica de SNMP.
- Ingestão de portas físicas, VLANs e cálculo automático de Broadband Forum TR-101 Circuit ID para cada ONU.
- Telemetria consolidada de portas ópticas e de uplink.
