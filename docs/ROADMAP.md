# 🗺️ Roadmap de Evolução - OLTAPI

Este documento consolida as metas alcançadas e os próximos passos planejados para o **OLTAPI**, orientados às necessidades práticas de provedores de internet (ISPs) e integração com ERPs (IXC, MK-Auth, Voalle, SGP, etc.).

---

## 🏁 Entregas Realizadas (Milestones Concluídos)

- [x] **Arquitetura Base & Driver Pattern:** Estrutura modular desacoplada com `BaseOLTDriver` e `DriverFactory`.
- [x] **Segurança e Sanitização:** Sanitização rigorosa contra injeção de comandos CLI, validação de `X-API-Key` em tempo constante e identificadores no padrão **UUIDv7 (RFC 9562)**.
- [x] **6 Fabricantes Homologados:**
  - Intelbras 8820 / 8820i (CLI)
  - Intelbras Concentradores G08 e G16 (CLI)
  - Huawei SmartAX MA5800 e MA5600T (VRP CLI)
  - Fiberhome AN5516 e AN6000 (TL1 Bellcore)
  - V-SOL V1600GT e Série V1600G (CLI)
  - ZTE C300, C320 e Titan C600 (ZXROS CLI)
- [x] **Módulo de Disaster Recovery & Backups:** Coleta automatizada, cálculo de hash criptográfico SHA-256, comparador de unified diff (estilo git), auditoria de integridade de disco e políticas de expurgo/retenção (purge).
- [x] **Assistente de Bootstrap Zero-Touch:** Geração de scripts recomendados pelos fabricantes para inicialização de OLTs virgens com suporte a VLAN única ou VLAN por porta PON.
- [x] **Hipermídia HATEOAS & RFC 9110:** Cabeçalhos `Location` em respostas `201 Created`, fluxos guiados por status de conexão (`online` vs `unreachable`), testes de conectividade TCP sob demanda e links contextuais enxutos com paths relativos.
- [x] **Containerização para Produção:** Dockerfile multi-stage enxuto (Python 3.13-slim non-root UID 1000) e Docker Compose com persistência de volumes, rotação de logs e healthcheck nativo.
- [x] **Garantia de Qualidade:** 89 testes automatizados com 100% de aprovação em 0.15s.

---

## 🎯 Próximos Passos (Backlog de Evolução)

### 1. Validação Real em Bancada (Hardware V-SOL V1600GT)
- Cadastrar a OLT física da bancada via `POST /api/v1/olts`.
- Validar a comunicação SSH em tempo real com o equipamento.
- Testar a descoberta ao vivo de ONUs conectadas na porta PON (`GET /api/v1/olts/{id}/unauthorized`).
- Confirmar compatibilidade dos parsers de sinal óptico (Rx/Tx dBm).

### 2. Desprovisionamento / Remoção de ONU (`DELETE`)
- Endpoint: `DELETE /api/v1/olts/{id}/onus/{serial}` (ou por porta/id).
- Implementação dos comandos de liberação de porta PON nos drivers:
  - Intelbras: `no ont add <onu_id>`
  - Huawei: `ont delete <port> <onu_id>`
  - Fiberhome: `DEL-ONT::...`
  - V-SOL: `no ont <onu_id>`
  - ZTE: `no onu <onu_id>`
- Testes unitários com simulação de exclusão e validação de 404 para ONUs inexistentes.

### 3. Ações Operacionais Remotas no Assinante
- **Reboot Remoto:** `POST /api/v1/olts/{id}/onus/{serial}/reboot` para reinicialização suave da ONU sem visita técnica.
- **Suspensão Financeira:** `POST /api/v1/olts/{id}/onus/{serial}/suspend` e `resume` para bloqueio e desbloqueio por inadimplência.
- **Diagnóstico de Alarmes:** Detecção e alerta para eventos de fibra rompida (LOS) e falta de energia no cliente (Dying-Gasp).

### 4. Persistência de Dados Relacional
- Migração opcional da persistência JSON (`data/olts.json`) para banco relacional:
  - **SQLite:** Para ambientes menores ou locais.
  - **PostgreSQL:** Para grandes operações com centenas de OLTs e alta concorrência.
- Integração com SQLAlchemy 2.0 / SQLModel e migrações automatizadas.

### 5. Webhooks & Notificações de Eventos
- Notificação push para o ERP quando uma nova ONU for detectada na fibra (worker em background).
- Notificações de alteração não autorizada no *running-config* da OLT (detecção de drift).
