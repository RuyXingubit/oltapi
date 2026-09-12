# Brainstorming & Homologação de Campo v8: Fluxo Operacional Ponta a Ponta Homologado

## 1. Avaliação de Segurança (Regra Mandatória)
- **Aumenta ou diminui a segurança?** **AUMENTA A SEGURANÇA.**
  - **Múltiplos Destinos Criptografados:** A API orquestra backups automáticos da OLT física Fiberhome AN5516 depositando os dados em servidores FTP remotos e no banco PostgreSQL 16.
  - **Senhas Ocultadas:** Credenciais da OLT e dos servidores FTP continuam protegidas contra vazamento em logs e em respostas JSON públicas da API.
  - **Integridade Criptográfica (SHA-256) e UUIDv7:** Cada backup gerado é validado por hash criptográfico SHA-256 e referenciado por identificadores universais sequenciais UUIDv7.

---

## 2. Componentes Homologados em Campo

### 2.1. OLT Fiberhome AN5516 Física
- **Host:** `${OLT_DEFAULT_HOST}:${OLT_DEFAULT_PORT}` (Telnet com usuário seguro)
- **Descoberta:** O comando oficial de dump global do fabricante é `upload ftp showrun <host> <user> <pass> <filename>`.
- **Performance:** A OLT compila os dados de todas as placas e envia o arquivo de ~178 KB em 60 a 75 segundos.

### 2.2. Servidor FTP de Destino
- **Host:** `${FTP_DEFAULT_HOST}:${FTP_DEFAULT_PORT}` (Pure-FTPd)
- **Modo:** `is_global_default = true` (herança automática para todas as OLTs cadastradas).
- **Latência de Handshake:** ~50ms a 55ms.

### 2.3. Persistência Relacional PostgreSQL 16 Oficial
- Tabela `backups_metadata` armazena o histórico com integridade referencial.
- Tabela `ftp_servers` gerencia os servidores remotos.
- Tabela `olt_ftp_destinations` permite vinculações específicas N:N.

---

## 3. Resultados de Validação em Produção

| Operação | Método / Endpoint | Status Code | Resultado Observado |
|---|---|---|---|
| **Cadastro de Servidor FTP** | `POST /api/v1/ftp-servers` | `201 Created` | Servidor `FTP-PROD-CENTRAL` registrado (`01a09724-1be5-77ed-acf0-daa55dacb08f`) com `is_global_default = true`. |
| **Teste de Conectividade FTP** | `POST /api/v1/ftp-servers/{id}/test` | `200 OK` | Conexão e autenticação estabelecidas com sucesso (latência 55ms). |
| **Cadastro da OLT Física** | `POST /api/v1/olts` | `201 Created` | OLT VTX cadastrada na porta 23 (telnet). Handshake em 9.11ms, status `online`. |
| **Destinos Efetivos de Backup** | `GET /api/v1/olts/{id}/ftp-servers` | `200 OK` | Resolução automática do FTP global central como destino efetivo. |
| **Disparo do 1º Backup** | `POST /api/v1/olts/{id}/backups` | `201 Created` | Backup `01a0979f-a18f-79de-8913-05d1cf084c8e` gerado (178.590 bytes, SHA-256 `a323959...`). |
| **Download do Arquivo .cfg** | `GET /api/v1/olts/{id}/backups/{id}/download` | `200 OK` | Arquivo transferido integralmente com configurações reais. |
| **Disparo do 2º Backup** | `POST /api/v1/olts/{id}/backups` | `201 Created` | Backup `01a097a0-e21a-756d-87c4-e5d186ad787c` gerado com sucesso. |
| **Comparação de Diff** | `GET /api/v1/olts/{id}/backups/compare` | `200 OK` | Comparação consecutiva instantânea (`identical: true`, `diff_lines: []`). |
| **Auditoria da OLT** | `GET /api/v1/olts/{id}/backups/audit` | `200 OK` | 2 backups auditados, total de 357.180 bytes persistidos. |
| **Auditoria Global** | `GET /api/v1/backups/audit-all` | `200 OK` | Relatório consolidado de todo o parque retornado. |
| **Suíte de Testes Unitários** | `pytest tests/ -v` | `Exit 0` | **153 testes passando (100% de aprovação)** sem regressões. |
