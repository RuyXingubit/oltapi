# Plano de Implementação: Telemetria de Chassi Orientada a Objetos, SNMP e Retenção PostgreSQL com Particionamento

## 1. Visão Geral do Objetivo
Este plano endereça com rigor técnico três necessidades fundamentais da plataforma:
1. **Restauração da Orientação a Objetos (Encapsulamento & Polimorfismo):** Transferir a responsabilidade de identificação e mapeamento de interfaces físicas (`get_chassis_interfaces`) do serviço procedural para o contrato abstrato `BaseOLTDriver` e suas subclasses especializadas por fabricante (`FiberhomeTL1Driver`, `HuaweiVRPDriver`, `ZTEZXROSDriver`, etc.). Isso corrige imediatamente a discrepância de formato de portas e o cálculo do estado operacional físico (`oper_status`).
2. **Padronização Técnica de Terminologia:** Substituir em 100% do código-fonte, endpoints da API e interface gráfica os termos informais provisórios (ex: "Raio-X") pela taxonomia formal de engenharia de telecomunicações (**Telemetria & Diagnóstico de Chassi**, **Mapeamento Físico de Interfaces**, **Alocação de VLANs & Capacidade**, **Repositório de Backup & Configuração**).
3. **Módulo de Telemetria SNMP & Retenção com Devolução Real de Disco:**
   - Adicionar campos de conexão SNMP (`snmp_community`, `snmp_port`) no modelo de OLT para enriquecer a telemetria com protocolo padrão (RFC 2863 IF-MIB e RFC 1213 MIB-II).
   - Implementar tabela de histórico consolidado `chassis_telemetry_history` com **Particionamento Declarativo Mensal (`PARTITION BY RANGE`)** no PostgreSQL, permitindo que registros com mais de 90 dias (3 meses) sejam descartados via `DETACH PARTITION` e `DROP TABLE`, devolvendo os blocos físicos ao sistema operacional instantaneamente e sem fragmentação de banco.

---

## 2. Decisões Técnicas e Revisão do Usuário

> [!IMPORTANT]
> **Particionamento Declarativo PostgreSQL (`PARTITION BY RANGE`):**
> Em tabelas particionadas no PostgreSQL, a Primary Key composta obrigatória é `(id, recorded_at)`. Usaremos UUIDv7 para `id` e particionamento mensal baseado no timestamp `recorded_at`.
> O descarte da partição com mais de 90 dias via `DROP TABLE` chamará a syscall `unlink` do kernel do SO, liberando os megabytes em disco no mesmo segundo.

> [!NOTE]
> **Coleta Híbrida (SNMP + CLI/TL1):**
> Se a OLT possuir `snmp_community` configurada e responder na porta UDP 161, a telemetria física (`ifOperStatus`, `ifAdminStatus`, `sysUpTime`) é alimentada via SNMP. Caso a comunidade não esteja configurada ou o equipamento não responda via SNMP, o driver executa o fallback transparente para a sessão CLI/TL1.

---

## 3. Modificações Propostas

### Fase 1: Orientação a Objetos & Contrato Polimórfico de Drivers

#### [MODIFY] [app/drivers/base.py](file:///Volumes/240/Code/oltapi/app/drivers/base.py)
* Definir os métodos abstratos no contrato base:
  * `get_chassis_interfaces(self, olt: OLTInDB) -> List[OLTPortStatusItem]`
  * `get_chassis_uptime(self, olt: OLTInDB) -> Optional[int]` (segundos de atividade)

#### [MODIFY] [app/drivers/fiberhome/fiberhome_tl1.py](file:///Volumes/240/Code/oltapi/app/drivers/fiberhome/fiberhome_tl1.py)
* Implementar `get_chassis_interfaces(olt)`:
  * Mapeia as portas reais no padrão Fiberhome (`slot/port`, ex: `1/1`, `1/2` ou `0/1/1`);
  * Agrupa a contagem de ONUs associadas por porta usando chave canônica normalizada;
  * Define `oper_status = "up"` caso a porta esteja ativa no chassi (laser habilitado), reportando o status operacional real e a contagem de ONUs ativas.

#### [MODIFY] [app/drivers/huawei/huawei_vrp.py](file:///Volumes/240/Code/oltapi/app/drivers/huawei/huawei_vrp.py)
* Implementar `list_all_authorized_onus(olt)` e `get_chassis_interfaces(olt)`:
  * Executa comandos VRP para varredura de interfaces PON e Uplink (`display interface brief`, `display ont info summary`);
  * Mapeia `0/1/X` com estado operacional real (`UP`/`DOWN`).

#### [MODIFY] [app/drivers/zte/zte_zxros.py](file:///Volumes/240/Code/oltapi/app/drivers/zte/zte_zxros.py), [app/drivers/intelbras/intelbras_gseries.py](file:///Volumes/240/Code/oltapi/app/drivers/intelbras/intelbras_gseries.py), [app/drivers/vsol/vsol_v1600.py](file:///Volumes/240/Code/oltapi/app/drivers/vsol/vsol_v1600.py)
* Implementar `get_chassis_interfaces(olt)` específico de cada fabricante.

