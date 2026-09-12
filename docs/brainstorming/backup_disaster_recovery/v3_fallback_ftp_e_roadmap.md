# Brainstorming v3: Coleta via Terminal (Principal) com Fallback para FTP (Secundário)

## 1. Decisão de Arquitetura Aprovada pelo Usuário
- **Modo Principal (Imediato):** Coleta via Terminal (`show current-configuration` / `show running-config`) através do canal de comando (SSH/Telnet). Formato de texto puro, zero dependência de portas adicionais.
- **Modo Secundário / Fallback (Roadmap Futuro):** Suporte a recebimento via FTP/TFTP.
  - **Motivação Operacional:** Em cenários de campo onde a OLT está sob alto estresse de CPU ou com terminal CLI congelado/bloqueado, o envio via FTP através de comando de sistema pode operar como canal alternativo de resgate do backup.

---

## 2. Requisitos Futuros para o Modo FTP (Backlog)
1. **Serviço FTP/SFTP embutido na stack:** Configuração de um container leve (ex: `vsftpd` ou servidor SFTP SSH em Python) no `docker-compose.yml`.
2. **Endpoint de Gatilho FTP na OLT:**
   - Envio do comando: `upload file cfg to ftp <ip_servidor> <user> <pass> [nome_arquivo]`
   - Monitoramento do diretório de recebimento até o arquivo ser totalmente transferido e validado.
3. **Conversão Binário ➔ Texto:** Tratamento de arquivos `.bin`/`.tar` proprietários caso a OLT não envie em `.cfg` puro.

---

## 3. Plano de Execução Atual (Homologação da OLT em Campo)
1. Conectar via Telnet na OLT com o usuário `tecnico`.
2. Realizar autenticação de dois estágios (`Login` + `enable`).
3. Desativar paginação de saída no terminal (`set terminal page-lines 0` ou equivalente).
4. Executar comando de leitura de configuração (`show current-configuration` ou `show running-config`).
5. Capturar o stream completo do terminal e salvar o arquivo em `/Volumes/240/Code/olt_backups/backup_olt_vtx_<data_hora>.cfg`.
6. Exibir resumo limpo com tamanho do arquivo e hash SHA-256.
