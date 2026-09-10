# Arquitetura do Sistema: OLT Provisioning & Diagnostics API

## 1. Visão Geral e Padrões Arquiteturais

A API foi projetada sobre três pilares essenciais:
1. **API-First & Contrato Agnóstico:** Clientes externos (ERPs ou técnicos via Postman) operam sobre um contrato REST JSON unificado (`docs/api_contracts/openapi.yaml`), desconhecendo comandos CLI específicos.
2. **Driver / Adapter Pattern:** Cada fabricante e modelo possui um driver dedicado que implementa `BaseOLTDriver`. A injeção e seleção do driver é realizada em tempo de execução pela `DriverFactory`.
3. **Imutabilidade e Rastreabilidade com UUIDv7:** Todos os identificadores de entidades e transações (OLTs, Backups, Tarefas) utilizam a especificação RFC 9562 (UUIDv7), garantindo ordenação cronológica nativa e indexação eficiente.

```
+-----------------------------------------------------------+
|                   Camada de Clientes                      |
|       (ERP IXC / MK-Auth / Voalle / Postman / cURL)       |
+-----------------------------+-----------------------------+
                              | HTTPS + X-API-Key
                              v
+-----------------------------------------------------------+
|                     Camada API REST                       |
|  - Fast API Router (v1)                                   |
|  - Middleware de Segurança & Validação de Entrada         |
|  - Injeção de Dependências (Deps)                         |
+-----------------------------+-----------------------------+
                              |
                              v
+-----------------------------------------------------------+
|               Camada de Negócio & Storage                 |
|  - OLT Repository (Gestão de Credenciais Seguras)         |
|  - Backup Manager (Integridade SHA-256 & Disco Protegido) |
+-----------------------------+-----------------------------+
                              |
                              v
+-----------------------------------------------------------+
|                 Driver Factory & Registry                 |
+-----------------------------+-----------------------------+
                              |
        +---------------------+---------------------+
        |                     |                     |
        v                     v                     v
+---------------+     +---------------+     +---------------+
| Intelbras8820 |     | HuaweiMA5800  |     | FiberhomeTL1  |
|    Driver     |     | Driver (Fut.) |     | Driver (Fut.) |
+-------+-------+     +-------+-------+     +-------+-------+
        |                     |                     |
        +---------------------+---------------------+
                              |
                              v
+-----------------------------------------------------------+
|                  Transporte de Rede                       |
|           (SSH / Telnet / Paramiko / Scrapli)             |
+-----------------------------------------------------------+
```

---

## 2. Padrão de Identificadores (UUIDv7)
Conforme as diretrizes globais do projeto:
- Todo identificador único é gerado como **UUIDv7** (RFC 9562).
- Os primeiros 48 bits contêm o timestamp Unix em milissegundos, garantindo ordenação natural no banco de dados e arquivos de log.
- O gerador é implementado em `app/core/uuid.py` e validado por testes unitários dedicados.

---

## 3. Gestão e Ciclo de Vida de Backups
1. **Disparo:** O endpoint `POST /api/v1/olts/{id}/backups` solicita ao driver a extração da configuração ativa.
2. **Armazenamento:** O conteúdo é gravado no diretório seguro de backups (`backups/{olt_id}/{backup_id}.cfg`).
3. **Integridade:** É calculado o hash criptográfico **SHA-256** no momento da gravação.
4. **Download:** O endpoint `GET /api/v1/olts/{id}/backups/{backup_id}/download` valida se o arquivo existe e o entrega como fluxo binário/texto com o cabeçalho `Content-Disposition`.
