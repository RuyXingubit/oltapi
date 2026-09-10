# 🌐 OLTAPI - Unified Multi-Vendor OLT Provisioning & Diagnostics REST API

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0-blue.svg" alt="License: AGPL-3.0"></a>
  <img src="https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-brightgreen.svg" alt="Python Versions">
  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/Pydantic-v2.10+-e92063.svg" alt="Pydantic v2">
  <img src="https://img.shields.io/badge/tests-39%20passed%20(100%25)-success.svg" alt="Tests">
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

1. **Visualizar Configurações da OLT:** Coleta e exibição em tempo real do *running-config* ativo via SSH/CLI.
2. **Backups com Integridade Criptográfica:** Geração de backups em disco com identificador **UUIDv7**, hash SHA-256 e download seguro via streaming.
3. **Consulta de Portas e Diagnóstico de ONUs:** Leitura de status operacional e potências ópticas (sinal Rx/Tx em dBm) direto da fibra.
4. **Descoberta de ONUs Não Autorizadas (*Autofind*):** Varredura em tempo real de equipamentos conectados na rede óptica aguardando autorização.
5. **Provisionamento Padronizado de ONUs:** Ativação imediata de ONU com VLAN, profile e descrição através de um único payload JSON agnóstico de marca.
6. **Assistente de Inicialização / Bootstrap Zero-Touch:** Geração de preview e aplicação automatizada de scripts oficiais de inicialização de OLTs virgens (baseado na engenharia oficial da Intelbras).

---

## 🖥️ Matriz de Equipamentos Suportados

| Fabricante | Modelo | Portas PON | Protocolo | Status | Suporte |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **Intelbras** | 8820 / 8820i | 8 GPON | SSH / Telnet | 🟢 Homologado | Completo (CLI Broadcom) |
| **Intelbras** | OLT G08 | 8 GPON | SSH / Telnet | 🟢 Homologado | Completo (G-Series CLI) |
| **Intelbras** | OLT G16 | 16 GPON | SSH / Telnet | 🟢 Homologado | Completo (G-Series CLI) |
| **Huawei** | SmartAX MA5800 | 8 / 16 GPON/XGS | SSH | 🟡 Em Roadmap | [Ajude a Contribuir!](CONTRIBUTING.md) |
| **Fiberhome** | AN5516-04 / 06 | 8 / 16 GPON | TL1 / SSH | 🟡 Em Roadmap | [Ajude a Contribuir!](CONTRIBUTING.md) |
| **ZTE** | C300 / C320 | 8 / 16 GPON | SSH | 🟡 Em Roadmap | [Ajude a Contribuir!](CONTRIBUTING.md) |
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
       ┌────────────────┼────────────────┐
       ▼                ▼                ▼
[ Intelbras 8820 ] [ Intelbras G08/G16 ] [ Futuros Drivers... ]
 (Broadcom CLI)     (G-Series CLI)      (Huawei / Fiberhome)
       │                │                │
       ▼                ▼                ▼
[ OLT Física ]     [ OLT Física ]     [ OLT Física ]
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

### Opção 1: Via Docker Compose (Recomendado)

```bash
# Clone o repositório
git clone https://github.com/RuyXingubit/oltapi.git
cd oltapi

# Inicie o container
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

Todas as rotas exigem o cabeçalho `X-API-Key: oltapi-default-secret-key` (exceto `/health`).

| Método | Endpoint | Descrição |
| :--- | :--- | :--- |
| `GET` | `/api/v1/health` | Healthcheck público da API |
| `POST` | `/api/v1/olts` | Cadastrar uma nova OLT |
| `GET` | `/api/v1/olts` | Listar todas as OLTs cadastradas |
| `GET` | `/api/v1/olts/{id}` | Obter detalhes de uma OLT específica |
| `GET` | `/api/v1/olts/{id}/config` | Obter o *running-config* atual da OLT |
| `POST` | `/api/v1/olts/{id}/backup` | Disparar backup com hash SHA-256 e UUIDv7 |
| `GET` | `/api/v1/olts/{id}/backups` | Listar backups realizados de uma OLT |
| `GET` | `/api/v1/olts/{id}/backups/{bid}/download` | Download seguro do arquivo de backup |
| `GET` | `/api/v1/olts/{id}/ports/{port}/onus` | Listar ONUs conectadas em uma porta PON |
| `GET` | `/api/v1/olts/{id}/onus/{serial}/details` | Consultar potência óptica (Rx/Tx dBm) e status |
| `GET` | `/api/v1/olts/{id}/onus/unauthorized` | Varredura de ONUs pendentes de ativação (*autofind*) |
| `POST` | `/api/v1/olts/{id}/onus/provision` | Provisionar ONU com VLAN e perfil |
| `POST` | `/api/v1/bootstrap/preview` | Pré-visualizar comandos CLI de inicialização zero-touch |
| `POST` | `/api/v1/bootstrap/apply` | Aplicar comandos de inicialização na OLT |

---

## 🧪 Testes Unitários

A integridade do projeto é garantida por 39 testes automatizados com cobertura completa de segurança, parsers regex e drivers:

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
