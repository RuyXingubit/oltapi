# Brainstorming: Física da Rede PON, Circuit ID (TR-101) e Ciclo de Vida Vinculado ao ERP
**Arquivo:** `v2_fisica_da_rede_circuit_id_e_erp.md`  
**Data:** 12/09/2026  
**Status:** Em debate e alinhamento com a operação real de campo

---

## 1. O Princípio da Física da Fibra Óptica (Correção de Premissa)

Em redes GPON/EPON, **não existe migração puramente por software sem evento físico**:
- A ONU é iluminada pelo laser de uma porta PON específica através de uma árvore de splitters (CTO -> CEO -> Feeder -> OLT).
- Portanto, a ONU só muda de porta PON ou de OLT quando ocorre um dos 3 eventos físicos reais:
  1. **Mudança de Endereço do Assinante:** O cliente se muda de bairro/rua, leva seu roteador/ONU antigo e o instalador espeta em uma nova CTO (que deságua em outra PON ou outra OLT).
  2. **Inversão de Fusão / Rompimento de Cabo:** Em uma manutenção de emergência na rua, a equipe técnica inverteu as fibras/tubos loose na caixa de emenda (CEO). Os clientes da PON 1 passaram a acender na PON 2 ou 3.
  3. **Manobra de POP / Troca de OLT:** O feeder inteiro de um bairro foi desconectado da OLT antiga e plugado na OLT nova.

Em todos esses casos:
- A ONU física **cai na porta/OLT antiga** (status `offline` / `dying gasp` / `LOS`).
- A mesma ONU física **acende no `autofind` da nova porta/OLT**.

---

## 2. A Tríade da Identidade: Serial, Contrato e Circuit ID

Para modelar a ONU como Objeto Orientado a Negócio no OLTAPI, precisamos correlacionar 3 pilares:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        TRÍADE DA IDENTIDADE DA ONU                     │
├────────────────────────────────────────────────────────────────────────┤
│ 1. SERIAL (Hardware Fixo):                                             │
│    - Gravado na placa de fábrica (MAC/Chipset: ex: INCL12345678)      │
│    - 100% Imutável por toda a vida útil do equipamento.               │
│                                                                        │
│ 2. CONTRATO DO ERP (Assinante / Regra de Negócio):                     │
│    - Vínculo com a pessoa: "Contrato 49102 - João Silva"               │
│    - Status no ERP: [ATIVO | SUSPENSO | CANCELADO / ESTOQUE]           │
│    - Define se a ONU em trânsito ainda é daquele cliente ou se é reuso.│
│                                                                        │
│ 3. CIRCUIT ID (TR-101 / Opção 82 DHCP):                                │
│    - Posição física na topologia de rede.                              │
│    - Padrão Broadband Forum TR-101:                                   │
│      Formato: {olt_name} eth {slot}/{port}:{onu_id}:{vlan}            │
│    - MUTÁVEL: Muda a cada manobra física, troca de PON ou troca de OLT!│
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Matriz de Decisão Operacional no OLTAPI

Quando uma ONU conhecida ou desconhecida aparece no `autofind` de uma porta PON:

```
                          [ Nova ONU Detectada no Autofind ]
                                         │
                                         ▼
                            [ Serial já é conhecido? ]
                                   │           │
                          NÃO      │           │ SIM
             ┌─────────────────────┘           └──────────────────────┐
             ▼                                                        ▼
[ Nova ONU Virgem de Fábrica ]                      [ Consultar Estado do Contrato no ERP ]
- Aguarda provisionamento manual                                      │
- Ou ativação via técnico de campo                   ┌────────────────┴────────────────┐
                                                     ▼                                 ▼
                                            [ Contrato ATIVO ]              [ Contrato CANCELADO / ESTOQUE ]
                                                     │                                 │
                                                     ▼                                 ▼
                                      [ MIGRAÇÃO / CORREÇÃO AUTOMÁTICA ]   [ REAPROVEITAMENTO DE ONU USADA ]
                                      1. Provisiona na nova PON/OLT         1. Não herda dados antigos
                                      2. Desprovisiona na PON/OLT antiga    2. Marca como equipamento livre
                                      3. Recalcula o Circuit ID (TR-101)    3. Aguarda novo contrato no ERP
                                      4. Atualiza o ERP com novo Circuit ID
```

