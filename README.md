# 🌐 OLTAPI - Unified Multi-Vendor OLT Provisioning & Diagnostics REST API

<p align="center">
  <a href="https://ruyxingubit.github.io/oltapi/"><img src="https://img.shields.io/badge/docs-GitHub%20Pages-blueviolet.svg" alt="Documentação Oficial"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0-blue.svg" alt="License: AGPL-3.0"></a>
  <img src="https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-brightgreen.svg" alt="Python Versions">
  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/Pydantic-v2.10+-e92063.svg" alt="Pydantic v2">
  <img src="https://img.shields.io/badge/tests-219%20backend%20%2B%208%20flutter%20passed-success.svg" alt="Tests">
  <img src="https://img.shields.io/badge/Testcontainers-PostgreSQL%2016-blue.svg" alt="Testcontainers PostgreSQL 16">
  <img src="https://img.shields.io/badge/SQLAlchemy-2.0+-red.svg" alt="SQLAlchemy 2.0">
  <img src="https://img.shields.io/badge/Alembic-Migrations-orange.svg" alt="Alembic Migrations">
  <img src="https://img.shields.io/badge/HATEOAS-RFC%209110%20Ready-blueviolet.svg" alt="HATEOAS">
  <img src="https://img.shields.io/badge/Webhooks-HMAC%20SHA--256-brightgreen.svg" alt="HMAC Webhooks">
  <img src="https://img.shields.io/badge/Autofind%20Scanner-Background%20Worker-blue.svg" alt="Autofind Scanner">
  <img src="https://img.shields.io/badge/TR--101-Circuit%20ID-blue.svg" alt="Broadband Forum TR-101">
  <img src="https://img.shields.io/badge/UUIDv7-RFC%209562-orange.svg" alt="UUIDv7">
  <img src="https://img.shields.io/badge/docker-ready-blue.svg" alt="Docker Ready">
</p>

