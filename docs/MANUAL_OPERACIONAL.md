# Manual Operacional & Guia de Integração para Provedores (OLTAPI)

Este manual destina-se a **engenheiros de rede**, **administradores de provedores de internet (ISPs)**, **técnicos de campo** e **desenvolvedores de ERPs de telecom** (como IXC Soft, MK-Auth, Voalle, SGP, RadiusNet, etc.) que desejam operar ou integrar com o **OLTAPI**.

---

## 🧭 Sumário

1. [Autenticação e Cabeçalhos](#1-autenticação-e-cabeçalhos)
2. [Cadastrando OLTs na API](#2-cadastrando-olts-na-api)
3. [Coletando Running-Config e Gerenciando Backups](#3-coletando-running-config-e-gerenciando-backups)
4. [Diagnóstico Óptico e Consulta de ONUs](#4-diagnóstico-óptico-e-consulta-de-onus)
5. [Descoberta (Autofind) e Provisionamento de ONUs](#5-descoberta-autofind-e-provisionamento-de-onus)
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
*(Exemplo: `/api/v1/olts/{id}/ports/1/onus` ou `/api/v1/olts/{id}/ports/0-1/onus`)*

```json
[
  {
    "onu_id": 1,
    "serial": "ITBS12345678",
    "status": "online",
    "distance": "1.2 km",
    "description": "Cliente_Joao_Silva"
  },
  {
    "onu_id": 2,
    "serial": "ITBS87654321",
    "status": "offline",
    "distance": null,
    "description": "Cliente_Maria_Santos"
  }
]
```

### 4.2 Consultar Potência Óptica (Sinal RX/TX em dBm)
`GET /api/v1/olts/{olt_id}/onus/{serial_or_id}/details`

```json
{
  "serial": "ITBS12345678",
  "status": "online",
  "rx_power_dbm": -19.45,
  "tx_power_dbm": 2.15,
  "olt_rx_power_dbm": -20.10,
  "distance_meters": 1240
}
```

---

## 5. Descoberta (Autofind) e Provisionamento de ONUs

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

Dúvidas ou sugestões operacionais? Abra uma issue ou contribua através do nosso [Guia de Contribuição](../CONTRIBUTING.md)!
