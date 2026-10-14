# 🗺️ Roadmap de Evolução - OLTAPI

Este documento consolida os marcos alcançados e as ondas de evolução planejadas para o **OLTAPI**, alinhados ao [System Design & Specification Document (`docs/SDD.md`)](SDD.md) e orientados às necessidades reais de provedores de internet (ISPs), operadores de Rede Neutra e integração com ERPs (IXC Soft, MK-Auth, Voalle, SGP, etc.).

---

## 🏁 Entregas Realizadas (Milestones Concluídos)

- [x] **Especificação SDD & Governança API-First:** Documento mestre [`docs/SDD.md`](SDD.md) e contrato OpenAPI 3.1.0 (`75 rotas`, `96 operações HTTP`, `96 schemas`) sincronizados automaticamente via `scripts/export_openapi.py`.
- [x] **Arquitetura Ports & Adapters com Registro Dinâmico:** Estrutura desacoplada com [`BaseOLTDriver`](file:///Volumes/240/Code/oltapi/app/drivers/base.py), [`DriverRegistry`](file:///Volumes/240/Code/oltapi/app/drivers/registry.py) (`@DriverRegistry.register`) e suíte obrigatória [`BaseDriverComplianceTest`](file:///Volumes/240/Code/oltapi/tests/unit/test_driver_compliance.py), com proibição estrita de drivers teóricos sem bancada física.
- [x] **3 Fabricantes 100% Homologados em Hardware Físico de Bancada:**
  - **Fiberhome AN5516-01 / AN6000 (Telnet CLI + TL1 Bellcore):** Handshake TCP, leitura de VLANs, perfis, 561 ONUs ativas, `running-config`, backups via FTP remoto, telemetria SNMP nativa (`cd service`), diagnóstico óptico duplo (ONU RX e OLT RX) e ciclo de vida completo (Router PPPoE, Bridge e VEIP).
  - **V-SOL V1600GT / Série V1600G (SSH / Telnet CLI):** Comissionamento completo em hardware real (firmware `V1.0.1R_250421155212`), detecção determinística `interface aux` vs SVI In-Band, VLANs híbridas, `p2p enable` intra-PON, compilação de perfis com submodo `commit`, persistência na flash (`write`) e provisionamento de ONUs Huawei Wi-Fi 6 HGU VEIP e Intelbras SFU Bridge ([Relatório de Homologação](HOMOLOGACAO_VSOL_V1600.md)).
  - **Parks Fiberlink 10008S / Série 21000 (Telnet CLI):** Homologação em hardware real (firmware `4.9.3`), contorno de segfault no Dropbear SSH via Telnet RFC 854 com handshake `<RETURN>` e `terminal length 0`, provisionamento multi-vendor com `ethernet-profile auto-on uni-port 1-4`, bloqueio por `gpon blacklist`, telemetria dupla (`status` + `rssi`) e backup FTP com fallback via terminal ([Relatório de Homologação](HOMOLOGACAO_PARKS_FIBERLINK.md)).
- [x] **Segurança, Criptografia Fernet & RBAC Multi-Tenant (Rede Neutra):** Sanitização rigorosa contra CLI Command Injection, proteção SSRF em Webhooks, identificadores **UUIDv7 (RFC 9562)**, criptografia Fernet AES em repouso (OLTs, FTP, SNMP e Webhooks), autenticação JWT Bearer + API Keys SHA-256 com validação de subconjunto de escopos (`enforce_scope`) e isolamento por OLT e VLAN (`enforce_olt` / `enforce_vlan`).
- [x] **Módulo de Disaster Recovery & Backups Multi-FTP:** Coleta automatizada com prioridade de upload FTP nativo da OLT e fallback via terminal, cálculo de hash SHA-256, comparador unified diff, auditoria de integridade e políticas de expurgo/retenção (`purge`).
- [x] **Onboarding Assistido em 2 Fases (Wizard Zero-Touch) & Stream SSE:** Pré-inspeção não-destrutiva (`inspect`), comissionamento guiado (`onboard-wizard`), geração de Baseline v0 obrigatório e acompanhamento em tempo real via Server-Sent Events (`onboard/stream`).
- [x] **Políticas PON & Modo Cutover Zero-Touch:** Pré-preenchimento inteligente de VLAN e Profile por porta PON (`pon-policies`) e janelas temporizadas de auto-provisionamento em lote para manobras de migração (`auto-provision-tasks`).
- [x] **Ciclo de Vida Completo de ONUs & Auto-Recuperação Reativa (TR-101):** Provisionamento dinâmico validado por schema de hardware, Reboot OMCI, Suspensão Administrativa, Reativação, Desprovisionamento (`DELETE`), cálculo perpétuo de Circuit ID Broadband Forum TR-101, conciliação reativa de campo e linha do tempo global do NOC.
- [x] **Autofind Scanner em Segundo Plano & Webhooks HMAC SHA-256:** Worker periódico assíncrono com locks defensivos por OLT e notificações push assinadas para ERPs.
- [x] **Central de Operações NOC em Flutter (Fase 1 Core):** Aplicação multi-plataforma (Desktop e Web) com login/setup, Autofind e ativação em 1-clique com dropdowns dinâmicos de hardware, inventário FTTH, diagnóstico óptico em tempo real, gestão de OLTs/backups e políticas PON.
- [x] **Persistência Relacional PostgreSQL 16, Docker & CI/CD:** SQLAlchemy 2.0 + 6 migrações canônicas Alembic, containers multi-stage com PostgreSQL 16 blindado em `127.0.0.1`, Caddy e pipeline GitHub Actions com publicação automatizada no Docker Hub e GitHub Pages.
- [x] **Garantia de Qualidade:** **253 testes automatizados no backend** (incluindo Testcontainers PostgreSQL 16 e `BaseDriverComplianceTest`) + suíte de testes Flutter com 100% de aprovação.

---

## 🎯 Próximos Passos (Backlog Estruturado Sob Demanda)

### 1. Evolução da Central de Operações NOC em Flutter (`frontend/`)
Conforme especificado na Seção 5.2 do [`docs/SDD.md`](SDD.md), os endpoints já implementados no backend serão integrados ao Flutter NOC estritamente sob demanda em 3 ondas:
- [x] **Onda A — Onboarding Zero-Touch Wizard (2 Fases), Raio-X de Chassi & Gestão de VLANs:** Telas para `POST /olts/inspect`, `POST /olts/onboard-wizard`, `POST /olts/onboard`, `POST /olts/{id}/telemetry`, `POST /olts/{id}/sync` e catálogo/métricas/histórico de VLANs (`/olts/{id}/vlans*`).
- [ ] **Onda B — Disaster Recovery Avançado (Multi-FTP, Unified Diff Visual, Auditoria SHA-256 & Expurgo):** Telas para gestão de servidores FTP (`/ftp-servers`), comparador visual de configurações (`/backups/compare`), auditoria (`/backups/audit`) e expurgo (`/backups/purge`).
- [x] **Onda C — Supervisão Autônoma, Conciliação TR-101, Webhooks HMAC & Governança RBAC Multi-Tenant:** Telas para controle do Autofind Scanner (`/scanner/*`), linha do tempo global TR-101 (`/onus/history`), Webhooks (`/webhooks`) e administração de Tenants, Usuários e API Keys (`/tenants`, `/users`, `/api-keys`).

### 2. Homologação de Novos Fabricantes em Bancada Física
- [ ] **Novos Concentradores Ópticos (Sob Demanda de Hardware Físico):** Homologação presencial em bancada com equipamento energizado e tráfego real antes de qualquer inclusão no `DriverRegistry`.