> 📖 **Portal Oficial de Documentação & ReDoc Interativo:** [https://ruyxingubit.github.io/oltapi/](https://ruyxingubit.github.io/oltapi/)  
> Acesse o portal com Guia de Instalação Docker, Manual Operacional para ERPs, Guia de Criação de Drivers e Especificação OpenAPI 3.1.0 completa.

---

## 📌 Sobre o Projeto

O **OLTAPI** é uma **API REST moderna, segura e agnóstica de fabricante** criada para unificar a gestão, o provisionamento e o diagnóstico óptico de OLTs (*Optical Line Terminals*) de múltiplos fabricantes.

Nos provedores de internet (ISPs), cada fabricante possui sua própria sintaxe de terminal (CLI), particularidades de SSH/Telnet, comandos de autofind e regras de provisionamento. Isso gera complexidade, scripts frágeis e alto acoplamento nos **ERPs de Provedor** (IXC Soft, MK-Auth, Voalle, SGP, etc.).

O **OLTAPI** resolve esse problema criando uma **camada intermediária de abstração (Driver Pattern)**: o ERP ou técnico interage apenas via JSON padronizado e a API cuida da tradução segura para o terminal de cada OLT.

---

## 🚀 Principais Funcionalidades

1. **Visualizar Configurações da OLT:** Coleta e exibição em tempo real do *running-config* ativo via SSH/CLI ou TL1.
2. **Backups com Integridade Criptográfica:** Geração de backups em disco com identificador **UUIDv7**, hash SHA-256 e download seguro via streaming.
3. **Módulo de Disaster Recovery & Detecção de Drift:** Auditoria de integridade via SHA-256, unified diff linha a linha e rotinas de retenção/expurgo seguro de backups obsoletos.
4. **Fluxos Guiados por HATEOAS & RFC 9110:** Respostas com cabeçalho padrão `Location` em criações (201) e links contextuais (`_links`) enxutos baseados no status da OLT (`online` vs `unreachable`).
5. **Consulta de Portas e Diagnóstico de ONUs:** Leitura de status operacional e potências ópticas (sinal Rx/Tx em dBm) direto da fibra com links diretos de ação rápida.
6. **Descoberta de ONUs Não Autorizadas (*Autofind*):** Varredura em tempo real de equipamentos conectados na rede óptica aguardando autorização, acompanhados de link direto para ativação.
7. **Provisionamento Padronizado de ONUs:** Ativação imediata de ONU com VLAN, profile e descrição através de um único payload JSON agnóstico de marca.
8. **Desprovisionamento & Cancelamento de Contrato:** Exclusão da ONU da memória permanente da OLT e liberação instantânea de porta PON e ONU ID (`DELETE`).
9. **Ações Remotas de Assinante:**
   - **Reboot Remoto OMCI:** Reinício do equipamento do cliente via protocolo de controle da OLT.
   - **Suspensão Administrativa (Inadimplência):** Desativação do tráfego GPON mantendo configurações intactas para fácil religamento.
   - **Reativação / Desbloqueio Financeiro:** Restabelecimento instantâneo do sinal após confirmação de pagamento.
10. **Assistente de Inicialização / Bootstrap Zero-Touch:** Geração de preview e aplicação automatizada de scripts oficiais de inicialização de OLTs virgens (baseado na engenharia oficial da Intelbras, Huawei, Fiberhome, V-SOL e ZTE).
11. **ONU como Entidade Autônoma & Auto-Recuperação Reativa (Broadband Forum TR-101):** Rastreamento perpétuo de hardware vinculado ao contrato no ERP. Quando uma fusão invertida em caixa de emenda (CEO), mudança de endereço ou cutover noturno de POP ocorre, a API provisiona na nova porta/OLT, remove a posição fantasma anterior, gera o Circuit ID padronizado (`{OLT} eth {slot}/{port}:{onu_id}:{vlan}`) e registra a manobra no histórico do NOC.
12. **Linha do Tempo Global do NOC & Coordenadas GIS:** Auditoria transparente de todas as correções ocorridas na rede e suporte nativo a geolocalização (latitude/longitude) para integração com mapas.
13. **Webhooks com Assinatura Criptográfica HMAC SHA-256:** Notificação push assíncrona (BackgroundTasks) em tempo real para os ERPs (`onu.reconciled`, `onu.detected`, `webhook.ping`) com verificação contra ataques de temporização e log de auditoria de entregas.
14. **Autofind Scanner em Segundo Plano (Supervisão Autônoma):** Worker assíncrono proativo com locks defensivos por OLT, auto-reconciliação de contratos ativos e notificações instantâneas de novos equipamentos na fibra.
15. **Persistência Relacional ACID & Migrações Canônicas Alembic:** Camada de banco de dados relacional via **SQLAlchemy 2.0**, com suporte híbrido para SQLite WAL (alta concorrência sem bloqueio de leituras) e PostgreSQL empresarial, migração transparente sem perdas de bases legadas JSON e controle de versão de schema profissional via Alembic.
16. **Onboarding Assistido via Wizard em 2 Fases (Bancada & Produção):** Pré-inspeção não-destrutiva com detecção factual de arquitetura (`interface aux` vs SVI In-Band), criação de gerência In-Band, catálogo de VLANs com propósitos (Router, Bridge, Rede Neutra, LAN-to-LAN Hairpin `p2p enable`), porta de teste untagged, compilação de perfis com submodo obrigatório `commit` e persistência na flash (`write`).

---

## 🖥️ Matriz de Concentradores Homologados

> [!NOTE]
> **Critério Rigoroso de Homologação em Bancada Física:** Drivers de OLT só são adicionados e mantidos no repositório mediante acesso a hardware físico real para homologação completa (leitura, gravação atômica, backup e provisionamento com tráfego real em bancada). Drivers teóricos foram extirpados do projeto.

| Fabricante | Modelo | Portas PON | Protocolo | Status de Homologação | Suporte |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **Fiberhome** | AN5516-01 / 04 / 06 | 4 a 16 GPON | Telnet (23) / TL1 (3337) | 🟢 Homologado em Campo | 100% Homologado em hardware real: Leitura de VLANs, perfis, ONUs ativas, running-config, backup FTP com fallback, telemetria óptica dupla (ONU/OLT RX), ciclo de vida e provisionamento ponta a ponta (Router PPPoE, Bridge e VEIP). |
| **V-SOL** | V1600GT / Série V1600G | 4 a 16 GPON | SSH / Telnet | 🟢 Homologado em Bancada Física | 100% Homologado em hardware real: Onboarding Wizard em 2 fases, detecção determinística AUX vs In-Band, VLANs híbridas, comutação inter-ONU LAN-to-LAN (`p2p enable`), porta de teste untagged, compilação de perfis com submodo `commit`, persistência na flash (`write`) e provisionamento com tráfego real de ONUs Huawei Wi-Fi 6 e Intelbras Bridge. |
| **Novos Fabricantes** | Bancada Física Requerida | GPON / EPON | Telnet / SSH / TL1 | ⚪ Sob Demanda de Hardware | [Contribuição com Hardware de Bancada](CONTRIBUTING.md) |

---

## 🏛️ Arquitetura & Inversão de Dependência (DriverRegistry)

```
[ ERP de Provedor (IXC, MK-Auth, Voalle) ]    [ Frontend NOC Flutter (Desktop & Web) ]
                     │                                        │
                     └───────────────────┬────────────────────┘
                                         │ JSON Padronizado + Header X-API-Key
                                         ▼
                             [ OLTAPI Core (FastAPI) ]
                                         │
                                         ▼
                            [ DriverRegistry Dinâmico ]
                                         │
                         ┌───────────────┴───────────────┐
                         ▼                               ▼
                 [ Fiberhome TL1 ]                [ V-SOL V1600 ]
                  (AN5516/AN6000)                  (V1600G / GT)
                         │                               │
                         ▼                               ▼
                   [ OLT Física ]                  [ OLT Física ]
```

- **Inversão de Dependência Radical:** A camada de serviço conversa exclusivamente com métodos polimórficos da interface `BaseOLTDriver`. Cada driver se auto-registra com `@DriverRegistry.register`.
- **Isolamento de Sintaxe:** Quem consome a API ou opera o Frontend NOC nunca precisa saber os dialetos de baixo nível dos fabricantes.
- **Padrão Canônico de Backup:** Prioridade nativa por FTP com fallback transparente para terminal.

---

## 🔒 Segurança em Primeiro Lugar

- **Proteção contra CLI Command Injection:** Sanitização rigorosa via regex defensivo em todos os campos fornecidos pelo usuário (`port`, `serial`, `vlan`, `description`), impedindo injeção de caracteres como `;`, `|`, `&`, `` ` ``, `$`, `>`, `<`.
- **Autenticação em Tempo Constante:** O cabeçalho `X-API-Key` é validado usando `hmac.compare_digest` para mitigar ataques de temporização (*timing attacks*).
- **Proteção contra Path Traversal:** O download de backups valida estritamente a conformidade com o formato UUIDv7 e confina os arquivos no diretório protegido.
- **Privacidade de Credenciais:** As senhas das OLTs nunca são devolvidas nos endpoints de leitura (`GET /api/v1/olts`).

---

## 📦 Como Executar

### Pré-requisitos
- Docker e Docker Compose **OU** Python 3.11+ instalado.

### Opção 1: Via Docker Compose (Stack Completa com PostgreSQL 16)

Esta é a opção recomendada tanto para desenvolvimento quanto para produção, garantindo **paridade absoluta** com o banco de dados oficial:

```bash
# 1. Clone o repositório
git clone https://github.com/RuyXingubit/oltapi.git
cd oltapi

# 2. Configure as variáveis de ambiente (opcional, defaults seguros inclusos)
cp .env.example .env

# 3. Inicie a stack (PostgreSQL 16 oficial + OLTAPI com migrações automáticas)
docker compose up -d --build
```

A stack inicializa automaticamente:
- **`oltapi_postgres` (PostgreSQL 16 Alpine):** Porta `5432`, com volume persistente `postgres_data` e healthcheck `pg_isready`.
- **`oltapi` (FastAPI Core):** Porta `8000`, aguarda o banco estar saudável, aplica as migrações do **Alembic** (`Context impl PostgresqlImpl`) e inicia o serviço.

Verifique os serviços ativos:
```bash
docker compose ps
```

A API estará disponível imediatamente em: `http://localhost:8000`

### Opção 2: Localmente com Python venv

```bash
# 1. Crie o ambiente virtual
python3 -m venv .venv
source .venv/bin/activate

# 2. Instale as dependências
pip install -r requirements.txt

# 3. Inicie o servidor com hot-reload
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 🖥️ Opção 3: Frontend NOC (Flutter Desktop & Web)

Para operar a central de rede com painel de autorização, inventário, diagnósticos ópticos e gestão de backups:

```bash
# 1. Navegue até a pasta do frontend
cd frontend

# 2. Obtenha as dependências
flutter pub get

# 3. Execute no macOS Desktop ou no navegador
flutter run -d macos  # ou: flutter run -d chrome
```

---

## 📖 Documentação Interativa da API

Com a aplicação rodando, acesse a documentação interativa com Swagger e ReDoc:
- **Swagger UI:** [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs)
- **ReDoc:** [http://localhost:8000/api/v1/redoc](http://localhost:8000/api/v1/redoc)
- **Contrato OpenAPI 3.1.0 Raw:** [`docs/api_contracts/openapi.yaml`](docs/api_contracts/openapi.yaml)
- **Portal de Documentação no GitHub Pages:** [https://ruyxingubit.github.io/oltapi/](https://ruyxingubit.github.io/oltapi/)

---

## ⚡ Resumo dos Endpoints da API

Todas as rotas exigem o cabeçalho `X-API-Key: oltapi_secret_default_key_change_me` (exceto `/health`).

| Método | Endpoint | Descrição |
| :--- | :--- | :--- |
| `GET` | `/health` | Healthcheck público da API (status 200) |
| `POST` | `/api/v1/olts` | Cadastrar OLT com teste de conectividade e Location header |
| `GET` | `/api/v1/olts` | Listar todas as OLTs cadastradas |
| `GET` | `/api/v1/olts/{id}` | Obter detalhes e links HATEOAS de uma OLT específica |
| `POST` | `/api/v1/olts/{id}/test-connection` | Teste de conectividade TCP e diagnóstico de latência |
| `GET` | `/api/v1/olts/{id}/config` | Obter o *running-config* atual da OLT |
| `POST` | `/api/v1/olts/{id}/sync` | Onboarding Brownfield com Snapshot v0 e descoberta de ONUs/VLANs |
| `GET` | `/api/v1/olts/{id}/vlans` | Listar VLANs configuradas no concentrador com links HATEOAS |
| `POST` | `/api/v1/olts/{id}/vlans` | Criar nova VLAN de serviço e gravar na memória flash (NVRAM) |
| `GET` | `/api/v1/olts/{id}/profiles` | Listar perfis de linha e DBA configurados no concentrador |
| `POST` | `/api/v1/olts/{id}/backups` | Disparar backup com hash SHA-256 e UUIDv7 |
| `GET` | `/api/v1/olts/{id}/backups` | Listar backups realizados de uma OLT |
| `GET` | `/api/v1/olts/{id}/backups/{bid}/download` | Download seguro do arquivo de backup |
| `GET` | `/api/v1/olts/{id}/backups/audit` | Auditoria de integridade e status de alteração (drift) |
| `GET` | `/api/v1/olts/{id}/backups/compare` | Comparador de 2 backups com unified diff (git diff) |
| `POST` | `/api/v1/olts/{id}/backups/purge` | Expurgo sob demanda conforme política de retenção |
| `POST` | `/api/v1/backups/run-all` | Execução em lote de backup de todas as OLTs |
| `GET` | `/api/v1/backups/audit-all` | Auditoria consolidada de todo o parque de OLTs |
| `POST` | `/api/v1/backups/purge-all` | Expurgo global de backups em todas as OLTs |
| `GET` | `/api/v1/olts/{id}/ports/{port}/onus` | Listar ONUs conectadas em uma porta PON com links rápidos |
| `GET` | `/api/v1/olts/{id}/onus/{serial}` | Consultar potência óptica (Rx/Tx dBm) e atalhos de controle |
| `GET` | `/api/v1/olts/{id}/unauthorized` | Varredura de ONUs pendentes de ativação com link de provision |
| `POST` | `/api/v1/olts/{id}/onus` | Provisionar ONU com VLAN, profile e Location header |
| `DELETE` | `/api/v1/olts/{id}/onus/{serial}` | Desprovisionar ONU e liberar recursos da porta PON |
| `POST` | `/api/v1/olts/{id}/onus/{serial}/reboot` | Reiniciar remotamente a ONU do cliente via OMCI |
| `POST` | `/api/v1/olts/{id}/onus/{serial}/suspend` | Bloquear administrativamente a ONU por inadimplência |
| `POST` | `/api/v1/olts/{id}/onus/{serial}/resume` | Reativar / desbloquear financeiramente a ONU |
| `POST` | `/api/v1/bootstrap/preview` | Pré-visualizar comandos CLI de inicialização zero-touch |
| `POST` | `/api/v1/bootstrap/apply` | Aplicar comandos de inicialização na OLT |
| `GET` | `/api/v1/onus` | Listar inventário global de ONUs e Circuit IDs |
| `POST` | `/api/v1/onus/reconcile-field-event` | Conciliação e auto-recuperação física reativa de ONU |
| `GET` | `/api/v1/onus/history` | Linha do tempo cronológica global do NOC |
| `GET` | `/api/v1/webhooks` | Listar assinaturas de Webhooks do ERP |
| `POST` | `/api/v1/webhooks` | Cadastrar novo Webhook com HMAC SHA-256 |
| `POST` | `/api/v1/webhooks/{id}/ping` | Disparar ping de teste HMAC para o ERP |
| `GET` | `/api/v1/webhooks/deliveries` | Auditoria de histórico de entregas de Webhook |
| `GET` | `/api/v1/scanner/status` | Consultar status, intervalo e métricas do Autofind Scanner |
| `POST` | `/api/v1/scanner/start` | Iniciar worker periódico de varredura em background |
| `POST` | `/api/v1/scanner/stop` | Interromper graciosamente o worker de varredura |
| `POST` | `/api/v1/scanner/run-now` | Forçar ciclo avulso imediato de varredura sob demanda |
| `PATCH` | `/api/v1/scanner/interval` | Modificar intervalo de varredura (mínimo defensivo: 10s) |

---

## 🧪 Testes Automatizados com Testcontainers & PostgreSQL 16

A integridade do projeto é garantida por **143 testes automatizados** executados diretamente contra uma instância real de **PostgreSQL 16** via **Testcontainers**, aplicando as migrações canônicas do **Alembic** e cobrindo segurança contra injeção, parsers de fabricantes, fluxos HATEOAS, ações remotas, auto-conciliação física e webhooks HMAC:

```bash
# Executar a suite de testes (sobe o container Postgres 16 automaticamente)
pytest tests/ -v
```

Relatório detalhado de conformidade: [`docs/QA_AUDIT_REPORT.md`](docs/QA_AUDIT_REPORT.md).

---

## 📚 Manuais e Guias de Referência

Criamos manuais detalhados para cada perfil de usuário:

- 🛠️ **[Manual do Desenvolvedor & Criação de Drivers](docs/MANUAL_DESENVOLVEDOR.md)**: Como o código funciona por dentro, fluxo de dados, padrão de drivers e como adicionar novos fabricantes.
- 📡 **[Manual Operacional & Integração de ERP](docs/MANUAL_OPERACIONAL.md)**: Exemplos práticos em cURL, Python, PHP e Node.js para integrar com seu ERP.
- 🏛️ **[Documento de Arquitetura](docs/ARCHITECTURE.md)**: Decisões arquiteturais, padrões adotados e ciclo de vida do driver.
- 🗺️ **[Roadmap de Evolução](docs/ROADMAP.md)**: Histórico de entregas e backlog de próximos passos operacionais.
- 🔒 **[Baseline de Segurança](docs/SECURITY_BASELINE.md)**: Mitigações de injeção de comandos, timing attacks e sanitização.
- 📋 **[Product Requirements Document (PRD)](docs/PRD.md)**: Escopo do MVP, persona e roadmap futuro.

---

## 🤝 Como Ajudar / Contribuir

Contribuições da comunidade são muito bem-vindas! Você pode ajudar:
1. **Adicionando novos drivers de OLT** (Huawei, Fiberhome, ZTE, Parks, Datacom, Nokia).
2. **Enviando saídas reais de terminal (CLI outputs)** para aumentarmos a base de testes unitários.
3. **Melhorando a documentação e exemplos de integração com ERPs.**

Leia nosso **[Guia de Contribuição (CONTRIBUTING.md)](CONTRIBUTING.md)** para instruções passo a passo de como criar branches, rodar testes e submeter Pull Requests.

---

## 📄 Licença

Este projeto está licenciado sob os termos da licença [GNU Affero General Public License v3.0 (AGPL-3.0)](LICENSE).
