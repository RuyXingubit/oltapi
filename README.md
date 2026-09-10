# OLT Provisioning & Diagnostics Unified API

API REST moderna, segura e padronizada para provisionamento multi-fabricante de OLTs, coleta de configurações ativas, gestão de backups com integridade criptográfica e diagnóstico óptico.

Projetada para integração direta com qualquer **ERP de Provedor** (IXC, MK-Auth, Voalle, SGP, etc.) ou uso operacional por técnicos via **Postman / cURL**.

---

## 🚀 Funcionalidades do MVP

1. **Visualizar Configurações da OLT:** Coleta e exibição em tempo real do *running-config*.
2. **Backups via API com Integridade:** Disparo de rotina de backup, armazenamento protegido em disco com identificador **UUIDv7**, hash SHA-256 e download via streaming.
3. **Consulta de Portas e Diagnóstico de ONUs:** Listagem de ONUs em uma porta PON e leitura de níveis de potência óptica (Rx/Tx em dBm) e status operacional (online/offline).
4. **Descoberta de ONUs Não Autorizadas:** Varredura em tempo real de ONUs pendentes de ativação (*autofind*).
5. **Provisionamento Padronizado:** Autorização de ONU com VLAN, perfil e descrição através de payload JSON agnóstico de fabricante.

**Piloto Inicial Implementado:** OLT **Intelbras 8820** (GPON).

---

## 🛠️ Arquitetura e Padrão de Drivers

```
[ ERP / Postman / App ] 
       │ (JSON agnóstico + X-API-Key)
       ▼
[ OLT API Core (FastAPI) ]
       │
[ Driver Factory / Router ]
       ├──> [ Intelbras8820Driver ] ──> SSH / Telnet (CLI)
       ├──> [ HuaweiMA5800Driver ]  ──> (Planejado / Roadmap)
       ├──> [ FiberhomeTL1Driver ]  ──> (Planejado / Roadmap)
       └──> [ ParksDriver ]         ──> (Planejado / Roadmap)
```

---

## 🔒 Segurança em Primeiro Lugar

- **Proteção contra CLI Command Injection:** Sanitização rigorosa via regex defensivo em todos os campos fornecidos pelo usuário (`port`, `serial`, `vlan`, `description`), impedindo injeção de pipes, ponto-e-vírgula e escapes.
- **Autenticação Segura:** Cabeçalho HTTP `X-API-Key` validado via comparação em tempo constante (`hmac.compare_digest`), mitigando *timing attacks*.
- **Prevenção de Path Traversal:** Validação de UUIDv7 estrito e confinamento de caminhos no download de arquivos de backup.
- **Omissão de Senhas:** Credenciais de OLTs nunca são expostas em endpoints GET.

---

## 📦 Como Executar

### Opção 1: Via Docker Compose (Recomendado)

```bash
docker compose up -d --build
```
A API estará acessível em `http://localhost:8000`.

### Opção 2: Localmente com Python 3.11+

```bash
# 1. Crie o ambiente virtual
python3 -m venv .venv
source .venv/bin/activate

# 2. Instale as dependências
pip install -r requirements.txt

# 3. Inicie o servidor
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Acesse a documentação interativa OpenAPI/Swagger no navegador:
- **Swagger UI:** `http://localhost:8000/api/v1/docs`
- **ReDoc:** `http://localhost:8000/api/v1/redoc`

---

## 🧪 Executando os Testes Unitários

```bash
pytest tests/ -v
```

Relatório detalhado de conformidade: [`docs/QA_AUDIT_REPORT.md`](docs/QA_AUDIT_REPORT.md).

---

## 📖 Documentação do Projeto

- **Contrato OpenAPI 3.1.0:** [`docs/api_contracts/openapi.yaml`](docs/api_contracts/openapi.yaml)
- **Documento de Arquitetura:** [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- **Baseline de Segurança:** [`docs/SECURITY_BASELINE.md`](docs/SECURITY_BASELINE.md)
- **Product Requirements Document (PRD):** [`docs/PRD.md`](docs/PRD.md)
- **Histórico de Brainstorming Incremental:** [`docs/brainstorming/provisionamento_multi_olt/`](docs/brainstorming/provisionamento_multi_olt/)
