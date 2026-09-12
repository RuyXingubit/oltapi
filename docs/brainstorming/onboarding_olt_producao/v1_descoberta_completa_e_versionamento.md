# Brainstorming: Onboarding de OLT em Produção (Brownfield), Descoberta Global e Versionamento Contínuo

## 1. Contexto do Mundo Real (Brownfield Deployment)
Provedores de Internet (ISPs) raramente começam do zero com uma OLT virgem (Greenfield). Na esmagadora maioria dos casos:
- A OLT já está em produção no POP há meses ou anos.
- Já possui centenas ou milhares de clientes GPON ativos navegando.
- Possui dezenas de VLANs (SVLAN, CVLAN, VLAN de Gerência, VLAN de Voz, VLAN de IPTV).
- Possui perfis de banda (Line Profiles, DBA Profiles, Traffic Profiles).
- O operador **NÃO PODE** correr o menor risco de sobrescrever, desconfigurar ou derrubar clientes existentes.

---

## 2. Diagnóstico: O que o OLTAPI tem hoje vs O que precisamos para esse cenário

### O que já temos implementado:
1. **Backup e Running-Config:** `GET /olts/{id}/config` e `POST /olts/{id}/backups` com identificador UUIDv7 e hash SHA-256.
2. **Detecção de Drift e Comparador de Backups:** `GET /olts/{id}/backups/compare` gerando diff linha a linha.
3. **Leitura de ONUs por Porta Pontual:** `GET /olts/{id}/ports/{port}/onus` consulta as ONUs ativas de uma porta específica.
4. **Persistência Relacional com PostgreSQL:** Banco de dados ACID pronto para armazenar milhares de ONUs e histórico de alterações.

### O que NÃO temos ainda (A Lacuna para OLTs em Produção):
1. **Varredura e Descoberta Global da OLT (Bulk Ingestion / Onboarding Sync):**
   - Atualmente não há um endpoint único (ex: `POST /api/v1/olts/{id}/sync`) que varra todas as portas e slots da OLT e importe todas as ONUs já provisionadas para o banco de dados do OLTAPI de uma só vez.
   - Hoje o operador teria que cadastrar ONU por ONU ou consultar porta por porta.
2. **Mapeamento Automático de VLANs Existentes na OLT:**
   - Ler as VLANs configuradas na OLT para que, ao provisionar um novo cliente, o sistema saiba quais VLANs são válidas naquele equipamento.
3. **Snapshot Automático Pré e Pós Alteração (Config Revision Tracking):**
   - Hoje o backup é disparado manualmente ou via rotina em lote.
   - Não temos ainda uma regra de: *"Sempre que provisionar ou desprovisionar uma ONU, tirar um snapshot antes e salvar o running-config após a mudança com commit/write na OLT"*.

---

## 3. Arquitetura Proposta para o "Onboarding Seguro de OLT em Produção"

### Etapa 1: Snapshot de Baseline Zero (Backup Inicial Obrigatório)
- Antes de qualquer leitura pesada ou comando, o sistema gera o **Backup de Baseline v0** da OLT.
- Registrado no PostgreSQL com SHA-256 e UUIDv7.

### Etapa 2: Varredura Completa de Inventário (Full Discovery Sync)
- Comando no driver:
  - **Fiberhome (TL1):** Consulta em lote via TL1 de todas as ONUs cadastradas no chassi (`LST-OMDD`, `LST-ONT` ou leitura iterativa por slot/porta).
  - **Intelbras / Huawei / ZTE / V-SOL:** Leitura de tabela global de ONUs autorizadas (ex: `display ont info summary`, `show gpon onu state`, etc.).
- Ingestão no PostgreSQL:
  - Cada ONU encontrada é inserida no inventário (`onus_inventory`) com status `ACTIVE` ou `DISCOVERED`.
  - Registra: Serial, Slot, Porta PON, ONU ID, Descrição/Nome original, VLAN atual, Profile atual e calcula o Circuit ID TR-101.

### Etapa 3: Política de Versionamento Contínuo (Continuous Configuration Versioning)
- **Modo Seguro (Safe Mode):**
  - Toda ação de escrita (`provision`, `deprovision`, `suspend`, `resume`) executa:
    1. Gravação do comando no log de auditoria com autor e timestamp.
    2. Execução segura na OLT.
    3. Persistência na OLT (`write` / `save` / commit TL1).
    4. Geração automática de novo backup pós-alteração com detecção de diff imediata.

---

## 4. Recomendações e Próximos Passos
Antes de plugar a Fiberhome física real:
1. Criar o endpoint de **Full Discovery / Ingestão de OLT** (`POST /api/v1/olts/{id}/sync`).
2. Testar o parser de leitura global de ONUs da Fiberhome TL1 para garantir que ele lê 100% dos dados sem travar o processador da OLT.
3. Implementar a política de snapshot/backup automático por alteração.