---

### Fase 2: Padronização de Terminologia & Refatoração do Serviço

#### [NEW] [app/services/olt_telemetry_service.py](file:///Volumes/240/Code/oltapi/app/services/olt_telemetry_service.py)
*(Substitui o antigo `olt_xray_service.py`)*
* Elimina qualquer loop forçado procedural de portas;
* Consome exclusivamente `driver.get_chassis_interfaces(olt)`;
* Agrega a telemetria física, VLANs detectadas e running-config em um objeto formal `OLTTelemetryResponse`.

#### [MODIFY] [app/routers/v1/olts.py](file:///Volumes/240/Code/oltapi/app/routers/v1/olts.py)
* Adicionar rota formal de telemetria `GET /api/v1/olts/{olt_id}/telemetry`;
* Manter redirect / alias para `GET /api/v1/olts/{olt_id}/xray` com marcação `@deprecated` no OpenAPI para compatibilidade.

#### [MODIFY] [app/static/index.html](file:///Volumes/240/Code/oltapi/app/static/index.html) e [app/static/js/app.js](file:///Volumes/240/Code/oltapi/app/static/js/app.js)
* Atualizar textos da UI:
  * "Raio-X de Chassi" ➔ **"Telemetria & Diagnóstico de Chassi"**
  * "Raio-X de Portas" ➔ **"Mapeamento Físico de Interfaces"**
  * "Raio-X de VLANs" ➔ **"Alocação de VLANs & Ocupação"**
  * "Raio-X do FTP" ➔ **"Repositório de Backup & Configuração"**

---

### Fase 3: Telemetria SNMP & Particionamento PostgreSQL (Retenção de 90 dias)

#### [MODIFY] [app/models/olt.py](file:///Volumes/240/Code/oltapi/app/models/olt.py)
* Adicionar campos opcionais:
  * `snmp_community: Optional[str] = "public"`
  * `snmp_port: Optional[int] = 161`
  * `snmp_version: Optional[str] = "v2c"`

#### [NEW] [app/services/snmp_collector.py](file:///Volumes/240/Code/oltapi/app/services/snmp_collector.py)
* Cliente SNMP assíncrono para leitura padrão:
  * `sysUpTime` (`.1.3.6.1.2.1.1.3.0`)
  * `ifTable` / `ifXTable`: `ifOperStatus`, `ifAdminStatus`, `ifInOctets`, `ifOutOctets`.

#### [NEW] [alembic/versions/add_partitioned_chassis_telemetry_history.py](file:///Volumes/240/Code/oltapi/alembic/versions/add_partitioned_chassis_telemetry_history.py)
* Migration que cria a tabela particionada:
  ```sql
  CREATE TABLE chassis_telemetry_history (
      id VARCHAR(36) NOT NULL,
      olt_id VARCHAR(36) NOT NULL REFERENCES olts(id) ON DELETE CASCADE,
      online_onus INTEGER NOT NULL DEFAULT 0,
      offline_onus INTEGER NOT NULL DEFAULT 0,
      active_ports INTEGER NOT NULL DEFAULT 0,
      uptime_seconds BIGINT,
      recorded_at TIMESTAMP WITH TIME ZONE NOT NULL,
      PRIMARY KEY (id, recorded_at)
  ) PARTITION BY RANGE (recorded_at);
  ```
* Cria as partições vigentes dos últimos 3 meses e mês atual.

#### [NEW] [app/services/telemetry_retention_service.py](file:///Volumes/240/Code/oltapi/app/services/telemetry_retention_service.py)
* Gerencia o ciclo de vida das partições:
  * Garante que a partição do mês seguinte exista antes da virada do mês;
  * Identifica partições com `recorded_at < NOW() - INTERVAL '90 days'`;
  * Executa `DETACH PARTITION` e `DROP TABLE`, liberando fisicamente o espaço em disco do servidor Linux.

---

## 4. Plano de Verificação

### Testes Automatizados
* Executar suíte de testes com `pytest`:
  * Teste unitário do polimorfismo `get_chassis_interfaces` em cada driver de vendor;
  * Teste unitário de criação e descarte de partição com devolução física (`telemetry_retention_service`);
  * Teste unitário de fallback SNMP ➔ CLI/TL1 quando SNMP indisponível;
  * Validação de UUIDv7 em novos registros de telemetria.
* Sincronização OpenAPI:
  ```bash
  python -m scripts.export_openapi
  ```

### Validação em Ambiente e Docker
* Recompilar container Docker (`docker compose up -d --build --no-deps oltapi`).
* Validar que as portas GPON no frontend exibem:
  * Estado operacional correto (`UP` / `DOWN`);
  * Quantidade real de ONUs associadas por porta;
  * Vocabulário formal e limpo (sem ocorrências de "Raio-X").
