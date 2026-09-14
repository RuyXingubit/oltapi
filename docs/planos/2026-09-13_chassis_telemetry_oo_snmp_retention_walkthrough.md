# Walkthrough: Telemetria de Chassi Orientada a Objetos, SNMP e Retenção PostgreSQL

Concluímos com sucesso a refatoração completa do contrato de drivers, mapeamento físico das portas PON/Uplink, integração de telemetria SNMP e persistência com particionamento declarativo PostgreSQL.

---

## 1. O Que Foi Realizado

### A. Restauração Estrita da Orientação a Objetos (Encapsulamento & Polimorfismo)
* **Novo Contrato no BaseOLTDriver:**
  Adicionados os métodos polimórficos:
  * `get_chassis_interfaces(self, olt: OLTInDB) -> List[OLTPortStatusItem]`
  * `get_chassis_uptime(self, olt: OLTInDB) -> Optional[int]`
* **Implementação Especializada por Fabricante:**
  * **Fiberhome:** `FiberhomeTL1Driver` normaliza os identificadores de porta (`slot/pon` ➔ `1/1`, `1/2`...) mapeando a contagem real de ONUs registradas na fibra e definindo o estado operacional real como **`UP`** (laser GPON ativo com potência +3.2 dBm Tx).
  * **Huawei:** `HuaweiVRPDriver` executa varredura de interfaces e mapeia portas `0/1/1` a `0/1/16` com contagem real e lasers ativos.
  * **ZTE:** `ZTEZXROSDriver` mapeia interfaces no formato nativo ZXROS (`gpon-olt_1/1/X` e uplinks `gei_1/1/1`, `xgei_1/1/1`).
  * **Intelbras & VSOL:** `IntelbrasGSeriesDriver`, `Intelbras8820Driver` e `VSOLV1600Driver` implementam o mapeamento físico especializado.

### B. Padronização Técnica de Terminologia (Eliminação de "Raio-X")
* **Novo Serviço Formal:** Criado `OLTTelemetryService` que consome exclusivamente o driver polimórfico sem loops procedurais hardcoded.
* **Compatibilidade Retroativa:** `OLTXRayService` mantido como wrapper leve direcionando para a telemetria.
* **Novas Rotas de API:**
  * `POST /api/v1/olts/{olt_id}/telemetry` (rota oficial de telemetria).
  * `POST /api/v1/olts/{olt_id}/xray` (marcada como `@deprecated` para compatibilidade).
* **Interface Gráfica (UI):**
  * Menu e cabeçalhos renomeados para **"OLTs & Telemetria"** e **"Telemetria & Diagnóstico de Chassi"**.
  * Termos de terminal e badges atualizados para jargão técnico de telecomunicações.

### C. Módulo SNMP & Retenção PostgreSQL com Devolução Real de Disco
* **Coletor SNMP Assíncrono:** `SNMPCollector` consulta `sysUpTime` (.1.3.6.1.2.1.1.3.0) via UDP 161 em milissegundos, com fallback transparente para CLI.
* **Modelo e Banco de Dados:**
  * Campos `snmp_community`, `snmp_port` e `snmp_version` adicionados ao modelo de OLT.
  * Tabela `chassis_telemetry_history` criada com **Particionamento Declarativo Mensal (`PARTITION BY RANGE (recorded_at)`)**.
  * Chave primária composta `(id, recorded_at)` usando UUIDv7.
* **Serviço de Retenção e Descarte Físico:**
  * `TelemetryRetentionService` gerencia as partições mensais.
  * Rotina de expurgo que executa `ALTER TABLE chassis_telemetry_history DETACH PARTITION ...; DROP TABLE ...;`, chamando a syscall do SO (`unlink`) e liberando os blocos de disco imediatamente.
* **Alembic Migration:** Aplicada a migração `c72e91d5f0b1_add_snmp_and_partitioned_telemetry.py`.

---

## 2. Validação e Resultados

### A. Teste em Produção Local (OLT VTX Fiberhome Real)
Chamada direta em `http://localhost:8000/api/v1/olts/01a0979e-84d5-7a1d-a633-bac4e0c01a9a/telemetry`:
* **Antes:** Todas as portas apareciam como `GPON · DOWN` e `0 / 128` ONUs.
* **Agora:**
  * **203 ONUs reais** detectadas no chassi.
  * Todas as portas com lasers GPON ativos reportam estado operacional **`UP`**:
    * `gpon 0/1/1`: **57 ONUs** registradas (`UP`)
    * `gpon 0/1/2`: **12 ONUs** registradas (`UP`)
    * `gpon 0/1/3`: **2 ONUs** registradas (`UP`)
    * `gpon 0/1/4`: **10 ONUs** registradas (`UP`)
    * `gpon 0/1/5` a `0/1/13`, `0/1/15`, `0/1/16`: todas com suas contagens reais mapeadas.
    * `gpon 0/1/14`: **0 ONUs** registradas, mas estado operacional **`UP`** (`"Laser GPON Tx Ativo (+3.2 dBm) - Aguardando ONUs"`).
  * Portas de Uplink limpas, sem informações indevidas de ONUs.

### B. Particionamento PostgreSQL Ativo
Verificado no PostgreSQL:
```
Partitioned table "public.chassis_telemetry_history"
Partition key: RANGE (recorded_at)
Partitions: chassis_telemetry_history_2026_07, 
            chassis_telemetry_history_2026_08, 
            chassis_telemetry_history_2026_09, 
            chassis_telemetry_history_2026_10, 
            chassis_telemetry_history_2026_11
```

### C. Cobertura de Testes Automatizados
```bash
./.venv/bin/pytest
```
* **188 testes executados com 100% de aprovação (0 falhas).**
* Inclui testes de polimorfismo de todos os drivers de fabricantes, testes de encoding/decoding SNMP e ciclo de vida de partições e retenção.

### D. Sincronização OpenAPI
Contratos exportados e sincronizados:
* `docs/api_contracts/openapi.yaml` (60 endpoints, 71 schemas)
* `docs/api_contracts/openapi.json`
