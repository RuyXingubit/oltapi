# Brainstorming v2: Estratégia de Coleta de Backup — Terminal vs. FTP/TFTP

## 1. Avaliação de Segurança (Regra Mandatória)
- **Aumenta ou diminui a segurança?**
  - **Coleta via Terminal (SSH):** **AUMENTA A SEGURANÇA.** Utiliza o próprio canal criptografado já estabelecido entre a API e a OLT. Nenhuma porta extra (como FTP inseguro porta 21) precisa ser aberta na infraestrutura.
  - **Envio via FTP tradicional:** **DIMINUI A SEGURANÇA.** O protocolo FTP tradicional (RFC 959) transmite dados e credenciais em texto puro. Além disso, a OLT precisa alcançar o servidor da API (exigindo rotas reversas ou furos em firewalls).
  - **Envio via SFTP/SCP:** Seguro, porém muitas OLTs legadas Fiberhome (firmwares antigos AN5516) não possuem cliente SFTP/SCP compilado, suportando apenas cliente TFTP ou FTP básico.

---

## 2. Comparativo Técnico: Terminal vs. FTP

| Critério | Método 1: Stream Direto pelo Terminal (Recomendado) | Método 2: Upload via FTP/TFTP |
| :--- | :--- | :--- |
| **Como funciona?** | A API executa `show current-configuration` ou `show running-config` na sessão SSH/Telnet e captura o texto retornado no buffer. | A API envia o comando `upload file cfg to ftp <ip> <user> <pass>` e a OLT faz upload para um servidor FTP da API. |
| **Dependência de Rede** | **Zero dependência extra.** Se a API já conectou na OLT, o backup é garantido. Funciona através de NAT, VPN e CGNAT. | **Alta dependência.** A OLT precisa conseguir abrir conexão de volta para o IP da API na porta 21/20 (Data Channel). |
| **Infraestrutura** | Não requer nenhum serviço adicional no Docker. | Requer container de FTP rodando no Docker Compose (`vsftpd` ou similar) com portas expostas. |
| **Velocidade** | 2 a 8 segundos (suficiente para agendamentos e rotinas). | 1 a 2 segundos (transferência de binário direto). |
| **Legibilidade / Diff** | Formato texto puro direto para diff de alterações e auditoria SHA-256. | Frequentemente em formato binário proprietário (.bin / .tar), dificultando diff textual. |

---

## 3. Workflow de Homologação da Fiberhome

O fluxo ideal de homologação para cadastrar uma nova Fiberhome de forma 100% autônoma e segura:

```mermaid
sequenceDiagram
    autonumber
    actor Operador
    participant API as OLT API
    participant OLT as Fiberhome OLT
    participant DB as PostgreSQL 16
    participant Disk as /olt_backups/

    Operador->>API: 1. Cadastra OLT (IP, user temporário 'tecnico')
    API->>OLT: 2. Conecta via Telnet (porta 23)
    API->>OLT: 3. Executa 'enable'
    API->>OLT: 4. Cria usuário de serviço aleatório com chave forte (ex: 'oltapi_svc')
    API->>OLT: 5. Ativa servidor SSH (porta 22) se inativo
    API->>OLT: 6. Executa 'save' na flash
    API->>OLT: 7. Desativa paginação ('set terminal page-lines 0')
    API->>OLT: 8. Executa 'show current-configuration' / 'show running-config'
    OLT-->>API: 9. Retorna texto completo da configuração
    API->>Disk: 10. Salva running-config em arquivo (.cfg)
    API->>DB: 11. Registra OLT, credenciais seguras e SHA-256 do 1º backup
    API-->>Operador: 12. Retorna Sucesso + Status de Conexão Segura
```

---

## 4. Recomendação Estratégica
1. **Adotar a Coleta via Terminal como padrão:** É a mais simples, segura, não exige servidor FTP extra e funciona em 100% das topologias de rede.
2. **Suporte a FTP como modo avançado:** Manter a porta aberta para, no futuro, caso o cliente tenha OLTs massivas (chassi de 16 slots), habilitar um modo de transferência FTP dedicado.
