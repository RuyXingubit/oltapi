# Próximos Passos & Ciclo Operacional: Roadmap de Evolução (v1)

Este documento registra o planejamento técnico e funcional para as próximas etapas de desenvolvimento da **OLTAPI**, com foco em fechar o ciclo operacional completo de um provedor de internet (ISP) e integração com ERPs (IXC Soft, MK-Auth, Voalle, SGP, etc.).

---

## 1. Estado Atual da Solução (Baseline Entregue)

- **6 Fabricantes Homologados:**
  - **Intelbras:** 8820 / 8820i (Broadcom CLI) e Linha G (G08 / G16).
  - **Huawei:** SmartAX MA5800 e MA5600T (VRP CLI).
  - **Fiberhome:** AN5516 (01/04/06) e AN6000 (TL1 Bellcore).
  - **V-SOL:** V1600GT e série V1600G (CLI).
  - **ZTE:** C300, C320 e Titan C600 (ZXROS CLI).
- **Módulo de Disaster Recovery & Backups:** SHA-256, Unified Diff (estilo git), Auditoria de Drift e Purge automático.
- **HATEOAS Orientado a Estado & RFC 9110:** Cabeçalhos `Location` em criações (201), checagem rápida de conectividade com latência e links acionáveis contextuais.
- **Containerização Produção:** Dockerfile multi-stage Python 3.13-slim non-root (UID 1000) e Docker Compose com healthcheck nativo.
- **Qualidade & Segurança:** 89 testes unitários aprovados (100% de sucesso) em 0.15s, sanitização contra CLI Command Injection e UUIDv7.

---

## 2. Backlog de Próximos Passos

### 🎯 Fase 1: Validação Real em Bancada com Hardware Físico (V-SOL V1600GT)
- **Contexto:** Equipamento físico V-SOL V1600GT disponível na bancada.
- **Tarefas:**
  1. Subir a API via Docker (`docker compose up -d`) ou virtualenv.
  2. Cadastrar a OLT real via `POST /api/v1/olts` com credenciais de laboratório.
  3. Validar handshake SSH e diagnóstico de latência via `POST /api/v1/olts/{id}/test-connection`.
  4. Testar leitura de *running-config* real e coleta de backup com SHA-256.
  5. Plugar ONU na porta PON e testar descoberta em tempo real (`GET /api/v1/olts/{id}/unauthorized`).
  6. Refinar regexes e timeouts caso o firmware específico da bancada apresente variações de prompt.

---

### 🔌 Fase 2: Ciclo de Desprovisionamento / Remoção de ONU
- **Objetivo:** Permitir ao ERP ou técnico cancelar contratos e liberar a porta PON da OLT.
- **Endpoint Proposto:** `DELETE /api/v1/olts/{id}/onus/{serial}` ou `DELETE /api/v1/olts/{id}/ports/{port}/onus/{onu_id}`.
- **Comandos Mapeados por Fabricante:**
  - **Intelbras 8820:** `interface gpon <port>` -> `no ont add <onu_id>`
  - **Intelbras G-Series:** `interface gpon <port>` -> `no ont <onu_id>`
  - **Huawei VRP:** `interface gpon <port>` -> `ont delete <port_id> <onu_id>`
  - **Fiberhome TL1:** `DEL-ONT::DEV=...:CTAG::...`
  - **V-SOL:** `interface epon/gpon <port>` -> `no ont <onu_id>`
  - **ZTE ZXROS:** `interface gpon-olt_<port>` -> `no onu <onu_id>`
- **Testes:** Testes unitários com simulação de remoção bem-sucedida e tratamento para ONU inexistente (404).

---

### 🛠️ Fase 3: Operações Remotas de Suporte e Diagnóstico de ONU
- **Reboot Remoto da ONU:**
  - `POST /api/v1/olts/{id}/onus/{serial}/reboot`
  - Permite reiniciar o equipamento do cliente remotamente sem precisar deslocar técnico até a residência.
- **Bloqueio / Desbloqueio por Inadimplência:**
  - `POST /api/v1/olts/{id}/onus/{serial}/suspend`
  - `POST /api/v1/olts/{id}/onus/{serial}/resume`
  - Desativa temporariamente o tráfego ou altera a VLAN/profile de serviço para a página de corte do ERP.
- **Histórico e Alarmes Ópticos:**
  - Identificação de alarmes de perda de sinal (*LOS - Loss of Signal*) e falha de energia (*Dying-Gasp*).

---

### 🗄️ Fase 4: Evolução da Persistência de Dados (Banco Relacional)
- **Cenário Atual:** Persistência leve e confiável em JSON atômico protegido (`data/olts.json`).
- **Evolução:**
  - Introduzir suporte opcional a banco relacional (**SQLite** para implantações menores ou **PostgreSQL** para provedores de grande porte com centenas de OLTs).
  - Utilizar SQLAlchemy 2.0 / SQLModel com transações ACID e suporte a múltiplos workers concorrentes no Uvicorn.
  - Migrações automáticas de esquema.

---

### 🔔 Fase 5: Webhooks & Notificações de Eventos em Tempo Real
- **Objetivo:** Notificar o ERP proativamente quando uma nova ONU for detectada na fibra.
- **Mecanismo:**
  - Worker assíncrono em background executando sondagem periódica configurável (ex: a cada 60s).
  - Disparo de requisição HTTP POST (Webhook) para a URL cadastrada no ERP quando encontrar uma nova ONU desautorizada.
