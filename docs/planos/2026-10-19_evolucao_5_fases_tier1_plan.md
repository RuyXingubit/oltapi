# Plano Diretor Aprovado: Evolução OLTAPI em 5 Fases (Benchmark Tier-1 Global)

Este documento consolida o plano diretor de 5 fases executado para elevar o **OLTAPI** ao patamar de liderança operacional para provedores FTTH/GPON.

## Fases Executadas

1. **Fase 1 — Diagnóstico N1/N2 (`Dying Gasp` vs `LoS`) & Tabela MAC FDB por ONU:**
   - Extração e normalização da última causa de queda (`dying_gasp`, `los`, `lof`, `admin_down`, `unknown`) e horário (`last_down_time`).
   - Leitura polimórfica da tabela MAC FDB (`get_onu_mac_table`) nos drivers `FiberhomeTL1Driver`, `VSOLV1600Driver` e `ParksFiberlinkDriver`.
2. **Fase 2 — Série Temporal de Sinal Óptico (`dBm`) & Radar de Degradação:**
   - Tabela histórica `onu_optical_telemetry_history` com retenção de amostras de `rx_power_dbm`, `tx_power_dbm` e `olt_rx_power_dbm`.
   - Cálculo de deriva óptica (`drift_db = max_rx - min_rx`) e listagem proativa de ONUs degradadas (`GET /api/v1/onus/degraded`).
3. **Fase 3 — Presets Universais, Pré-Provisionamento Zero-Touch & Ações em Lote (*Batch Actions*):**
   - Templates universais em `provisioning_presets` (`GET/POST/DELETE /api/v1/presets`).
   - Pré-provisionamento de seriais em estoque (`POST /api/v1/onus/pre-provision`) com auto-ativação pelo `AutofindScannerService`.
   - Ações em lote (`POST /api/v1/onus/batch-action`) para `reboot`, `suspend`, `resume`, `change_vlan` e `deprovision`.
4. **Fase 4 — Topologia Passiva FTTH (Zonas, CTOs/ODBs & Splitters) e Mapa de Saúde:**
   - Tabelas `network_zones` e `optical_distribution_boxes` com validação anti-colisão de portas de splitter (`1:8`, `1:16`, `1:32`).
   - Mapa de Saúde (`GET /api/v1/topology/health-map`) correlacionando eventos `dying_gasp` (`power_outage`) vs `los` (`fiber_cut`) por CTO.
5. **Fase 5 — Conector ACS TR-069 / CWMP (GenieACS NBI):**
   - Tabela `acs_servers` com senhas criptografadas via Fernet AES-128-CBC + HMAC-SHA256 e proteção anti-SSRF.
   - Gerência remota de Wi-Fi 2.4GHz/5GHz, WAN PPPoE/DHCP e atualização OTA de firmware (`GET/POST /api/v1/onus/{serial}/tr069/*`).
