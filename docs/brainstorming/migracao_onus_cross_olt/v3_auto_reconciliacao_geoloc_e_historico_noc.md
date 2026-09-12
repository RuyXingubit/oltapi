# Brainstorming: Auto-Recuperação Reativa de Campo, Geolocalização e Histórico de NOC
**Arquivo:** `v3_auto_reconciliacao_geoloc_e_historico_noc.md`  
**Data:** 12/09/2026  
**Status:** Em debate e especificação dos requisitos finais

---

## 1. O Paradoxo Operacional: "Os Humanos Erram em Campo, o Software Não"

A realidade da fibra óptica não é de migrações previamente agendadas em laboratório. A rotina dos ISPs é viva e caótica:
- Rompimento de cabo na rodovia às 01:30 da manhã: a equipe sobe no poste no escuro, abre a CEO (caixa de emenda) e, ao fusionar 12 fibras, inverte o tubo loose verde com o azul.
- Ao religar a rede, 64 clientes que deveriam estar na PON 1 agora acendem na PON 2 da mesma OLT ou na OLT vizinha.
- Sem o OLTAPI, o NOC acordaria às 07:00 com centenas de chamados no suporte, clientes sem navegação e técnicos batendo cabeça no poste.
- **Com o OLTAPI:** A API e o ERP conversam em tempo real. Cada cliente que acende em porta trocada é identificado pelo serial, conferido se o contrato está ativo, provisionado na nova posição física, limpo da posição antiga, recebe seu novo **Circuit ID TR-101** e volta a navegar em segundos.

---

## 2. Novos Requisitos Incorporados

### 2.1 Coordenadas Geográficas Opcionais (GIS / Mapa de Rede)
Cada ONU no inventário agora suporta geolocalização:
- `latitude: Optional[float]` (ex: `-23.550520`)
- `longitude: Optional[float]` (ex: `-46.633308`)
- Permite que o ERP ou o NOC plote no mapa onde o cliente está fisicamente conectado e visualize deslocamentos geográficos (mudanças de bairro/CTO).

### 2.2 Motor de Auto-Recuperação & Reconciliação Física (`POST /api/v1/onus/reconcile-field-event`)
Fluxo quando um evento de campo ocorre:
1. **Entrada do Evento:** A OLT física (ou o instalador, ou o polling de autofind) informa:
   - `serial`: ex: `INCL12345678`
   - `detected_olt_id`: ID da OLT onde a luz acendeu
   - `detected_port`: Porta PON onde a luz acendeu (ex: `1/2`)
   - `detected_onu_id`: Opcional (se não fornecido, busca o próximo livre)
2. **Inspeção de Contrato:**
   - O OLTAPI busca o registro da ONU pelo serial.
   - Pergunta: O contrato está `ACTIVE`?
     - **Se ATIVO:** Dispara a **Auto-Recuperação**:
       a) Provisiona a ONU na `detected_olt_id` / `detected_port` usando a VLAN e o perfil do contrato.
       b) Desprovisiona a ONU da OLT e porta anteriores (onde ela ficou fantasma/offline).
       c) Recalcula o **Circuit ID TR-101** (ex: de `OLT-A eth 1/1:3:100` para `OLT-B eth 1/2:1:100`).
       d) Registra um evento imutável na linha do tempo (**Timeline / Audit Log**):
          *"Migração automática por evento de campo: movido de OLT-A 1/1 para OLT-B 1/2 devido a inversão/mudança física."*
       e) Retorna o status de sucesso com o novo Circuit ID para o ERP.
     - **Se INATIVO / CANCELADO / ESTOQUE:**
       a) Bloqueia a cópia dos dados antigos.
       b) Retorna status `IN_STOCK`: pronto para associação a um novo contrato limpo.

### 2.3 Histórico de Movimentações (Timeline / Audit Trail do NOC)
Um registro cronológico imutável de todas as manobras e auto-recuperações ocorridas na rede:
- `GET /api/v1/onus/history`: Visão consolidada de todas as migrações e movimentações de rede.
  - Filtros por data, OLT de origem/destino, porta PON ou serial.
  - Permite ao supervisor do NOC chegar de manhã e emitir o relatório:
    *"Na madrugada de 12/09, 32 ONUs foram auto-recuperadas da PON 1 para a PON 3 devido a inversão de fusão. 100% dos clientes restabelecidos automaticamente."*
- `GET /api/v1/onus/{serial}/history`: Histórico de vida daquela ONU específica (onde ela já foi instalada, por quais portas/OLTs passou e quais contratos atendeu).

---

## 3. Modelo de Dados da Linha do Tempo (`ONUMigrationHistory`)

Cada movimentação de rede gera um registro imutável:
```json
{
  "id": "0191e4f2-xxxx-7d84-xxxx-xxxxxxxxxxxx",
  "serial": "INCL12345678",
  "contract_id": "49102",
  "subscriber_name": "João da Silva",
  "timestamp": "2026-09-12T03:15:22Z",
  "reason": "field_event_auto_reconciliation",
  "from_olt_id": "0191e4f2-51a8-7d84-a12b-3456789abcde",
  "from_olt_name": "OLT-CENTRAL-ITBS",
  "from_port": "1/1",
  "from_onu_id": 3,
  "from_circuit_id": "OLT-CENTRAL-ITBS eth 1/1:3:100",
  "to_olt_id": "0191e4f2-9999-7d84-b22c-999999999999",
  "to_olt_name": "OLT-CENTRAL-HUAWEI",
  "to_port": "0/1/2",
  "to_onu_id": 1,
  "to_circuit_id": "OLT-CENTRAL-HUAWEI eth 0/1/2:1:100",
  "status": "success",
  "details": "ONU detectada em nova PON com contrato ativo. Migração e limpeza executadas com sucesso."
}
```

---

## 4. Endpoints da Arquitetura

1. **`GET /api/v1/onus`**: Inventário consolidado de ONUs com contratos, Circuit IDs e coordenadas geográficas (lat/long).
2. **`GET /api/v1/onus/{serial}`**: Visão 360º da ONU: localização física atual, status de contrato, coordenadas e atalhos HATEOAS.
3. **`POST /api/v1/onus`**: Registro/vinculação de nova ONU ao inventário (com contrato, VLAN, coordenadas).
4. **`POST /api/v1/onus/reconcile-field-event`**: Motor inteligente de auto-recuperação de campo (resolve inversões e mudanças de endereço).
5. **`GET /api/v1/onus/history`**: Linha do tempo global de manobras para o painel matinal do NOC.
6. **`GET /api/v1/onus/{serial}/history`**: Linha do tempo individual da vida daquela ONU.
