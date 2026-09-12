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
- [x] **Desprovisionamento & Remoção de ONU (`DELETE`):** Liberação de porta PON e ONU ID em todos os 6 fabricantes homologados.
- [x] **Ações Remotas no Assinante:** Reboot remoto OMCI, Suspensão Administrativa e Desbloqueio Financeiro (`suspend` / `resume`).
- [x] **ONU como Entidade Autônoma & Conciliação Reativa:** Rastreamento perpétuo de hardware vinculado ao contrato ERP, resolução de fusões invertidas e cutovers noturnos com Broadband Forum TR-101 Circuit ID e linha do tempo para o NOC.
- [x] **Webhooks Criptografados para ERPs (HMAC SHA-256):** Notificações push assíncronas em tempo real com controle de timeout e prevenção de timing attacks.
- [x] **Garantia de Qualidade:** 122 testes automatizados com 100% de aprovação em 3.30s.

---

## 🎯 Próximos Passos (Backlog de Evolução)

### 1. Validação Real em Bancada (Hardware Físico)
- Cadastrar a OLT física da bancada via `POST /api/v1/olts`.
- Validar a comunicação SSH em tempo real com o equipamento.
- Testar a descoberta ao vivo de ONUs conectadas na porta PON (`GET /api/v1/olts/{id}/unauthorized`).
- Confirmar compatibilidade dos parsers de sinal óptico (Rx/Tx dBm).

### 2. Worker / Scanner Periódico em Background
- Varredura programada em background (Scheduler assíncrono) para consulta periódica de autofind em todas as OLTs cadastradas.
- Acionamento automático do motor de auto-reconciliação quando novas luzes forem detectadas nas portas PON.

### 3. Persistência de Dados Relacional
- Migração opcional da persistência JSON para banco relacional:
  - **SQLite:** Para ambientes menores ou locais.
  - **PostgreSQL:** Para grandes operações com centenas de OLTs e alta concorrência.
- Integração com SQLAlchemy 2.0 / SQLModel e migrações automatizadas via Alembic.
