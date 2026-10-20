# Walkthrough: Evolução em 5 Fases Tier-1 (OLTAPI NOC & Core)

Todas as **5 Fases** do Plano Diretor de paridade e superação operacional frente ao **Benchmark Tier-1 Global** foram implementadas de ponta a ponta (Drivers CLI/SNMP, Persistência SQLAlchemy + Alembic, Contratos OpenAPI 3.1.0, Painel NOC Flutter e Suítes Automatizadas de Testes).

---

## 1. Resumo das Entregas por Fase

### Fase 1: Diagnóstico N1/N2 (`Dying Gasp` vs `LoS`) & Tabela MAC por ONU
- **Contrato Polimórfico (`BaseOLTDriver`):** Adicionados `get_onu_mac_table()`, `normalize_down_cause()` e `format_canonical_mac()` em `app/drivers/base.py`, com implementação real nos 3 drivers homologados (`vsol_v1600.py`, `fiberhome_tl1.py` e `parks_fiberlink.py`).
- **Endpoint REST:** `GET /api/v1/olts/{olt_id}/onus/{serial_or_id}/mac-table` e enriquecimento automático de `GET /api/v1/olts/{olt_id}/onus/{serial_or_id}` com `last_down_cause`, `last_down_time` e `mac_table`.
- **Frontend NOC:** Badges semânticos (`⚡ Queda Elétrica (Dying Gasp)` vs `✂️ Rompimento Óptico (LoS)`) na listagem de ONUs e tabela MAC aprendida no diálogo `onu_detail_dialog.dart`.

### Fase 2: Séries Temporais de Sinal Óptico (`dBm`) & Radar de Degradação
- **Persistência Histórica:** Nova tabela `onu_optical_telemetry_history` (`ONUOpticalTelemetryHistoryModel` em `app/db/models.py`) e cache instantâneo de `last_rx_power_dbm`, `last_tx_power_dbm`, `last_olt_rx_power_dbm`, `last_down_cause` em `onus_inventory`.
- **Detecção de Deriva Óptica (`drift_db`):** Cálculo automático de mínimo, máximo, média e variação de atenuação (`max_rx - min_rx >= 3.0 dB` ou `rx <= -27.0 dBm`).
- **Endpoints REST:**
  - `GET /api/v1/onus/{serial}/optical-history`
  - `GET /api/v1/onus/degraded`
  - `POST /api/v1/olts/{olt_id}/collect-optical-telemetry`

### Fase 3: Presets Universais, Pré-Provisionamento Zero-Touch & Ações em Lote (*Batch Actions*)
- **Presets Universais (`provisioning_presets`):** Templates multi-vendor reutilizáveis (`GET/POST/DELETE /api/v1/presets`) integrados ao modal `authorize_onu_dialog.dart` para preenchimento em 1 clique.
- **Pré-Provisionamento (`PRE_PROVISIONED`):** Cadastro antecipado de seriais em estoque (`POST /api/v1/onus/pre-provision`) com ativação automática pelo `AutofindScannerService` assim que a ONU acende fisicamente em qualquer porta PON.
- **Operações em Lote (`POST /api/v1/onus/batch-action`):** Seleção múltipla em `configured_screen.dart` para `reboot`, `suspend`, `resume`, `change_vlan` e `deprovision`.

### Fase 4: Topologia Passiva FTTH (Zonas, CTOs/ODBs & Splitters) e Mapa de Saúde
- **Modelagem FTTH (`network_zones` e `optical_distribution_boxes`):** Cadastro de zonas/bairros e Caixas de Atendimento Óptico (`CTO/ODB`) com validação anti-colisão de portas do splitter (`1:8`, `1:16`, `1:32`).
- **Correlação Inteligente de Quedas (`GET /api/v1/topology/health-map`):** Diferenciação automática na CTO entre **Queda de Energia Regional (`power_outage`)** quando múltiplas ONUs da mesma caixa reportam `dying_gasp` e **Rompimento de Fibra (`fiber_cut`)** quando reportam `los`.

### Fase 5: Gerência Remota de CPE via Conector TR-069 / CWMP (GenieACS NBI)
- **Segurança & Criptografia (`acs_servers`):** Credenciais NBI criptografadas em repouso via **Fernet AES-128-CBC + HMAC-SHA256** e validação anti-SSRF em `app/services/acs_service.py`.
- **Gerência Remota 1-Clique:** Leitura de resumo TR-069 (`GET /api/v1/onus/{serial}/tr069`), alteração de SSID/Senha Wi-Fi 2.4GHz e 5GHz (`POST /api/v1/onus/{serial}/tr069/wifi`), configuração WAN PPPoE/DHCP (`POST /api/v1/onus/{serial}/tr069/wan`) e disparo de firmware OTA (`POST /api/v1/onus/{serial}/tr069/firmware`).

---

## 2. Validação e Testes Executados

- **Sincronização OpenAPI 3.1.0 (`python -m scripts.export_openapi`):** `96 endpoints e 123 esquemas` exportados em `docs/api_contracts/openapi.yaml` e `docs/api_contracts/openapi.json`.
- **Testes Unitários e de Conformidade Backend (`pytest`):** `261 passed` (incluindo `test_driver_compliance.py` e `test_tier1_phases_1_to_5.py`).
- **Análise Estática e Testes Frontend Flutter (`flutter analyze && flutter test`):** `0 issues` e `22 passed`.
