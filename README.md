# 🌐 OLTAPI - Unified Multi-Vendor OLT Provisioning & Diagnostics REST API

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0-blue.svg" alt="License: AGPL-3.0"></a>
  <img src="https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-brightgreen.svg" alt="Python Versions">
  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/Pydantic-v2.10+-e92063.svg" alt="Pydantic v2">
  <img src="https://img.shields.io/badge/tests-89%20passed%20(100%25)-success.svg" alt="Tests">
  <img src="https://img.shields.io/badge/HATEOAS-RFC%209110%20Ready-blueviolet.svg" alt="HATEOAS">
  <img src="https://img.shields.io/badge/UUIDv7-RFC%209562-orange.svg" alt="UUIDv7">
  <img src="https://img.shields.io/badge/docker-ready-blue.svg" alt="Docker Ready">
</p>

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
5. **Consulta de Portas e Diagnóstico de ONUs:** Leitura de status operacional e potências ópticas (sinal Rx/Tx em dBm) direto da fibra.
6. **Descoberta de ONUs Não Autorizadas (*Autofind*):** Varredura em tempo real de equipamentos conectados na rede óptica aguardando autorização, acompanhados de link direto para ativação.
7. **Provisionamento Padronizado de ONUs:** Ativação imediata de ONU com VLAN, profile e descrição através de um único payload JSON agnóstico de marca.
8. **Assistente de Inicialização / Bootstrap Zero-Touch:** Geração de preview e aplicação automatizada de scripts oficiais de inicialização de OLTs virgens (baseado na engenharia oficial da Intelbras, Huawei, Fiberhome, V-SOL e ZTE).

---

## 🖥️ Matriz de Equipamentos Suportados

| Fabricante | Modelo | Portas PON | Protocolo | Status | Suporte |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **Intelbras** | 8820 / 8820i | 8 GPON | SSH / Telnet | 🟢 Homologado | Completo (CLI Broadcom) |
| **Intelbras** | OLT G08 | 8 GPON | SSH / Telnet | 🟢 Homologado | Completo (G-Series CLI) |
| **Intelbras** | OLT G16 | 16 GPON | SSH / Telnet | 🟢 Homologado | Completo (G-Series CLI) |
| **Huawei** | SmartAX MA5800 (X2/X7/X15/X17) | 8 a 16 GPON/XGS | SSH | 🟢 Homologado | Completo (VRP CLI) |
| **Huawei** | MA5600T (MA5608T / MA5680T) | 8 a 16 GPON | SSH | 🟢 Homologado | Completo (VRP CLI) |
| **Fiberhome** | AN5516 (01/04/06) & AN6000 | 4 a 16 GPON | TL1 (TCP 3337) / SSH | 🟢 Homologado | Completo (TL1 Bellcore) |
| **V-SOL** | V1600GT / V1600G Series | 4 a 16 GPON | SSH / Telnet | 🟢 Homologado | Completo (CLI V-SOL) |
| **ZTE** | C300 / C320 / C600 | 8 a 16 GPON | SSH / Telnet | 🟢 Homologado | Completo (ZXROS CLI) |
| **Parks / Datacom / Nokia** | Vários | GPON | SSH | 🟡 Em Roadmap | [Ajude a Contribuir!](CONTRIBUTING.md) |

---

## 🏛️ Arquitetura (Driver / Adapter Pattern)

```
[ ERP de Provedor / Postman / cURL / App Mobile ]
                        │
                        │  JSON Padronizado + Header X-API-Key
                        ▼
             [ OLTAPI Core (FastAPI) ]
                        │
  ┌───────────────┬────────────────┬────────────────┬────────────────┬────────────────┬────────────────┐
  ▼               ▼                ▼                ▼                ▼                ▼                ▼
[ Intelbras 8820 ][ Intelbras G08 ] [ Huawei VRP ]  [ Fiberhome TL1 ] [ V-SOL V1600 ]  [ ZTE ZXROS ]   [ Em Roadmap... ]
 (Broadcom CLI)    (G08 / G16)      (MA5800/MA5600) (AN5516/AN6000)   (V1600G/GT)      (C300/C320/C600) (Parks/Datacom)
  │               │                │                │                │                │                │
  ▼               ▼                ▼                ▼                ▼                ▼                ▼
[ OLT Física ]    [ OLT Física ]    [ OLT Física ]    [ OLT Física ]    [ OLT Física ]    [ OLT Física ]    [ OLT Física ]
```

- **Isolamento de Sintaxe:** Quem consome a API nunca precisa saber se o comando é `show gpon onu unauth`, `ont-find` ou `display ont autofind`.
- **Drivers Testáveis:** Parsers regex desacoplados da conexão SSH, permitindo testes unitários rápidos e sem dependência de hardware físico.

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

### Opção 1: Via Docker Compose (Recomendado para Produção)

```bash
# 1. Clone o repositório
git clone https://github.com/RuyXingubit/oltapi.git
cd oltapi

# 2. Configure as variáveis de ambiente (opcional, defaults seguros inclusos)
cp .env.example .env

# 3. Inicie o container em background com healthcheck nativo
docker compose up -d --build
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

---

## 📖 Documentação Interativa da API

Com a aplicação rodando, acesse a documentação interativa com Swagger e ReDoc:
- **Swagger UI:** [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs)
- **ReDoc:** [http://localhost:8000/api/v1/redoc](http://localhost:8000/api/v1/redoc)
- **Contrato OpenAPI 3.1.0 Raw:** [`docs/api_contracts/openapi.yaml`](docs/api_contracts/openapi.yaml)

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
| `POST` | `/api/v1/olts/{id}/backups` | Disparar backup com hash SHA-256 e UUIDv7 |
| `GET` | `/api/v1/olts/{id}/backups` | Listar backups realizados de uma OLT |
| `GET` | `/api/v1/olts/{id}/backups/{bid}/download` | Download seguro do arquivo de backup |
| `GET` | `/api/v1/olts/{id}/backups/audit` | Auditoria de integridade e status de alteração (drift) |
| `GET` | `/api/v1/olts/{id}/backups/compare` | Comparador de 2 backups com unified diff (git diff) |
| `POST` | `/api/v1/olts/{id}/backups/purge` | Expurgo sob demanda conforme política de retenção |
| `POST` | `/api/v1/backups/run-all` | Execução em lote de backup de todas as OLTs |
| `GET` | `/api/v1/backups/audit-all` | Auditoria consolidada de todo o parque de OLTs |
| `POST` | `/api/v1/backups/purge-all` | Expurgo global de backups em todas as OLTs |
| `GET` | `/api/v1/olts/{id}/ports/{port}/onus` | Listar ONUs conectadas em uma porta PON |
| `GET` | `/api/v1/olts/{id}/onus/{serial}` | Consultar potência óptica (Rx/Tx dBm) e status da ONU |
| `GET` | `/api/v1/olts/{id}/unauthorized` | Varredura de ONUs pendentes de ativação com link de provision |
| `POST` | `/api/v1/olts/{id}/onus` | Provisionar ONU com VLAN, profile e Location header |
| `POST` | `/api/v1/bootstrap/preview` | Pré-visualizar comandos CLI de inicialização zero-touch |
| `POST` | `/api/v1/bootstrap/apply` | Aplicar comandos de inicialização na OLT |

---

## 🧪 Testes Unitários

A integridade do projeto é garantida por 89 testes automatizados com cobertura completa de segurança, parsers regex, fluxos HATEOAS e drivers:

```bash
# Executar a suite de testes
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
