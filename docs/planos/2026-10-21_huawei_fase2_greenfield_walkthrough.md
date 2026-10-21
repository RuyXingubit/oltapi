# Walkthrough Concluído — Fase 1 (Brownfield SmartOLT) & Fase 2 (Greenfield Do Zero) na Huawei MA5800-X2

**Data:** 2026-10-21  
**Equipamento Homologado:** Huawei SmartAX MA5800-X2 (`10.200.250.10`, Telnet `23`)  
**Backup Original Salvo:** `/Users/ruy/Downloads/backup_huawei_ma5800_x2_smartolt_10.200.250.10.cfg` (`60,128 bytes`)

---

## 1. Resumo da Fase 1 (Migração Brownfield SmartOLT $\rightarrow$ OLTAPI)

1. **Reconhecimento de Configuração Legada:** `16` portas GPON + `8` Uplinks, `7` VLANs (`1, 6, 20, 202, 621, 711, 824`), `38` perfis SmartOLT, `98` ONTs multi-vendor, `100` `service-ports` e community SNMP `Yew1[qbci0kZ`.
2. **Testes Reais em Bancada (Bridge & Router):**
   - **ONU Bridge (`ITBS5F44CA50` — Intelbras `110GB`):** Descoberta, provisionamento (`Generic_1_V621`), leitura óptica (`-20.27 dBm`), troca de VLAN in-place (`621 <-> 202`) sem queda, mudança de porta (`0/1/0 <-> 0/1/5`) e desprovisionamento.
   - **ONT Router (`HWTCF052B5B1` — Huawei `EG8145X6-10`):** Descoberta, provisionamento (`SMARTOLT_FLEXIBLE_GPON` + `EG8145X6-10`), leitura óptica (`-20.55 dBm`), troca de VLAN in-place (`621 <-> 202`) sem queda, mudança de porta (`0/1/0 <-> 0/1/5`) e desprovisionamento.
3. **Simulação Real de Troca Acidental de Cabo PON (`0/1/0 -> 0/1/1`):**
   - Ambas as ONUs provisionadas na `0/1/0` tiveram o cordão óptico movido fisicamente para a `0/1/1`.
   - Detectadas como `offline (los)` na `0/1/0` e descobertas no `autofind` da `0/1/1`.
   - Movidas via `move_onu_port` para `0/1/1:62` (Router, `-20.65 dBm`) e `0/1/1:63` (Bridge, `-20.36 dBm`), subindo `online` na hora.

---

## 2. Resumo da Fase 2 (Limpeza do SmartOLT e Configuração Do Zero / Greenfield)

1. **Limpeza Cirúrgica em 5 Camadas:**
   - Removidos `102/102` `service-ports` (`undo service-port board 0/1`), `100/100` ONTs (`ont delete 0..4 all`), todos os perfis GPON/EPON/DBA/Traffic Table do SmartOLT e as VLANs de clientes (`20, 202, 621, 711, 824`), preservando apenas `VLAN 1` e a gerência In-Band `VLAN 6` (`10.200.250.10/30`).
2. **Comissionamento Do Zero (`execute_wizard_commissioning`):**
   - Criados os perfis canônicos `OLTAPI_DBA_1G` (ID `10`), `OLTAPI_1G_UP` (Index `8`), `OLTAPI_1G_DOWN` (Index `9`), `OLTAPI_ROUTER_LINE` (ID `1`), `OLTAPI_ROUTER_SRV` (ID `2`), `OLTAPI_BRIDGE_SRV_V621/202` (IDs `3, 4`) e `OLTAPI_BRIDGE_LINE_V621/202` (IDs `6, 7`), além das VLANs `621` e `202` passadas no uplink `0/4/3`.
3. **Validação Real das 2 ONUs Físicas na OLT Greenfield (`0/1/1`):**
   - **Bridge (`ITBS5F44CA50`):** Provisionada em `0/1/1:0` (`online`, `Rx ONU: -20.55 dBm`, `Tx ONU: 3.48 dBm`, `Rx OLT: -24.21 dBm`), troca de VLAN in-place (`621 -> 202 -> 621`) sem queda.
   - **Router (`HWTCF052B5B1`):** Provisionada em `0/1/1:1` (`online`, `Rx ONU: -20.81 dBm`, `Tx ONU: 2.35 dBm`, `Rx OLT: -26.03 dBm`), troca de VLAN in-place (`621 -> 202 -> 621`) sem queda.
   - **Ciclo de Vida de VLAN (`VLAN 300`):** Criada, alterada de porta de uplink e removida com sucesso.
