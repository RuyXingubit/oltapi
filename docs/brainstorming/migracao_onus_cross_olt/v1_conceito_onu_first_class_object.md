# Brainstorming: ONU como Entidade Autônoma & Motor de Migração Cross-OLT / Cross-POP
**Arquivo:** `v1_conceito_onu_first_class_object.md`  
**Data:** 12/09/2026  
**Status:** Em debate e concepção técnica

---

## 1. O Problema Histórico no Setor de Telecomunicações / ISPs

Na arquitetura tradicional da maioria dos softwares de mercado (ERPs como IXC, MK-Auth, Voalle, e NMS de fabricantes):
- A ONU é tratada como um mero **filho estático de uma porta física**: ela só existe dentro do contexto `OLT -> Placa/Slot -> Porta PON -> ONU ID`.
- Se o provedor faz uma **manobra de rede**, expansão de POP, substituição de equipamento (ex: trocando uma OLT de 8 portas por uma de 16, ou trocando de fabricante Intelbras -> Huawei):
  1. Todos os clientes caem com status `LOS` (Loss of Signal) ou `Offline`.
  2. Na nova OLT, dezenas ou centenas de ONUs aparecem como "anônimas" na lista de `autofind` / não autorizadas.
  3. O técnico ou operador de NOC precisa deletar manualmente cada cliente da OLT antiga e re-provisionar um por um na nova OLT, conferindo VLANs, planos de velocidade e contratos.
  4. Qualquer erro resulta em cliente sem conexão, VLAN trocada, descompasso no ERP e horas de trabalho manual sob estresse.

---

## 2. A Visão Inovadora: ONU como Objeto de Domínio de Primeira Classe (First-Class Citizen)

Em vez de a ONU pertencer estaticamente a uma OLT, **a ONU é uma Entidade de Negócio com Identidade Própria**:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   ONU / ASSINANTE (Objeto de Domínio)                  │
│  - ID: UUIDv7                                                          │
│  - Serial: INCL12345678 / HWTC88776655                                 │
│  - Assinante: "João da Silva - Contrato 49102"                         │
│  - Perfil Lógico: "PLAN_100M_ROUTER"                                   │
│  - VLAN de Serviço: 100                                                │
│  - Estado de Ciclo de Vida: [Provisionada | Migrando | Suspensa]       │
│                                                                        │
│  Attachment Atual (Onde ela está agora):                               │
│    -> OLT Origem: 0191e4f2-51a8-7d84-a12b-3456789abcde (Intelbras 8820)│
│    -> Porta: 1/1, ONU ID: 3                                            │
│                                                                        │
│  Target Planejado (Para onde ela vai na manobra):                      │
│    -> OLT Destino: 0191e4f2-9999-7d84-b22c-999999999999 (Huawei MA5800)│
│    -> Porta: 0/2/1, ONU ID: auto                                       │
└────────────────────────────────────────────────────────────────────────┘
```

A OLT é apenas o **Host de Fixação (Ponto de Ancoragem / Access Point)**. A inteligência, os atributos e o estado pertencem ao objeto ONU.

---

## 3. Os Dois Cenários de Migração

### Cenário A: Migração Intra-OLT (Entre Portas PON da mesma OLT)
- **Motivo:** Balanceamento de tráfego, saturação de uma porta PON específica, splitagem de rede (CTO dividida em duas).
- **Operação:**
  1. OLTAPI desprovisiona a ONU da porta antiga `1/1`.
  2. Provisiona imediatamente na nova porta `1/2` preservando o mesmo serial, VLAN, perfil e descrição.
  3. Atualiza os links HATEOAS da ONU.

### Cenário B: Migração Inter-OLT / Cross-POP (Inédita no Setor)
- **Motivo:** Upgrade de POP, troca de chassi/marca (ex: Intelbras -> Huawei), migração física de rotas de fibra para nova OLT.
- **Modos de Execução:**

#### Modo B.1: Migração Ativa / Transacional Imediata (Cutover Online)
Quando ambas as OLTs estão ligadas na rede de gerência e o operador/técnico está realizando a troca naquele instante:
1. **Pre-flight Check:**
   - Verifica se a OLT Destino está online (`test-connection`).
   - Valida se a porta de destino possui slot livre (`onu_id`).
   - Verifica compatibilidade de VLAN e perfil na OLT destino.
2. **Desativação Limpa:**
   - Executa `deprovision_onu` na OLT Origem (libera recursos e memória da OLT antiga).
3. **Ativação no Destino:**
   - Executa `provision_onu` na OLT Destino com os mesmos parâmetros lógicos, traduzidos para o dialeto do novo fabricante.
4. **Relatório & HATEOAS:**
   - Retorna o status de sucesso com link para a nova localização da ONU.
   - Caso falhe no destino, executa política de compensação (rollback).

#### Modo B.2: Migração Planejada / Assistida por Janela de Manobra (Aguardando Autofind)
Imagine que o provedor vai trocar a OLT de madrugada (janela de manutenção):
1. O engenheiro cadastra a intenção de migração:
   `POST /api/v1/onus/migrations`
   (Origem: OLT-ANTIGA-ITBS -> Destino: OLT-NOVA-HUAWEI).
2. O sistema marca as ONUs como `MIGRATION_PENDING`.
3. O técnico desliga a fibra da OLT antiga e espeta na OLT nova.
4. Conforme as ONUs sobem na OLT nova, o serviço de escuta/descoberta (`Autofind Reconciliation Worker`) reconhece:
   *"Opa! O serial INCL12345678 apareceu na porta 0/1/2 da OLT Huawei. Esse serial está agendado para migração do contrato do João!"*
5. O OLTAPI **provisiona automaticamente a ONU no destino com as exatas credenciais do João**, e emite webhook para o ERP informando:
   `"Assinante João migrado com sucesso da OLT A para OLT B sem intervenção humana!"`

---

## 4. O Desafio Cross-Vendor: Abstração de Perfis

Como traduzir configurações entre fabricantes distintos?
- Na **Intelbras 8820**: `interface gpon-onu_1/1:1`, `vlan 100`.
- Na **Huawei**: `interface gpon 0/1`, `ont add ... ont-lineprofile-name "PLAN_100M"`, `service-port vlan 100 ...`.
- Na **Fiberhome**: `ADD-ONU ... LINEPROF="PLAN_100M"`, `CFG-LANPORTVLAN ...`.

**Solução Elegante:** O conceito de **Profile Mapping Lógico**:
Um perfil genérico (`ROUTER_PADRAO_VLAN`) que cada driver sabe converter para os comandos nativos da sua plataforma.

---

## 5. Próximos Passos de Modelagem para Debate
1. Como estruturar o repositório de persistência das ONUs como entidades permanentes?
2. Como projetar o endpoint de migração:
   - `POST /api/v1/olts/{source_olt_id}/onus/{serial}/migrate` ?
   - ou um recurso de nível superior `/api/v1/onus/{serial}/migrate` ?
3. Como lidar com rollback em caso de falha física?
