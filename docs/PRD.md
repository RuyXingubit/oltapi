# PRD: API Unificada de Provisionamento Multi-OLT (`oltapi`)

## 1. Visão do Produto e Problema
Provedores de Internet (ISPs) e operadores de Rede Neutra gerenciam parques ópticos com múltiplos fabricantes de OLTs (Fiberhome, V-SOL, Parks, etc.). Cada fabricante possui sintaxes de terminal (CLI / TL1), protocolos e comportamentos distintos.
Isso gera:
- Dependência de softwares proprietários caros ou interfaces web lentas.
- Dificuldade de integração direta com ERPs de telecomunicações (IXC Soft, MK-Auth, SGP, Voalle, etc.).
- Complexidade para técnicos de campo e operadores do NOC autorizarem e diagnosticarem ONUs rapidamente.

**Solução:** Uma plataforma API-First agnóstica, rápida e segura construída em Python (FastAPI) com o padrão *Ports & Adapters (`BaseOLTDriver` + `@DriverRegistry.register`)* e acompanhada de uma **Central de Operações NOC em Flutter** (Web e Desktop), permitindo que qualquer ERP ou operador realize o ciclo de vida completo de comissionamento, provisionamento, backup e diagnóstico óptico das OLTs através de contratos REST JSON padronizados.

---

## 2. Personas e Casos de Uso
1. **Sistema ERP de Provedor / Operadora Locatária (Rede Neutra):**
   - Consome a API REST via chamadas autenticadas (`X-API-Key` com escopos granulares ou `Bearer JWT`) quando um contrato é assinado, alterado ou bloqueado.
   - Dispara provisionamento informando apenas serial, porta PON, perfil e VLAN autorizada.
2. **Operador de NOC / Técnico de Campo (via Central NOC Flutter ou Postman/cURL):**
   - Lista ONUs desautorizadas conectadas na caixa de atendimento (Autofind).
   - Realiza o provisionamento em 1-clique com pré-preenchimento inteligente por porta PON (`PonPolicy`) ou janelas de Cutover Zero-Touch.
   - Consulta sinal óptico real em tempo real (ONU RX, ONU TX e OLT RX RSSI em dBm) para certificar a qualidade da fibra.
3. **Engenheiro de Redes / SRE:**
   - Executa onboarding assistido em 2 fases (`inspect` e `onboard-wizard`) com criação de Baseline v0 obrigatório.
   - Dispara backups automatizados com prioridade nativa por FTP e fallback via terminal, validação SHA-256, auditoria de integridade e comparador unified diff.

---

