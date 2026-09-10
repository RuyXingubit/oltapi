# Brainstorming: API Unificada de Provisionamento Multi-OLT
**Versão:** v4 (Especificação Estrita do Escopo MVP: Backup, Diagnóstico e Provisionamento)  
**Data:** 2026-09-10  
**Autor:** Antigravity & Usuário  

---

## 1. Escopo Fechado do MVP

Com base no alinhamento direto, o MVP focará estritamente nas 5 operações essenciais:

1. **Visualizar Configurações da OLT:** Coleta e exibição da configuração ativa (*running-config* / *display current-configuration*) de qualquer OLT cadastrada.
2. **Gerar e Entregar Backups via API:** Disparo de rotina de backup da OLT, armazenamento local/seguro com identificador único (**UUIDv7**) e download do arquivo de backup pela API.
3. **Visualizar ONU ou Porta:** Consulta detalhada de uma porta PON específica ou de uma ONU (status operacional, potência óptica Rx/Tx em dBm, status online/offline).
4. **Listar ONUs Descobertas (Não Autorizadas):** Varredura de ONUs pendentes de autorização (*autofind* / *unassigned*).
5. **Provisionar ONU:** Autorização de ONU na porta com perfil de linha, perfil de serviço e VLAN informados pelo ERP/técnico.

---

## 2. Contrato da API REST (Endpoints do MVP)

Todas as entidades geradas pelo sistema utilizam identificadores universais no padrão **UUIDv7**.

### 2.1 Gestão e Configuração da OLT
- `GET /api/v1/olts`: Lista as OLTs cadastradas (ID, nome, fabricante, modelo, IP, status).
- `GET /api/v1/olts/{id}/config`: Retorna a configuração corrente da OLT em texto puro ou encapsulada em JSON.

### 2.2 Rotinas de Backup
- `POST /api/v1/olts/{id}/backups`: Solicita a execução de um novo backup na OLT.
  - *Retorno:* Metadados do backup com `backup_id` (UUIDv7), data/hora, tamanho e status.
- `GET /api/v1/olts/{id}/backups`: Lista o histórico de backups da OLT.
- `GET /api/v1/olts/{id}/backups/{backup_id}/download`: Faz o download do arquivo de backup bruto gerado.

### 2.3 Diagnóstico de Portas e ONUs
- `GET /api/v1/olts/{id}/ports/{port_id}/onus`: Lista as ONUs ativas na porta PON informada (ex: `0/1/2`).
- `GET /api/v1/olts/{id}/onus/{serial_or_id}`: Retorna os detalhes de uma ONU específica:
  - Porta PON e ONU-ID.
  - Status operacional (Online/Offline/Loss of Signal).
  - Níveis de sinal óptico (Rx OLT, Rx ONU, Tx ONU) em dBm.
  - VLAN e perfis aplicados.

### 2.4 Descoberta e Provisionamento
- `GET /api/v1/olts/{id}/unauthorized`: Lista as ONUs conectadas que aguardam autorização (Serial Number, Modelo, Porta PON detectada).
- `POST /api/v1/olts/{id}/onus`: Realiza o provisionamento formal.
  - *Payload de Entrada (JSON Agnóstico):*
    ```json
    {
      "port": "0/1/1",
      "serial": "HWTC12345678",
      "vlan": 100,
      "profile": "DEFAULT_100M",
      "description": "Cliente_Joao_Silva"
    }
    ```
  - *Retorno:* Confirmação com ONU-ID atribuído e status do provisionamento.

---

## 3. Interface Padronizada dos Drivers (Driver Contract)

Cada fabricante (Huawei, Intelbras G16, Intelbras 8820, Intelbras 4840, Fiberhome, Parks) implementará a seguinte interface padrão:

```
type OLTDriver interface {
    GetRunningConfig(ctx, olt) (string, error)
    BackupConfig(ctx, olt) (BackupResult, error)
    ListUnauthorizedONUs(ctx, olt, optionalPort) ([]UnauthorizedONU, error)
    GetPortONUs(ctx, olt, port) ([]ONUSummary, error)
    GetONUDetails(ctx, olt, serialOrId) (ONUDetails, error)
    ProvisionONU(ctx, olt, req ProvisionRequest) (ProvisionResult, error)
}
```

---

## 4. Segurança em Primeiro Lugar
1. **Credenciais Protegidas:** As senhas de SSH/Telnet/SNMP das OLTs não devem ser retornadas em nenhum endpoint GET da API.
2. **Validação de Entrada Rigorosa:** Evitar *Command Injection* ao montar comandos de terminal (sanitização estrita de `serial`, `port`, `vlan` e `description` antes de enviar à CLI).
3. **Controle de Acesso:** Proteção dos endpoints por chave de API (`X-API-Key` ou Bearer Token) para que apenas o ERP ou técnicos autorizados possam disparar provisionamentos ou baixar backups.

---

## 5. Próxima Decisão para Implementação
Para iniciar o código da API:
1. **Definição da Linguagem:**
   - **Go (Golang):** Alta performance, sem dependências de sistema, Goroutines para concorrência de backups e SSH.
   - **Python (FastAPI):** Rápido desenvolvimento, uso de bibliotecas existentes como Netmiko.
2. **Primeiro Driver a Implementar:** Escolher qual OLT será o primeiro alvo para implementarmos o driver e validar com o Postman (ex: Intelbras G16 ou Huawei MA5800).
