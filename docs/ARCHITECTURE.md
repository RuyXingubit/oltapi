# Arquitetura do Sistema: OLT Provisioning & Diagnostics API

## 1. Visão Geral e Padrões Arquiteturais

A API foi projetada sobre três pilares essenciais:
1. **API-First & Contrato Agnóstico:** Clientes externos (ERPs ou técnicos via Postman) operam sobre um contrato REST JSON unificado (`docs/api_contracts/openapi.yaml`), desconhecendo comandos CLI específicos.
2. **Driver / Adapter Pattern:** Cada fabricante e modelo possui um driver dedicado que implementa `BaseOLTDriver`. A injeção e seleção do driver é realizada em tempo de execução pela `DriverFactory`.
3. **Imutabilidade e Rastreabilidade com UUIDv7:** Todos os identificadores de entidades e transações (OLTs, Backups, Tarefas) utilizam a especificação RFC 9562 (UUIDv7), garantindo ordenação cronológica nativa e indexação eficiente.

```
+-----------------------------------------------------------------------------+
|                             Camada de Clientes                              |
|                (ERP IXC / MK-Auth / Voalle / Postman / cURL)                |
+--------------------------------------+--------------------------------------+
                                       | HTTPS + X-API-Key
                                       v
+-----------------------------------------------------------------------------+
|                              Camada API REST                                |
|  - FastAPI Router (v1)                                                      |
|  - Middleware de Segurança, Rate Limiting & Validação de Entrada            |
|  - Injeção de Dependências (Deps: DB Session, Auth, Settings)              |
+--------------------------------------+--------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------+
|                         Camada de Negócio & Storage                         |
|  - OLT Repository (Gestão de Credenciais Seguras com Fernet AES-128)        |
|  - Backup & Disaster Recovery Service (Integridade SHA-256, Diff e Purge)   |
|  - Storage Local / Volumes Docker Protegidos (backups/{olt_id}/)            |
+--------------------------------------+--------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------+
|                           Driver Factory & Registry                         |
+--------------------------------------+--------------------------------------+
                                       |
         +-------------+---------------+-------------+-------------+
         |             |               |             |             |
         v             v               v             v             v
   +-----------+ +-----------+   +-----------+ +-----------+ +-----------+
   | Intelbras | |  Huawei   |   | Fiberhome | |   V-SOL   | |    ZTE    |
   | 8820 / G  | | SmartAX   |   |   AN5516  | |  V1600G   | | C300/C320 |
   |   (CLI)   | | VRP (CLI) |   |   (TL1)   | |   (CLI)   | |   ZXROS   |
   +-----+-----+ +-----+-----+   +-----+-----+ +-----+-----+ +-----+-----+
         |             |               |             |             |
         +-------------+---------------+-------------+-------------+
                                       |
                                       v
+-----------------------------------------------------------------------------+
|                            Transporte de Rede                               |
|                     (SSH / Telnet / Scrapli / Paramiko)                     |
+-----------------------------------------------------------------------------+
```

---

## 2. Padrão de Identificadores (UUIDv7)
Conforme as diretrizes globais do projeto:
- Todo identificador único é gerado como **UUIDv7** (RFC 9562).
- Os primeiros 48 bits contêm o timestamp Unix em milissegundos, garantindo ordenação cronológica nativa no banco de dados e no sistema de arquivos.
- O gerador é implementado em `app/core/uuid.py` e validado por testes unitários dedicados.

---

## 3. Gestão e Ciclo de Vida de Backups & Disaster Recovery
1. **Disparo e Coleta:** O endpoint `POST /api/v1/olts/{id}/backups` aciona o driver do fabricante correspondente para extrair a configuração ativa (`running-config` ou tabela TL1).
2. **Armazenamento e Imutabilidade:** O arquivo é gravado no diretório seguro de backups (`backups/{olt_id}/{backup_id}.cfg`) acompanhado do timestamp e metadados.
3. **Integridade Criptográfica (SHA-256):** O hash SHA-256 é calculado e persistido na entidade `Backup`.
4. **Auditoria Contínua & Detecção de Drift:** O endpoint `POST /api/v1/olts/{id}/backups/audit` recalcula em tempo real o hash de cada arquivo em disco e compara com o banco de dados, acusando arquivos corrompidos (`hash_mismatch`) ou ausentes (`missing`).
5. **Análise de Alterações (Unified Diff):** O endpoint `GET /api/v1/olts/{id}/backups/compare` gera diffs estruturados linha a linha entre duas versões de backup ou entre o backup selecionado e o snapshot anterior.
6. **Políticas de Retenção & Expurgo (Purge):** O endpoint `POST /api/v1/olts/{id}/backups/purge` aplica retenção por idade (`retention_days`) e cota mínima (`keep_minimum`), com modo de simulação (`dry_run=true`) antes da remoção definitiva.
7. **Operações Globais:** Endpoints em lote (`/run-all`, `/audit-all`, `/purge-all`) possibilitam execução paralela ou em lote de rotinas preventivas em todo o parque de OLTs da rede.
8. **Download Seguro:** O endpoint `GET /api/v1/olts/{id}/backups/{backup_id}/download` valida se o arquivo existe e o entrega como fluxo binário/texto com o cabeçalho `Content-Disposition`.
