# Documentação Oficial de Homologação Física — Huawei SmartAX MA5800-X2 (`MA5800V100R021`)

**Data de Homologação:** 2026-10-21  
**Equipamento Físico de Bancada:** Huawei SmartAX MA5800-X2 (`10.200.250.10`, Firmware `MA5800V100R021C00SPH305`)  
**Placas Instaladas:** `0/0 H901PISA` (Power), `0/1 H901GPHF` (16 portas GPON `0/1/0..15`), `0/2 H902FMSA` (FAN), `0/3 H901MPSG` (Standby MPU), `0/4 H901MPSG` (Active MPU, 2x 10GE + 2x GE Uplink)  
**ONUs Físicas Homologadas:**
1. **Bridge (SFU):** Intelbras `110GB` (`ITBS5F44CA50` / Hex `495442535F44CA50`)
2. **Router (HGU Wi-Fi 6):** Huawei `EG8145X6-10` (`HWTCF052B5B1` / Hex `48575443F052B5B1`)

---

## 1. Arquitetura Dual Suportada pelo `HuaweiVRPDriver`

O driver [`HuaweiVRPDriver`](file:///Volumes/240/Code/oltapi/app/drivers/huawei/huawei_vrp.py) suporta nativamente os dois cenários operacionais de provedores ISP:

### 1.1 Fase 1 — Migração de Gerenciador (Brownfield SmartOLT $\rightarrow$ OLTAPI)
Quando uma OLT Huawei vem de produção gerenciada pelo SmartOLT:
- **Reconhecimento Integral Sem Perda:** Lê placas, portas GPON e de Uplink, VLANs `smart` e bindings `port vlan <VID> 0/<S> <P>`, perfis legados (`Generic_1_V<VLAN>`, `SMARTOLT_FLEXIBLE_GPON`, `EG8145X6-10`, `SMARTOLT_DEFAULT_TCONT_1G`, `SMARTOLT-1G-UP/DOWN`), todas as ONTs multi-vendor (`HWTC`, `ITBS`, `FHTT`, `PRKS`, `ZTEG`, `ALCL`) e todos os `service-ports`.
- **Extração de Comunidade SNMP Criptografada:** Descobre a community em texto plano via `display snmp-agent community read` mesmo quando o `running-config` exibe `cipher`.
- **Reuso Inteligente de Perfis:** Ao provisionar ou trocar a VLAN de uma ONT em uma caixa vinda do SmartOLT, reutiliza automaticamente `Generic_1_V<VLAN>` para Bridge e `SMARTOLT_FLEXIBLE_GPON` + `EG8145X6-10` para Router.

### 1.2 Fase 2 — Configuração Do Zero (Greenfield Zero-Touch OLTAPI)
Quando uma OLT Huawei é limpa ou tirada da caixa e comissionada via `execute_wizard_commissioning`:
- **Perfis Globais de Banda (1 Gbps):**
  - `dba-profile add profile-id 10 profile-name "OLTAPI_DBA_1G" type4 max 1048000`
  - `traffic table ip index 8 name "OLTAPI_1G_UP" cir 1048064 ...`
  - `traffic table ip index 9 name "OLTAPI_1G_DOWN" cir 1048064 ...`
- **Par Universal para ONTs em Modo Router / HGU (Qualquer Marca e Qualquer VLAN):**
  - `OLTAPI_ROUTER_LINE` (ID `1`, `mapping-mode priority`, `gem mapping 1 1 priority 0` e `priority 7`)
  - `OLTAPI_ROUTER_SRV` (ID `2`, `ont-port pots adaptive 32 eth adaptive 8 catv adaptive 8`, sem `port vlan translation`)
- **Perfis Bridge por VLAN de Serviço:**
  - `OLTAPI_BRIDGE_SRV_V<VLAN>` (ID `>= 3`, `port vlan eth 1..4 translation <VLAN> user-vlan <VLAN>`)
  - `OLTAPI_BRIDGE_LINE_V<VLAN>` (ID `>= 6`, `gem mapping 1 1 vlan <VLAN>`)

---

## 2. Descobertas Críticas de Hardware na Bancada

1. **Troca de VLAN In-Place com Zero Queda Óptica (`ont modify`):**
   - Em vez de desprovisionar e reprovisionar a ONT (`ont delete` + `ont add`), `change_onu_vlan` executa `undo service-port port 0/<S>/<P> ont <ID>`, `ont modify <P> <ID> ont-lineprofile-id <LP> ont-srvprofile-id <SP>`, `ont port native-vlan` (em modo Bridge) e recria o `service-port`, mantendo o link GPON `online` com `0s` de queda.
2. **Detecção no `autofind` após Troca Física de Porta PON:**
   - Quando o cordão óptico é movido fisicamente de uma porta PON (ex: `0/1/0`) para outra (ex: `0/1/1`), a Huawei MA5800 marca o registro antigo como `offline` (`last_down_cause: 'los'`) e **lista imediatamente a ONT no `display ont autofind all` da nova porta (`0/1/1`)**. O método `move_onu_port` remove o registro da porta antiga antes de registrar na nova porta, alocando automaticamente o próximo `ONT-ID` livre.
3. **Limpeza em Massa de `service-ports` por Placa (`undo service-port board 0/1`):**
   - No VRP `MA5800V100R021`, a exclusão em lote de todos os fluxos de uma placa GPON utiliza `undo service-port board 0/<S>` com confirmação `(y/n)`.
4. **Prevenção de Reset de Sessão Telnet e Lock de Flash Dual-MPU:**
   - Reexecutar `sysman server source telnet any-interface` dentro de uma sessão Telnet ativa reinicia o daemon Telnet da MA5800 e derruba o socket TCP atual; o comissionamento habilita apenas os protocolos complementares.
   - Com `autosave interval configuration 60` ativo, operações rápidas de ONU não invocam `save` síncrono a cada chamada, evitando o bloqueio de ~15s de duplicação de flash entre as MPUs Active/Standby (`0/4` e `0/3`).
