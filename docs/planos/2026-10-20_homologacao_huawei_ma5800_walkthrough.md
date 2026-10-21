# Walkthrough — Homologação Huawei SmartAX MA5800-X2 (Fase 1 Completa + ONU Física Validada)

- **Data:** 21/10/2026
- **Equipamento:** `Huawei SmartAX MA5800-X2` (`10.200.250.10`)
- **Backup Externo:** `/Users/ruy/Downloads/backup_huawei_ma5800_x2_smartolt_10.200.250.10.cfg`
- **ONU Física Validada:** Intelbras `110GB` (`ITBS5F44CA50`) na porta `0/1/0`

## Resultados Reais na ONU Física (`ITBS5F44CA50`)

1. **Descoberta (`list_unauthorized_onus`):** Detectada em `0/1/0` (`ITBS5F44CA50`, `110GB`).
2. **Provisionamento (`provision_onu`):** Porta `0/1/0`, `ONT-ID 0`, `VLAN 621`.
3. **Leitura de Sinal Óptico Real (`get_onu_details`):** `status='online'`, **Rx ONU: `-20.27 dBm`**, **Tx ONU: `3.52 dBm`**, **Rx OLT: `-23.80 dBm`**.
4. **Mudança de VLAN In-Place (`change_onu_vlan`: `621 -> 202`):** Executado via `ont modify` sem queda do link GPON (`status='online'`, `vlan=202`, `Rx: -20.27 dBm`).
5. **Mudança de Porta (`move_onu_port`: `0/1/0 -> 0/1/5 -> 0/1/0`):** Movida para `0/1/5:0` e retornada para `0/1/0:0` (`VLAN 621`, `status='online'`, `Rx: -20.31 dBm`).
6. **Desprovisionamento (`deprovision_onu`):** Removida com sucesso, retornando imediatamente para o `autofind` na porta `0/1/0`.