### Cenário 1: Contrato ATIVO no ERP (Migração Real / Inversão de Fibra / Mudança de Casa)
- **O que aconteceu:** O cliente João mudou de endereço ou os técnicos inverteram as fibras da CEO na rua.
- **Detecção do OLTAPI:**
  - O serial `INCL12345678` apareceu no autofind da OLT `HUAWEI-POP-02` (porta `0/1/3`).
  - No banco do OLTAPI/ERP, esse serial tem o contrato `49102` (João), que está **ATIVO**.
- **Ação Autônoma da API:**
  1. Aceita a ONU na nova porta (`0/1/3`) aplicando a VLAN e o perfil contratados pelo João.
  2. Apaga o registro fantasma na porta antiga (`1/1` da OLT Intelbras).
  3. Gera o novo **Circuit ID TR-101**: `HUAWEI-POP-02 eth 0/1/3:1:100`.
  4. Dispara Webhook para o ERP:
     ```json
     {
       "event": "onu.circuit_migrated",
       "serial": "INCL12345678",
       "contract_id": "49102",
       "subscriber": "João Silva",
       "old_circuit_id": "ITBS-CENTRAL eth 1/1:3:100",
       "new_circuit_id": "HUAWEI-POP-02 eth 0/1/3:1:100",
       "action_taken": "provisioned_on_new_and_purged_from_old"
     }
     ```

### Cenário 2: Contrato INATIVO no ERP (Reaproveitamento de Estoque)
- **O que aconteceu:** O cliente anterior cancelou o plano há 3 meses. A ONU foi recolhida pelo técnico, revisada no laboratório e agora está sendo instalada em outro cliente completamente novo.
- **Detecção do OLTAPI:**
  - O serial `INCL12345678` apareceu no autofind.
  - O contrato antigo associado a ela está **CANCELADO / DEVOLVIDO AO ESTOQUE**.
- **Ação da API:**
  - A API **NÃO aplica** o perfil do cliente anterior nem apaga configurações ativas.
  - O serial é disponibilizado para o instalador/ERP associar ao novo contrato.
  - Receberá um novo `contract_id` e novo Circuit ID limpo.

---

## 4. Onde a Entidade ONU Deve Ser Persistida?

Atualmente no OLTAPI temos:
- `app/storage/olt_repository.py` (`data/olts.json`): Catálogo das OLTs físicas cadastradas.
- `app/storage/backup_storage.py` (`data/backups.json`): Metadados de backups.

Para tratar a ONU como Objeto Orientado a Domínio:
- Criar o **`ONURepository`** (`data/onus_inventory.json`):
  Armazena o cadastro lógico das ONUs geridas:
  ```json
  {
    "id": "0191e4f2-xxxx-7d84-xxxx-xxxxxxxxxxxx",
    "serial": "INCL12345678",
    "contract_id": "49102",
    "subscriber_name": "João da Silva",
    "vlan": 100,
    "profile": "PLAN_100M",
    "current_olt_id": "0191e4f2-51a8-7d84-a12b-3456789abcde",
    "current_port": "1/1",
    "current_onu_id": 3,
    "circuit_id": "OLT-CENTRAL eth 1/1:3:100",
    "contract_status": "ACTIVE",
    "updated_at": "2026-09-12T08:00:00Z"
  }
  ```

---

## 5. Endpoints Propostos para esta Feature

1. **`GET /api/v1/onus`**: Listar inventário consolidado de ONUs com seus respectivos contratos e Circuit IDs atuais.
2. **`GET /api/v1/onus/{serial}`**: Obter a visão unificada da ONU (independente de em qual OLT ela esteja ligada).
3. **`POST /api/v1/onus/{serial}/reconcile-migration`**:
   - Endpoint chamado pelo instalador, ERP ou pelo listener de autofind quando uma ONU ativa é espetada em uma nova PON/OLT.
   - Executa a tríade: *autoriza na nova PON -> remove da antiga -> recalcula Circuit ID*.
4. **`POST /api/v1/onus/detect-swaps`**:
   - Varredura de integridade: compara o que está cadastrado no OLTAPI vs o que está de fato online nas OLTs físicas para detectar fusões invertidas e deslocamentos físicos de clientes.
