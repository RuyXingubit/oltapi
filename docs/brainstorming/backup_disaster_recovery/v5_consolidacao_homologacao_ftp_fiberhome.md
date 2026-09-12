# Brainstorming v5: Consolidação da Homologação de Backup via FTP na Fiberhome AN5516

## 1. Resultado da Prova de Conceito (PoC de Campo)
- **Equipamento:** Fiberhome AN5516 em produção (`OLT VTX`).
- **Comando executado pela API via Telnet:**
  `upload ftp showrun <ftp_host> <ftp_user> <ftp_pass> oltvtx`
- **Tempo de processamento da OLT:** 64 segundos.
- **Status de retorno:**
  ```text
  Trying upload file to ftp server, please wait...
  Finished.
  You've successfully upload config file.
  Admin#
  ```
- **Download do FTP para armazenamento local:** Executado com sucesso.
- **Arquivo salvo:** `/Volumes/240/Code/olt_backups/backup_olt_vtx_20260912_162955.cfg`
- **Tamanho:** 178.590 bytes (174.40 KB)
- **Total de Linhas:** 2.914 linhas de configuração real (placas, VLANs, perfis DBA, ONUs).
- **Hash de Integridade SHA-256:** `a323959fcb157151817fef3a70075d685090649d3ee8ab9bfe55eb76187fb550`

---

## 2. Modelagem Recomendada para a API

### Entidade `FTPServerConfig` (ou campos na OLT / Tabela Relacional)
- `id`: UUIDv7
- `name`: Nome identificador (ex: "FTP Backups Produção")
- `host`: IP ou FQDN do servidor FTP
- `port`: Porta (padrão: 21)
- `username`: Usuário do FTP
- `password`: Senha criptografada
- `base_path`: Subdiretório para armazenamento (ex: `/backups/olts/`)
- `is_default`: bool

### Tabela Relacional `olt_backups`
- `id`: UUIDv7
- `olt_id`: UUIDv7 (FK para `olts.id`)
- `filename`: Nome do arquivo gravado
- `file_size_bytes`: Tamanho em bytes
- `sha256`: Hash criptográfico SHA-256 do conteúdo
- `total_lines`: Quantidade de linhas
- `storage_path`: Caminho no volume persistente do Docker
- `created_at`: Data e hora da coleta

---

## 3. Motor de Diff de Configurações
- Com o arquivo `.cfg` oficial em texto puro de 2.914 linhas baixado pelo FTP:
  - O algoritmo `difflib.unified_diff` compara versão atual vs. versão anterior.
  - Gera visualização clara de:
    - Novas ONUs adicionadas (`+`).
    - ONUs removidas ou desprovisionadas (`-`).
    - Mudanças de VLAN, perfis de velocidade ou rotas.
