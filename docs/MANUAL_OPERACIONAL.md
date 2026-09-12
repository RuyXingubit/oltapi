# Manual Operacional & Guia de Integração para Provedores (OLTAPI)

Este manual destina-se a **engenheiros de rede**, **administradores de provedores de internet (ISPs)**, **técnicos de campo** e **desenvolvedores de ERPs de telecom** (como IXC Soft, MK-Auth, Voalle, SGP, RadiusNet, etc.) que desejam operar ou integrar com o **OLTAPI**.

---

## 🧭 Sumário

1. [Autenticação e Cabeçalhos](#1-autenticação-e-cabeçalhos)
2. [Cadastrando OLTs na API](#2-cadastrando-olts-na-api)
3. [Coletando Running-Config e Gerenciando Backups](#3-coletando-running-config-e-gerenciando-backups)
4. [Diagnóstico Óptico e Consulta de ONUs](#4-diagnóstico-óptico-e-consulta-de-onus)
5. [Ciclo de Vida Completo de ONUs (Provisionamento e Ações Remotas)](#5-ciclo-de-vida-completo-de-onus-provisionamento-e-ações-remotas)
   - 5.1 [Descoberta (Autofind)](#51-listar-onus-não-autorizadas-no-bairro)
   - 5.2 [Provisionamento](#52-provisionar-a-onu-ativação-imediata)
   - 5.3 [Reboot Remoto OMCI](#53-reinicialização-remota-reboot-omci)
   - 5.4 [Bloqueio por Inadimplência](#54-suspensão-administrativa-bloqueio-por-inadimplência)
   - 5.5 [Desbloqueio Financeiro](#55-reativação--desbloqueio-financeiro)
   - 5.6 [Desprovisionamento / Cancelamento](#56-desprovisionamento-e-cancelamento-de-contrato)
6. [Assistente de Bootstrap Zero-Touch (OLT Virgem)](#6-assistente-de-bootstrap-zero-touch-olt-virgem)
7. [Exemplos Práticos de Integração (cURL, Python, PHP, Node.js)](#7-exemplos-práticos-de-integração)

---

## 1. Autenticação e Cabeçalhos

Todas as requisições para a API (exceto o healthcheck `/api/v1/health`) devem incluir o cabeçalho HTTP:

```http
X-API-Key: sua-chave-secreta-aqui
Content-Type: application/json
```

A chave padrão em ambiente de desenvolvimento é `oltapi-default-secret-key` (configurada via variável de ambiente `API_KEY` no `.env` ou `docker-compose.yml`).

---

## 2. Cadastrando OLTs na API

Para cadastrar um novo equipamento gerenciado:

### Requisição:
`POST /api/v1/olts`

```json
{
  "name": "OLT-POP-CENTRO-01",
  "vendor": "intelbras",
  "model": "8820i",
  "host": "10.0.100.2",
  "port": 22,
  "protocol": "ssh",
  "username": "admin",
  "password": "MinhaSenhaForte123"
}
```

> [!TIP]
> Fabricantes e modelos atualmente homologados:
> - **Intelbras:** `vendor: "intelbras"` / `model: "8820"`, `"8820i"`, `"g08"`, `"g16"`
> - **Huawei:** `vendor: "huawei"` / `model: "ma5800"`, `"ma5800-x2"`, `"ma5800-x7"`, `"ma5608t"`, `"ma5680t"`
> - **Fiberhome:** `vendor: "fiberhome"` / `model: "an5516"`, `"an5516-01"`, `"an5516-04"`, `"an5516-06"`, `"an6000"`
> - **V-SOL:** `vendor: "vsol"` / `model: "v1600gt"`, `"v1600g"`, `"v1600g-04"`, `"v1600g-08"`, `"v1600g-16"`
> - **ZTE:** `vendor: "zte"` / `model: "c300"`, `"c320"`, `"c600"`

### Resposta de Sucesso (`201 Created`):
**Cabeçalho HTTP:** `Location: /api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde`

```json
{
  "id": "0191e4f2-51a8-7d84-a12b-3456789abcde",
  "name": "OLT-POP-CENTRO-01",
  "vendor": "intelbras",
  "model": "8820i",
  "host": "10.0.100.2",
  "port": 22,
  "protocol": "ssh",
  "status": "online",
  "connection_message": "Porta 22 acessível em 10.0.100.2. Latência de handshake: 8.5ms.",
  "created_at": "2026-09-11T19:30:00Z",
  "_links": {
    "self": { "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde", "method": "GET" },
    "config": { "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde/config", "method": "GET" },
    "unauthorized_onus": { "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde/unauthorized", "method": "GET" },
    "backups": { "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde/backups", "method": "GET" },
    "trigger_backup": { "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde/backups", "method": "POST" }
  }
}
```
*Se a OLT não responder na porta TCP no momento do cadastro, ela é gravada com `status: "unreachable"`, trazendo mensagem diagnóstica e `_links` contextuais para edição e reteste.*

### 2.1 Teste de Conectividade sob Demanda
`POST /api/v1/olts/{olt_id}/test-connection`

Executa um handshake rápido (sem travar requisições) para validar se a porta SSH/Telnet da OLT está acessível na rede:
```json
{
  "olt_id": "0191e4f2-51a8-7d84-a12b-3456789abcde",
  "host": "10.0.100.2",
  "port": 22,
  "reachable": true,
  "latency_ms": 7.42,
  "message": "Porta 22 acessível em 10.0.100.2. Latência de handshake: 7.42ms.",
  "_links": {
    "self": { "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde", "method": "GET" },
    "config": { "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde/config", "method": "GET" }
  }
}
```

---

## 3. Coletando Running-Config e Gerenciando Backups

### 3.1 Visualizar Configuração Ativa
`GET /api/v1/olts/{olt_id}/config`

Retorna a íntegra da configuração que está rodando na memória da OLT acompanhada de links para persistir em backup.

### 3.2 Gerar Backup com Hash Criptográfico
`POST /api/v1/olts/{olt_id}/backups`

Gera um arquivo de backup em disco com nome seguro baseado em UUIDv7, calcula o hash SHA-256 e devolve o header `Location`:
**Cabeçalho HTTP:** `Location: /api/v1/olts/{olt_id}/backups/{backup_id}/download`

```json
{
  "backup_id": "0191e512-3456-789a-bcde-f0123456789a",
  "olt_id": "0191e4f2-51a8-7d84-a12b-3456789abcde",
  "created_at": "2026-09-11T19:30:00Z",
  "size_bytes": 24512,
  "sha256_hash": "3a7b9c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b",
  "filename": "backup_0191e512-3456-789a-bcde-f0123456789a.cfg",
  "_links": {
    "download": { "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde/backups/0191e512-3456-789a-bcde-f0123456789a/download", "method": "GET" },
    "compare": { "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde/backups/compare?target_id=0191e512-3456-789a-bcde-f0123456789a", "method": "GET" },
    "audit": { "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde/backups/audit", "method": "GET" }
  }
}
```

### 3.3 Download do Arquivo de Backup
`GET /api/v1/olts/{olt_id}/backups/{backup_id}/download`

Faz o download via stream do arquivo de configuração para armazenamento externo, cofre ou replicação S3.

### 3.4 Auditoria de Integridade e Detecção de Drift
`GET /api/v1/olts/{olt_id}/backups/audit`

Retorna métricas de saúde dos backups da OLT e se houve alteração no *running-config* (`has_changed: true/false`):

```json
{
  "olt_id": "0191e4f2-51a8-7d84-a12b-3456789abcde",
  "olt_name": "OLT-POP-CENTRO-01",
  "total_backups": 15,
  "total_bytes": 367680,
  "latest_backup": { "backup_id": "...", "sha256_hash": "..." },
  "previous_backup": { "backup_id": "...", "sha256_hash": "..." },
  "has_changed": true,
  "last_backup_at": "2026-09-11T19:30:00Z"
}
```

### 3.5 Comparador de Backups com Unified Diff (Estilo Git Diff)
`GET /api/v1/olts/{olt_id}/backups/compare`
*(Opcional: `?base_id={id1}&target_id={id2}`. Se omitido, compara os 2 backups mais recentes).*

```json
{
  "olt_id": "0191e4f2-51a8-7d84-a12b-3456789abcde",
  "base_backup_id": "0191e4f2-...",
  "target_backup_id": "0191e512-...",
  "identical": false,
  "base_sha256": "3a7b9c...",
  "target_sha256": "8f2e1a...",
  "diff_lines": [
    "--- backup_base.cfg",
    "+++ backup_target.cfg",
    "@@ -15,4 +15,6 @@",
    " vlan 100",
    "+vlan 200",
    "+ name CLIENTES_FIBRA",
    " interface gpon 0/1"
  ],
  "additions_count": 2,
  "deletions_count": 0
}
```

### 3.6 Expurgo e Política de Retenção sob Demanda
`POST /api/v1/olts/{olt_id}/backups/purge`
Payload opcional: `{"max_backups_per_olt": 30, "max_age_days": 60}`.

### 3.7 Operações Globais em Lote
- `POST /api/v1/backups/run-all`: Coleta backups de todo o parque de OLTs sequencialmente.
- `GET /api/v1/backups/audit-all`: Visão de auditoria de todas as OLTs cadastradas.
- `POST /api/v1/backups/purge-all`: Aplica limpeza global de backups antigos.


---

## 4. Diagnóstico Óptico e Consulta de ONUs

### 4.1 Listar ONUs em uma Porta PON
`GET /api/v1/olts/{olt_id}/ports/{port}/onus`
*(Exemplo: `/api/v1/olts/{id}/ports/1/1/onus` ou `/api/v1/olts/{id}/ports/0/1/onus`)*

Cada item da listagem conta com links rápidos (`_links`) para diagnóstico detalhado, reinicialização ou bloqueio imediato:

```json
[
  {
    "port": "1/1",
    "onu_id": 1,
    "serial": "ITBS12345678",
    "status": "online",
    "name": "Cliente_Joao_Silva",
    "_links": {
      "details": {
        "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde/onus/ITBS12345678",
        "method": "GET",
        "description": "Consultar níveis de potência óptica e detalhes"
      },
      "reboot": {
        "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde/onus/ITBS12345678/reboot?port=1/1&onu_id=1",
        "method": "POST",
        "description": "Reiniciar remotamente esta ONU"
      },
      "suspend": {
        "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde/onus/ITBS12345678/suspend?port=1/1&onu_id=1",
        "method": "POST",
        "description": "Bloquear administrativamente por inadimplência"
      }
    }
  }
]
```

### 4.2 Consultar Detalhes e Potência Óptica (Sinal RX/TX em dBm)
`GET /api/v1/olts/{olt_id}/onus/{serial_or_id}`

```json
{
  "port": "1/1",
  "onu_id": 1,
  "serial": "ITBS12345678",
  "status": "online",
  "name": "Cliente_Joao_Silva",
  "rx_power_dbm": -19.45,
  "tx_power_dbm": 2.15,
  "_links": {
    "reboot": {
      "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde/onus/ITBS12345678/reboot?port=1/1&onu_id=1",
      "method": "POST",
      "description": "Reiniciar remotamente esta ONU"
    },
    "suspend": {
      "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde/onus/ITBS12345678/suspend?port=1/1&onu_id=1",
      "method": "POST",
      "description": "Suspender administrativamente o serviço da ONU"
    },
    "resume": {
      "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde/onus/ITBS12345678/resume?port=1/1&onu_id=1",
      "method": "POST",
      "description": "Reativar serviço da ONU"
    },
    "deprovision": {
      "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde/onus/ITBS12345678?port=1/1&onu_id=1",
      "method": "DELETE",
      "description": "Desprovisionar e liberar porta"
    },
    "port_onus": {
      "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde/ports/1/1/onus",
      "method": "GET",
      "description": "Listar ONUs da mesma porta"
    }
  }
}
```

---

## 5. Ciclo de Vida Completo de ONUs (Provisionamento e Ações Remotas)

### 5.1 Listar ONUs Não Autorizadas no Bairro
`GET /api/v1/olts/{olt_id}/unauthorized`

Cada ONU descoberta vem acompanhada de um hiperlink HATEOAS que aponta diretamente para a ação de provisionamento:

```json
[
  {
    "port": "1/1",
    "serial": "ITBS99887766",
    "model": "110B",
    "detected_at": "2026-09-11T19:32:00Z",
    "_links": {
      "provision": {
        "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde/onus",
        "method": "POST"
      }
    }
  }
]
```

### 5.2 Provisionar a ONU (Ativação Imediata)
`POST /api/v1/olts/{olt_id}/onus`

```json
{
  "serial": "ITBS99887766",
  "port": "1/1",
  "vlan": 100,
  "profile": "100M_FIBRA",
  "description": "Cliente_Contrato_49102"
}
```

**Resposta (`201 Created`):**
**Cabeçalho HTTP:** `Location: /api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde/onus/ITBS99887766`

```json
{
  "success": true,
  "port": "1/1",
  "onu_id": 3,
  "serial": "ITBS99887766",
  "message": "ONU provisionada e salva com sucesso na memória da OLT.",
  "_links": {
    "details": {
      "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde/onus/ITBS99887766",
      "method": "GET"
    },
    "port_onus": {
      "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde/ports/1/1/onus",
      "method": "GET"
    }
  }
}
```

### 5.3 Reinicialização Remota (Reboot OMCI)
`POST /api/v1/olts/{olt_id}/onus/{serial_or_id}/reboot?port=1/1&onu_id=3`

Permite ao suporte N1 reiniciar o equipamento da casa do assinante sem visita técnica e sem derrubar a porta PON inteira.

```json
{
  "success": true,
  "action": "reboot",
  "olt_id": "0191e4f2-51a8-7d84-a12b-3456789abcde",
  "serial": "ITBS99887766",
  "port": "1/1",
  "onu_id": 3,
  "message": "Comando de reinicialização remota enviado com sucesso para a ONU ITBS99887766.",
  "_links": {
    "details": {
      "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde/onus/ITBS99887766",
      "method": "GET",
      "description": "Verificar status e potências ópticas da ONU pós-reinicialização"
    },
    "olt": {
      "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde",
      "method": "GET",
      "description": "Consultar status da OLT"
    }
  }
}
```

### 5.4 Suspensão Administrativa (Bloqueio por Inadimplência)
`POST /api/v1/olts/{olt_id}/onus/{serial_or_id}/suspend?port=1/1&onu_id=3`

Utilizado por rotinas automáticas de ERP (como IXC, MK-Auth) quando uma fatura vence há mais de N dias. Desativa o tráfego da ONU na OLT mantendo as configurações gravadas.

```json
{
  "success": true,
  "action": "suspend",
  "olt_id": "0191e4f2-51a8-7d84-a12b-3456789abcde",
  "serial": "ITBS99887766",
  "port": "1/1",
  "onu_id": 3,
  "message": "ONU ITBS99887766 suspensa administrativamente (bloqueada) com sucesso.",
  "_links": {
    "resume": {
      "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde/onus/ITBS99887766/resume?port=1/1&onu_id=3",
      "method": "POST",
      "description": "Reativar / desbloquear serviço da ONU"
    },
    "details": {
      "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde/onus/ITBS99887766",
      "method": "GET",
      "description": "Verificar status da ONU"
    },
    "deprovision": {
      "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde/onus/ITBS99887766?port=1/1&onu_id=3",
      "method": "DELETE",
      "description": "Desprovisionar e liberar porta se cancelado"
    }
  }
}
```

### 5.5 Reativação / Desbloqueio Financeiro
`POST /api/v1/olts/{olt_id}/onus/{serial_or_id}/resume?port=1/1&onu_id=3`

Ao receber a confirmação de baixa do boleto ou PIX no ERP, a ONU é reativada instantaneamente no hardware da OLT.

```json
{
  "success": true,
  "action": "resume",
  "olt_id": "0191e4f2-51a8-7d84-a12b-3456789abcde",
  "serial": "ITBS99887766",
  "port": "1/1",
  "onu_id": 3,
  "message": "ONU ITBS99887766 reativada (desbloqueada) com sucesso.",
  "_links": {
    "details": {
      "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde/onus/ITBS99887766",
      "method": "GET",
      "description": "Verificar sinal óptico da ONU reativada"
    },
    "suspend": {
      "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde/onus/ITBS99887766/suspend?port=1/1&onu_id=3",
      "method": "POST",
      "description": "Suspender administrativamente a ONU"
    },
    "reboot": {
      "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde/onus/ITBS99887766/reboot?port=1/1&onu_id=3",
      "method": "POST",
      "description": "Reiniciar remotamente a ONU"
    }
  }
}
```

### 5.6 Desprovisionamento e Cancelamento de Contrato
`DELETE /api/v1/olts/{olt_id}/onus/{serial_or_id}?port=1/1&onu_id=3`

Em caso de cancelamento de plano ou mudança de endereço, a ONU é excluída da memória permanente da OLT, liberando o índice ONU ID e os recursos da porta PON:

```json
{
  "success": true,
  "action": "deprovision",
  "olt_id": "0191e4f2-51a8-7d84-a12b-3456789abcde",
  "serial": "ITBS99887766",
  "port": "1/1",
  "onu_id": 3,
  "message": "ONU ITBS99887766 desprovisionada e removida com sucesso da porta 1/1.",
  "_links": {
    "unauthorized_onus": {
      "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde/unauthorized",
      "method": "GET",
      "description": "Verificar ONUs não autorizadas para reprovisionamento"
    },
    "port_onus": {
      "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde/ports/1/1/onus",
      "method": "GET",
      "description": "Listar ONUs ativas na porta"
    },
    "olt": {
      "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde",
      "method": "GET",
      "description": "Consultar dados da OLT"
    }
  }
}
```

---

## 6. Assistente de Bootstrap Zero-Touch (OLT Virgem)

Quando o técnico instala uma OLT nova que acabou de sair da caixa, ele não precisa digitar dezenas de comandos complexos de terminal. O **OLTAPI** gera a configuração oficial recomendada pelo fabricante.

### 6.1 Pré-visualizar Comandos (Preview Seguro)
`POST /api/v1/bootstrap/preview`

```json
{
  "vendor": "intelbras",
  "model": "g16",
  "ip_address": "192.168.1.100",
  "netmask": "255.255.255.0",
  "gateway": "192.168.1.1",
  "vlan_mode": "single",
  "vlan_id": 100,
  "uplink_port": "ge1",
  "uplink_type": "optical"
}
```

Retorna uma lista ordenada com cada comando CLI que será executado na OLT.

### 6.2 Aplicar Configuração na OLT
`POST /api/v1/bootstrap/apply`

```json
{
  "olt_id": "018e3c45-6789-7abc-def0-123456789abc",
  "config": {
    "vendor": "intelbras",
    "model": "g16",
    "ip_address": "10.0.100.2",
    "netmask": "255.255.255.0",
    "gateway": "10.0.100.1",
    "vlan_mode": "vlan_per_pon",
    "base_vlan": 200,
    "uplink_port": "ge1"
  }
}
```

A API se conecta via SSH/Telnet, aplica o lote de comandos e salva as alterações na memória não-volátil da OLT automaticamente.

---

## 7. Exemplos Práticos de Integração

### 7.1 Exemplo via cURL
```bash
# Consultar ONUs não autorizadas
curl -X GET "http://localhost:8000/api/v1/olts/018e3c45-6789-7abc-def0-123456789abc/onus/unauthorized" \
     -H "X-API-Key: oltapi-default-secret-key"
```

### 7.2 Exemplo via Python (requests)
```python
import requests

API_URL = "http://localhost:8000/api/v1"
HEADERS = {"X-API-Key": "oltapi-default-secret-key"}

# Provisionar uma nova ONU
payload = {
    "serial": "ITBS12345678",
    "port": "1",
    "vlan": 100,
    "description": "CLIENTE_49102"
}

resp = requests.post(
    f"{API_URL}/olts/018e3c45-6789-7abc-def0-123456789abc/onus/provision",
    json=payload,
    headers=HEADERS
)

print(resp.json())
```

### 7.3 Exemplo via PHP (cURL / Laravel)
```php
<?php
$client = new \GuzzleHttp\Client([
    'base_uri' => 'http://localhost:8000/api/v1/',
    'headers' => [
        'X-API-Key' => 'oltapi-default-secret-key',
        'Accept' => 'application/json'
    ]
]);

$response = $client->get('olts/018e3c45-6789-7abc-def0-123456789abc/onus/unauthorized');
$unauthorizedOnus = json_decode($response->getBody()->getContents(), true);
```

### 7.4 Exemplo via Node.js (Axios)
```javascript
const axios = require('axios');

const api = axios.create({
  baseURL: 'http://localhost:8000/api/v1',
  headers: { 'X-API-Key': 'oltapi-default-secret-key' }
});

async function checkOpticalPower(oltId, serial) {
  const { data } = await api.get(`/olts/${oltId}/onus/${serial}/details`);
  console.log(`RX Power: ${data.rx_power_dbm} dBm, TX Power: ${data.tx_power_dbm} dBm`);
}
```

---

## 8. ONU como Entidade Autônoma, Broadband Forum TR-101 e Auto-Recuperação Reativa

No mundo real de telecomunicações, **portas PON e OLTs são efêmeras, mas o serial do equipamento e o contrato do assinante são perenes**. Durante manutenções na madrugada, cutovers de anel óptico, fusões invertidas em caixas de emenda (CEOs) ou mudanças de endereço de assinantes, a ONU pode surgir fisicamente em outra porta da mesma OLT ou até em outra OLT de outro POP.

O OLTAPI trata a ONU como uma entidade de primeira classe orientada a objetos baseada na **Tríade de Identidade**:
1. **Serial de Hardware (MAC/EPON/GPON):** Identificador físico imutável gravado de fábrica na EEPROM do modem.
2. **Vínculo Comercial no ERP:** Contrato do cliente (`contract_id`) e status (`ACTIVE`, `IN_STOCK`, `SUSPENDED`, `CANCELLED`).
3. **Circuit ID (Broadband Forum TR-101 / RFC 3046):** Localizador topológico dinâmico da porta física onde a luz acende:
   `{OLT-NAME} eth {slot}/{port}:{onu_id}:{vlan}`.

---

### 8.1 Cadastrar Equipamento no Inventário Global

Cadastra ou atualiza uma ONU no inventário central com coordenadas GPS para mapeamento GIS:

`POST /api/v1/onus`

```json
{
  "serial": "INCL99887766",
  "contract_id": "CTR-49102",
  "subscriber_name": "Provedor Turbo Fibra Ltda",
  "contract_status": "ACTIVE",
  "olt_id": "0191e4f2-51a8-7d84-a12b-3456789abcde",
  "port": "1/1",
  "onu_id": 4,
  "vlan": 150,
  "profile": "1G_DOWN_500M_UP",
  "latitude": -23.550520,
  "longitude": -46.633308,
  "description": "Cliente corporativo migrado"
}
```

**Resposta 201 Created:**
```json
{
  "id": "0191e4f3-a1b2-7c3d-8e4f-567890abcdef",
  "serial": "INCL99887766",
  "contract_id": "CTR-49102",
  "subscriber_name": "Provedor Turbo Fibra Ltda",
  "contract_status": "ACTIVE",
  "vlan": 150,
  "profile": "1G_DOWN_500M_UP",
  "latitude": -23.55052,
  "longitude": -46.633308,
  "current_olt_id": "0191e4f2-51a8-7d84-a12b-3456789abcde",
  "current_port": "1/1",
  "current_onu_id": 4,
  "circuit_id": "OLT-POP-CENTRO-01 eth 1/1:4:150",
  "_links": {
    "self": {
      "href": "/api/v1/onus/INCL99887766",
      "method": "GET",
      "description": "Consultar cadastro da ONU"
    },
    "history": {
      "href": "/api/v1/onus/INCL99887766/history",
      "method": "GET",
      "description": "Histórico de movimentações"
    }
  }
}
```

---

### 8.2 Motor de Auto-Recuperação e Conciliação Reativa de Campo

Quando um script de varredura ou worker de autofind detecta uma ONU ligada em uma porta PON, ele submete o evento ao endpoint de conciliação:

`POST /api/v1/onus/reconcile-field-event`

```json
{
  "serial": "INCL99887766",
  "detected_olt_id": "0191e4f5-9988-7766-5544-33221100aabb",
  "detected_port": "0/2",
  "detected_onu_id": 2,
  "latitude": -23.551000,
  "longitude": -46.634000,
  "reason": "Fusão invertida identificada na caixa CEO-04"
}
```

#### Comportamentos Automáticos do Motor:
- **Se Contrato ATIVO (`ACTIVE`):**
  1. Provisiona imediatamente a ONU na nova OLT/porta detectada (`detected_olt_id`, `detected_port`).
  2. Executa a limpeza física da posição antiga (desprovisiona a ONU fantasma da OLT/porta anterior para liberar slots e evitar colisões).
  3. Recalcula o Circuit ID Broadband Forum TR-101.
  4. Atualiza as coordenadas geográficas se fornecidas.
  5. Grava o evento imutável na Linha do Tempo do NOC (`ONUMigrationEvent`).
- **Se Contrato em ESTOQUE ou CANCELADO (`IN_STOCK` ou `CANCELLED`):**
  - **Bloqueia a conciliação** (`success: false`, `action_taken: "rejected_in_stock_onu"`).
  - Impede que um equipamento recolhido em campo herde credenciais ou VLANs do antigo titular antes de ser reassociado a um novo contrato no ERP.

---

### 8.3 Linha do Tempo Global para o NOC (Auditoria Noturna)

Os operadores do NOC que chegam pela manhã podem visualizar todas as auto-recuperações e manobras realizadas de forma transparente durante a madrugada:

`GET /api/v1/onus/history?limit=100`

```json
[
  {
    "id": "0191e4f6-1122-7788-9900-aabbccddeeff",
    "serial": "INCL99887766",
    "contract_id": "CTR-49102",
    "subscriber_name": "Provedor Turbo Fibra Ltda",
    "timestamp": "2026-09-12T04:15:30Z",
    "reason": "Cutover de anel óptico da madrugada - POP Centro",
    "from_olt_id": "0191e4f2-51a8-7d84-a12b-3456789abcde",
    "from_olt_name": "OLT-POP-CENTRO-01",
    "from_port": "1/1",
    "from_onu_id": 4,
    "from_circuit_id": "OLT-POP-CENTRO-01 eth 1/1:4:150",
    "to_olt_id": "0191e4f5-9988-7766-5544-33221100aabb",
    "to_olt_name": "OLT-HUAWEI-POP-SUL",
    "to_port": "0/2",
    "to_onu_id": 2,
    "to_circuit_id": "OLT-HUAWEI-POP-SUL eth 0/2:2:150",
    "status": "success",
    "details": "ONU detectada em nova posição física com contrato ativo. Migração e limpeza executadas com sucesso."
  }
]
```

---

Dúvidas ou sugestões operacionais? Abra uma issue ou contribua através do nosso [Guia de Contribuição](../CONTRIBUTING.md)!