## 3. Escopo Funcional e Operações Suportadas
A plataforma cobre as operações essenciais para o ciclo de vida operacional de redes GPON/EPON:
1. **Visualizar Configurações:** Obter a configuração corrente (`running-config` / TL1) das OLTs cadastradas.
2. **Backup & Disaster Recovery Multi-FTP:** Envio prioritário por FTP nativo da OLT com fallback automático via terminal, integridade criptográfica SHA-256, ID **UUIDv7**, comparador unified diff, auditoria de drift e expurgo automático.
3. **Diagnóstico de Porta e Telemetria Óptica Dupla:** Listar ONUs de uma porta PON e consultar potência óptica recebida na ONU (Downstream RX), transmitida pela ONU (TX) e recebida na OLT (Upstream RSSI), com links HATEOAS de navegação.
4. **Varredura de Descoberta (Autofind):** Listar ONUs pendentes de autorização (*unconfigured / autofind*).
5. **Provisionamento Dinâmico & Políticas PON:** Autorizar ONU na porta com perfil e VLAN validados contra o `provisioning-schema` real do hardware, suportando políticas padrão por porta PON e tarefas temporizadas de Cutover Zero-Touch.
6. **Desprovisionamento & Cancelamento:** Excluir ONU da OLT e liberar recursos da porta PON (`DELETE`).
7. **Ações Remotas de Assinante:** Reboot remoto OMCI, Suspensão Administrativa (bloqueio por inadimplência) e Reativação / Desbloqueio financeiro (`suspend` / `resume`).
8. **Onboarding Assistido em 2 Fases (Wizard Zero-Touch):** Pré-inspeção não-destrutiva (`AUX_ONLY`, `AUX_WITH_INBAND`, `INBAND_ACTIVE`), comissionamento de VLANs e perfis com gravação atômica na flash e snapshot Baseline v0 obrigatório.
9. **ONU como Entidade Autônoma & Auto-Recuperação Reativa (TR-101):** Rastreamento perpétuo de hardware ancorado ao contrato comercial do ERP com cálculo automático do Circuit ID Broadband Forum TR-101 e remoção da posição fantasma antiga em manobras de campo.
10. **Linha do Tempo do NOC & Geolocalização GIS:** Linha do tempo global reversa para auditoria de movimentações e suporte a coordenadas geográficas.
11. **Webhooks Criptografados para ERPs (HMAC SHA-256):** Notificações push assíncronas em tempo real com segredo cifrado em repouso (Fernet), proteção anti-SSRF e assinatura digital HMAC SHA-256.
12. **Autofind Scanner em Segundo Plano:** Worker periódico em background com locks defensivos por OLT, detecção de ONUs virgens e auto-conciliação autônoma contínua.
13. **RBAC Multi-Tenant & Rede Neutra:** Isolamento entre operadora dona da infraestrutura (`PROVIDER_OWNER`) e provedores locatários (`WHOLESALE_TENANT`), com escopos granulares e restrição por OLT e VLAN.
14. **Persistência Relacional ACID & Migrações Alembic:** Armazenamento transacional via **SQLAlchemy 2.0** com suporte híbrido SQLite WAL e PostgreSQL 16, criptografia Fernet AES para credenciais e controle canônico de versões via Alembic.

*Parque de Concentradores Homologados em Hardware Físico de Bancada:*
- **Fiberhome:** `AN5516-01` / `AN5516-04` / `AN5516-06` / `AN6000` (Telnet CLI + TL1 Bellcore).
- **V-SOL:** `V1600GT` / Série `V1600G` (SSH / Telnet CLI).
- **Parks:** `Fiberlink 10008S` / Série `21000` (Telnet CLI).

---

## 4. Critérios de Aceite
- [x] Especificação SDD ([`docs/SDD.md`](file:///Volumes/240/Code/oltapi/docs/SDD.md)) e Contrato OpenAPI 3.1.0 ([`docs/api_contracts/openapi.yaml`](file:///Volumes/240/Code/oltapi/docs/api_contracts/openapi.yaml)) sincronizados (75 rotas / 96 operações / 96 schemas).
- [x] Toda entidade e backup identificado por **UUIDv7** (RFC 9562).
- [x] Proteção ativa contra injeção de comandos CLI e SSRF em todos os parâmetros de entrada.
- [x] Controle de acesso RBAC Multi-Tenant (JWT Bearer + API Keys SHA-256 com validação de subconjunto de escopos) e criptografia Fernet AES em repouso.
- [x] 3 Drivers de fabricantes homologados em bancada física real (Fiberhome, V-SOL e Parks) aprovados na `BaseDriverComplianceTest`.
- [x] Ciclo de vida completo de ONUs: Descoberta, Provisionamento, Reboot, Suspensão, Reativação e Desprovisionamento.
- [x] Central de Operações NOC em Flutter (Desktop e Web) integrada à API REST sem dados fictícios.
- [x] Motor de Auto-Recuperação Reativa de Campo e Circuit ID Broadband Forum TR-101.
- [x] Subsistema de Webhooks com assinatura digital HMAC SHA-256, proteção SSRF e execução não-bloqueante.
- [x] Autofind Scanner periódico em background com proteção de concorrência por OLT e endpoints de controle operacional.
- [x] Persistência Relacional com SQLAlchemy 2.0, suporte SQLite WAL / PostgreSQL 16 e 6 migrações canônicas Alembic.
- [x] 100% de aprovação na suíte de testes automatizados (**253 testes unitários e de conformidade no backend** + testes Flutter).
- [x] Pipeline CI/CD GitHub Actions otimizado (Actions Node 24 `@v7`/`@v5`, gate OpenAPI, limites de tempo e controle de concorrência).
