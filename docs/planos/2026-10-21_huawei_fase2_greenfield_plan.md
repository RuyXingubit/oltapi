# Plano Aprovado — Fase 2: Huawei MA5800-X2 Limpeza do SmartOLT e Configuração do Zero (Greenfield)

**Data:** 2026-10-21  
**Status:** Aprovado pelo usuário  
**Equipamento:** Huawei SmartAX MA5800-X2 (`10.200.250.10`, Telnet `23`)  
**Backup Original Seguro:** `/Users/ruy/Downloads/backup_huawei_ma5800_x2_smartolt_10.200.250.10.cfg`

---

## 1. Limpeza Cirúrgica da Configuração SmartOLT na `10.200.250.10`

1. **Preservação de Conectividade:** Manter intactos `vlan 6 smart`, `port vlan 6 0/4 0`, `port vlan 6 0/4 3`, `interface Vlanif6` (`10.200.250.10/30`), `interface MEth0` (`10.200.250.6/30`), `ip route-static 0.0.0.0 0.0.0.0 10.200.250.9` e usuários `root` / `smartoltuser`.
2. **Sequência em 5 Camadas:**
   - **Camada 1 (`service-ports`):** `undo service-port all`
   - **Camada 2 (`ONTs`):** `interface gpon 0/1` $\rightarrow$ `ont delete 0..4 all` + `undo shutdown 3`, `undo shutdown 4`, `port 4 range min-distance 0 max-distance 20`
   - **Camada 3 (`Perfis ONT`):** `undo ont-srvprofile gpon profile-id 1..23`, `undo ont-lineprofile gpon profile-id 1..3, 6..15`, `undo ont-lineprofile epon profile-id 4..5`, `undo ont tr069-server-profile profile-id 1`, `undo ont wan-profile profile-id 0`, `undo ont policy-route-profile profile-id 0`
   - **Camada 4 (`DBA e Traffic Tables`):** `dba-profile delete profile-id 10..14`, `undo traffic table ip index 7..12`
   - **Camada 5 (`VLANs de Clientes`):** `undo port vlan 20 0/4 3`, `undo port vlan 621 0/4 3`, `undo vlan 20`, `202`, `621`, `711`, `824`.

---

## 2. Arquitetura Canônica OLTAPI Do Zero (Greenfield)

- **Perfis Globais:** `OLTAPI_DBA_1G` (ID `10`), `OLTAPI_1G_UP` (Index `8`), `OLTAPI_1G_DOWN` (Index `9`).
- **Par Universal Router (`mode="router"`):** `OLTAPI_ROUTER_LINE` (ID `1`, `mapping-mode priority`) + `OLTAPI_ROUTER_SRV` (ID `2`, `pots adaptive 32 eth adaptive 8 catv adaptive 8`).
- **Perfis Bridge por VLAN (`mode="bridge"`):** `OLTAPI_BRIDGE_SRV_V<VLAN>` (ID `>= 3`) + `OLTAPI_BRIDGE_LINE_V<VLAN>` (ID `>= 6`).
- **Compatibilidade Híbrida:** Reconhecimento automático tanto de `OLTAPI_*` (Greenfield) quanto de `Generic_1_V*` / `SMARTOLT_FLEXIBLE_GPON` (Brownfield).

---

## 3. Validação em Bancada Pós-Comissionamento

1. Executar `execute_wizard_commissioning` na OLT limpa criando `VLAN 621` e `VLAN 202` no uplink `0/4/3`.
2. Descobrir e provisionar simultaneamente `ITBS5F44CA50` (`bridge`) e `HWTCF052B5B1` (`router`) usando os perfis `OLTAPI_*`.
3. Validar sinal óptico real (`dBm`), mudança de VLAN in-place (`621 <-> 202`), criação/exclusão de VLAN (`VLAN 300`), mudança de porta PON (`move_onu_port`) e suíte `pytest`.
