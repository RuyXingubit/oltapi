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
8. [Disaster Recovery & Auditoria de Configuração](#8-disaster-recovery--auditoria-de-configuração)
9. [Sistema de Webhooks em Tempo Real & Eventos](#9-sistema-de-webhooks-em-tempo-real--eventos)
10. [Autofind Scanner em Segundo Plano (Monitoramento Autônomo)](#10-autofind-scanner-em-segundo-plano-monitoramento-autônomo--auto-conciliação)
11. [Persistência Relacional, Banco de Dados & Alembic Migrations](#11-persistência-relacional-banco-de-dados--migrações-com-alembic)
12. [Onboarding Seguro de OLTs em Produção (Brownfield) & Gestão de VLANs](#12-onboarding-seguro-de-olts-em-produção-brownfield--gestão-de-vlans)
   - 12.1 [Sincronização com Snapshot Baseline v0 Obrigatório (`POST /olts/{id}/sync`)](#121-sincronização-com-snapshot-baseline-v0-obrigatório)
   - 12.2 [Mapeamento e Criação de VLANs com Gravação Permanente na Flash (`GET/POST /olts/{id}/vlans`)](#122-mapeamento-e-criação-de-vlans-com-gravação-permanente-na-flash)
   - 12.3 [Consulta de Profiles de Linha e DBA (`GET /olts/{id}/profiles`)](#123-consulta-de-profiles-de-linha-e-dba)

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
> Fabricantes e modelos atualmente suportados na arquitetura de drivers:
> - **Fiberhome:** `vendor: "fiberhome"` / `model: "an5516"`, `"an5516-01"`, `"an5516-04"`, `"an5516-06"`, `"an6000"` (🟢 100% Homologado em Campo e Bancada Real)
> - **Intelbras:** `vendor: "intelbras"` / `model: "8820"`, `"8820i"`, `"g08"`, `"g16"`
> - **Huawei:** `vendor: "huawei"` / `model: "ma5800"`, `"ma5800-x2"`, `"ma5800-x7"`, `"ma5608t"`, `"ma5680t"`
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

## 9. Webhooks e Notificações Push para o ERP (HMAC SHA-256)

Para manter o ERP (IXC Soft, MK-Auth, Voalle, SGP, etc.) **100% sincronizado em tempo real** sem necessidade de polling constante, o OLTAPI dispõe de um subsistema de **Webhooks com Assinatura Criptográfica HMAC SHA-256**.

Sempre que uma ONU for auto-recuperada na madrugada (`onu.reconciled`), uma nova ONU acender na fibra (`onu.detected`) ou um backup for concluído, o OLTAPI envia uma requisição HTTP POST imediata para a URL cadastrada do ERP.

---

### 9.1 Cadastrar Webhook do ERP

`POST /api/v1/webhooks`

```json
{
  "url": "https://erp.provedor.com.br/api/v1/webhooks/oltapi",
  "description": "Sincronizador em Tempo Real - IXC Soft Matriz",
  "events": ["onu.reconciled", "onu.detected"],
  "secret": "whsec_minha_chave_secreta_super_segura_123"
}
```
*(Se o campo `secret` for omitido, o OLTAPI gerará automaticamente uma chave criptográfica segura com prefixo `whsec_`).*

---

### 9.2 Cabeçalhos de Segurança Enviados ao ERP

Cada entrega HTTP POST enviada pelo OLTAPI inclui:
- `X-OLTAPI-Signature`: `sha256=<hex_digest_hmac>`
- `X-OLTAPI-Event`: `onu.reconciled`
- `X-OLTAPI-Delivery`: `<uuid7_da_entrega>` (para deduplicação e idempotência no ERP)
- `X-OLTAPI-Timestamp`: `<timestamp_iso_utc>`
- `Content-Type`: `application/json`

---

### 9.3 Validando a Assinatura no ERP

#### Exemplo em Python (FastAPI / Flask / Django):
```python
import hashlib
import hmac

def validar_webhook(secret: str, raw_body_bytes: bytes, signature_header: str) -> bool:
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), raw_body_bytes, hashlib.sha256).hexdigest()
    # Comparação em tempo constante para evitar timing attacks
    return hmac.compare_digest(expected, signature_header)
```

#### Exemplo em PHP (Laravel / nativo):
```php
<?php
function validar_webhook(string $secret, string $rawBody, string $signatureHeader): bool {
    $expected = 'sha256=' . hash_hmac('sha256', $rawBody, $secret);
    return hash_equals($expected, $signatureHeader);
}
```

---

### 9.4 Exemplo de Payload do Evento `onu.reconciled`

```json
{
  "id": "0191e4f7-3344-7788-9900-112233445566",
  "event": "onu.reconciled",
  "timestamp": "2026-09-12T04:15:30.123456Z",
  "data": {
    "serial": "INCL99887766",
    "contract_id": "CTR-49102",
    "subscriber_name": "Provedor Turbo Fibra Ltda",
    "action_taken": "reconciled_cross_olt",
    "old_olt_id": "0191e4f2-51a8-7d84-a12b-3456789abcde",
    "old_olt_name": "OLT-POP-CENTRO-01",
    "old_port": "1/1",
    "old_onu_id": 4,
    "old_circuit_id": "OLT-POP-CENTRO-01 eth 1/1:4:150",
    "new_olt_id": "0191e4f5-9988-7766-5544-33221100aabb",
    "new_olt_name": "OLT-HUAWEI-POP-SUL",
    "new_port": "0/2",
    "new_onu_id": 2,
    "new_circuit_id": "OLT-HUAWEI-POP-SUL eth 0/2:2:150",
    "vlan": 150,
    "profile": "1G_DOWN_500M_UP",
    "latitude": -23.551,
    "longitude": -46.634,
    "reason": "Fusão invertida corrigida na caixa CEO-04"
  }
}
```

---

### 9.5 Teste de Conectividade e Auditoria de Entregas

- **Disparar Ping de Teste:** `POST /api/v1/webhooks/{id}/ping`
- **Consultar Histórico de Entregas Recentes:** `GET /api/v1/webhooks/deliveries?limit=50`

---

## 10. Autofind Scanner em Segundo Plano (Monitoramento Autônomo & Auto-Conciliação)

O **Autofind Scanner Service** transforma o OLTAPI em uma plataforma proativa de supervisão contínua da rede óptica. Um worker assíncrono em background varre ciclicamente todas as OLTs cadastradas, detecta ONUs que acabaram de acender na fibra e executa o roteamento inteligente:

```mermaid
graph LR
    Worker["Autofind Scanner Loop"] -->|Varredura Periódica| Driver["OLTDriver.list_unauthorized_onus"]
    Driver -->|ONUs Desautorizadas| Classifier{"Status no Inventário?"}
    Classifier -->|Contrato ATIVO| Reconcile["Auto-Reconciliação<br/>(Provisiona nova porta + limpa antiga)"]
    Classifier -->|Virgem / Não Cadastrada| WebhookDetected["Webhook: onu.detected"]
    Classifier -->|Estoque / Cancelada| Reject["Herança Bloqueada<br/>(Segurança)"]
    Reconcile -->|Broadband Forum TR-101| WebhookReconciled["Webhook: onu.reconciled"]
```

### 10.1 Proteção de Recursos das OLTs (Security-First)
- **Lock Assíncrono por OLT:** Evita concorrência e sobrecarga de CPU nos processadores de controle das OLTs. Varreduras periódicas nunca sobrepõem comandos de provisionamento manual.
- **Threadpool I/O Assíncrono:** Todas as chamadas de socket/SSH/telnet rodam via `asyncio.to_thread` sem travar o event loop da API.
- **Isolamento de Falhas:** Se uma OLT sofrer timeout ou ficar inacessível, o erro é contabilizado no ciclo e a varredura prossegue nas demais OLTs normalmente.
- **Piso Mínimo Defensivo:** Intervalo padrão de 60s, com piso rígido de 10s para evitar saturação.

### 10.2 Endpoints de Controle Operacional

| Endpoint | Método | Descrição |
|---|---|---|
| `/api/v1/scanner/status` | `GET` | Consulta status do worker (ativo/parado), intervalo e métricas acumuladas |
| `/api/v1/scanner/start` | `POST` | Inicia o worker em background |
| `/api/v1/scanner/stop` | `POST` | Interrompe graciosamente o worker em background |
| `/api/v1/scanner/run-now` | `POST` | Força uma varredura avulsa imediata com relatório completo (UUIDv7) |
| `/api/v1/scanner/interval` | `PATCH` | Ajusta dinamicamente a frequência de varredura em segundos (min: 10s) |

### 10.3 Exemplo de Resposta: `GET /api/v1/scanner/status`
```json
{
  "is_running": true,
  "interval_seconds": 60,
  "last_run_at": "2026-09-12T10:15:00.124Z",
  "last_run_duration_ms": 145.2,
  "last_cycle_id": "0191e5a2-3b4c-7def-8901-23456789abcd",
  "total_cycles": 120,
  "total_onus_detected": 15,
  "total_onus_reconciled": 4,
  "total_virgin_onus": 11,
  "total_errors": 0,
  "_links": {
    "self": { "href": "/api/v1/scanner/status", "method": "GET" },
    "start": { "href": "/api/v1/scanner/start", "method": "POST" },
    "stop": { "href": "/api/v1/scanner/stop", "method": "POST" },
    "run_now": { "href": "/api/v1/scanner/run-now", "method": "POST" }
  }
}
```

---

## 11. Persistência Relacional, Banco de Dados & Migrações com Alembic

O OLTAPI adota uma camada de persistência relacional com **SQLAlchemy 2.0** e versionamento canônico de esquema via **Alembic**, garantindo transações ACID, isolamento concorrente e integridade referencial com chaves primárias **UUIDv7**.

### 11.1 Arquitetura Docker Compose com PostgreSQL 16 (Paridade Absoluta Dev/Prod)

Para assegurar que o ambiente de desenvolvimento, homologação e produção comportem-se de maneira **100% idêntica** (mesmos drivers, tipos de dados, concorrência e transações DDL nas migrações), o `docker-compose.yml` provisiona a stack oficial com dois serviços coordenados:

```yaml
services:
  postgres:
    image: postgres:16-alpine
    container_name: oltapi_postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U oltuser -d oltapi"]

  oltapi:
    build: .
    container_name: oltapi
    depends_on:
      postgres:
        condition: service_healthy
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+psycopg2://oltuser:oltpassword@postgres:5432/oltapi
```

#### Inicialização da Stack:
```bash
docker compose up -d --build
```

Ao iniciar, a API aguarda o PostgreSQL atingir o estado saudável (`service_healthy`) e executa automaticamente as migrações do Alembic:
```text
oltapi  | INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
oltapi  | INFO  [alembic.runtime.migration] Will assume transactional DDL.
oltapi  | INFO  [alembic.runtime.migration] Running upgrade  -> cf1f56210add, initial_schema
```

#### Acesso Direto ao Banco PostgreSQL via Terminal:
Para inspecionar as tabelas, índices e registros diretamente pelo terminal do container:
```bash
docker exec -it oltapi_postgres psql -U oltuser -d oltapi
```
Comandos úteis no `psql`:
- `\dt`: Lista todas as 7 tabelas gerenciadas pelo Alembic (`olts`, `onus_inventory`, `onus_history`, `backups_metadata`, `webhook_subscriptions`, `webhook_deliveries`, `alembic_version`).
- `SELECT * FROM olts;`: Consulta OLTs cadastradas.
- `SELECT * FROM onus_inventory;`: Consulta ONUs catalogadas.

---

### 11.2 Configuração da Base de Dados

A persistência é configurada via variável de ambiente `DATABASE_URL` no arquivo `.env`:

```bash
# Modo Oficial / Produção / Docker Compose: PostgreSQL 16
DATABASE_URL="postgresql+psycopg2://oltuser:oltpassword@postgres:5432/oltapi"

# Modo Embarcado / Testes Locais Leves: SQLite WAL
DATABASE_URL="sqlite:///./data/oltapi.db"

# Ativar logs SQL de depuração (opcional, padrão: false)
DATABASE_ECHO=false
```

> [!TIP]
> **Performance no SQLite (WAL Mode):**
> Caso seja necessário rodar sem Docker diretamente em SQLite, o OLTAPI ativa automaticamente no evento de conexão:
> - `PRAGMA journal_mode=WAL;` (permite múltiplas leituras concorrentes sem bloquear escritas).
> - `PRAGMA foreign_keys=ON;` (garante integridade referencial rígida).
> - `PRAGMA synchronous=NORMAL;` (excelente throughput sem risco de corrupção).

---

### 11.3 Migração Transparente de Dados Legados (Zero Downtime)

Caso seu ambiente possua arquivos JSON legados (`olts.json`, `onus_inventory.json`, `onus_history.json`, `webhooks.json`, `backups_metadata.json`), o OLTAPI na inicialização:
1. Executa o comando canônico `alembic upgrade head` para certificar que todas as tabelas e índices estão atualizados.
2. Identifica os arquivos JSON legados e importa todos os registros para as tabelas relacionais de forma **idempotente** (sem duplicatas).
3. Renomeia os arquivos antigos com sufixo `.migrated` para manter histórico seguro.

### 11.4 Operação com o CLI do Alembic

Para administradores e engenheiros de DevOps que desejam manipular migrações via terminal:

```bash
# 1. Aplicar todas as migrações pendentes até a versão mais recente
alembic upgrade head

# 2. Verificar histórico de revisões aplicadas
alembic history --verbose

# 3. Consultar versão atual da base de dados
alembic current

# 4. Criar uma nova migração a partir de alterações no modelo SQLAlchemy
alembic revision --autogenerate -m "adicionar_campo_xpto"

# 5. Reverter a última migração aplicada (Rollback)
alembic downgrade -1
```

> [!NOTE]
> Para compatibilidade total entre SQLite e PostgreSQL, o arquivo `alembic/env.py` está configurado com `render_as_batch=True`, permitindo alterações de tabelas com constraints sem limitações de engine.

### 11.5 Ambiente de Testes Fidedigno com Testcontainers (PostgreSQL 16)

Para garantir paridade absoluta com a infraestrutura de produção, o OLTAPI integra **Testcontainers** (`testcontainers[postgres]`). 

Ao executar a suite de testes:
```bash
pytest tests/ -v
```
1. O Pytest se comunica com o Docker daemon local e inicializa uma instância limpa de `postgres:16-alpine`.
2. Executa todas as migrações canônicas do Alembic (`alembic upgrade head`) diretamente no container efêmero.
3. Roda todos os 143 testes de API, conciliação, inventário e drivers contra o banco PostgreSQL real.
4. Ao final da suite, o container é destruído automaticamente sem deixar processos órfãos.

*(Caso o Docker não esteja em execução na máquina do desenvolvedor, a suite ativa um fallback transparente para SQLite WAL, mantendo o fluxo de trabalho ágil).*

---

## 12. Onboarding Seguro de OLTs em Produção (Brownfield) & Gestão de VLANs

Na maioria dos provedores, a OLT já está em operação há meses ou anos, atendendo centenas ou milhares de clientes com VLANs e perfis configurados manualmente via CLI. O OLTAPI implementa o protocolo de **Onboarding Brownfield** seguro e auditável.

> [!CAUTION]
> **Segurança em Primeiro Lugar:** O OLTAPI **NUNCA** altera ou provisiona nada em uma OLT sem antes gerar um **Snapshot de Baseline v0** com cálculo de integridade SHA-256 e persistência em banco relacional.

### 12.1 Sincronização com Snapshot Baseline v0 Obrigatório

O endpoint de sincronização executa em uma única operação atômica:
1. **Snapshot Preventivo Obrigatório (Baseline v0):** Coleta a running-config integral da OLT, calcula hash SHA-256 e armazena no histórico de backups.
2. **Varredura Completa do Chassi:** Descobre todas as ONUs já autorizadas e ativas em todos os slots/portas PON (ex: `LST-ONU:::1::;` na Fiberhome).
3. **Ingestão Reversa & Circuit ID TR-101:** Cadastra automaticamente as ONUs no inventário relacional com status `ACTIVE` e calcula o identificador físico padronizado Broadband Forum TR-101 / RFC 3046 (`{OLT_NAME} eth {PORT}:{ONU_ID}:{VLAN}`).
4. **Mapeamento de VLANs:** Cataloga todas as VLANs de serviço existentes no concentrador.

#### Requisição:
`POST /api/v1/olts/{id}/sync`

```http
POST /api/v1/olts/01a096d1-674b-7595-b5ab-f4adca3060bc/sync HTTP/1.1
Host: api.provedor.com.br
X-API-Key: sua-chave-secreta-aqui
```

#### Resposta de Sucesso (`200 OK`):
```json
{
  "olt_id": "01a096d1-674b-7595-b5ab-f4adca3060bc",
  "olt_name": "OLT-FIBERHOME-CENTRAL",
  "baseline_backup_id": "01a096d1-6789-7def-8901-123456789abc",
  "total_onus_discovered": 384,
  "new_onus_registered": 384,
  "existing_onus_updated": 0,
  "vlans_discovered": [100, 200, 300, 400],
  "duration_ms": 1240.5,
  "message": "Sync concluído com sucesso. 384 novas ONUs cadastradas e 0 atualizadas.",
  "_links": {
    "olt": {
      "href": "/api/v1/olts/01a096d1-674b-7595-b5ab-f4adca3060bc",
      "method": "GET"
    },
    "vlans": {
      "href": "/api/v1/olts/01a096d1-674b-7595-b5ab-f4adca3060bc/vlans",
      "method": "GET"
    },
    "baseline_backup": {
      "href": "/api/v1/olts/01a096d1-674b-7595-b5ab-f4adca3060bc/backups/01a096d1-6789-7def-8901-123456789abc/download",
      "method": "GET"
    }
  }
}
```

> [!TIP]
> Execuções repetidas do endpoint `/sync` são **idempotentes**: se uma ONU já existe no inventário, seus dados de porta, slot e status são atualizados sem duplicação de registros.

---

### 12.2 Mapeamento e Criação de VLANs com Gravação Permanente na Flash

A API permite controlar as VLANs de serviço e portas de uplink da OLT, garantindo que toda alteração seja imediatamente comitada na memória flash não-volátil (`save_running_config`), evitando perda de dados caso a OLT reinicie ou haja queda de energia no POP.

#### Listar VLANs configuradas na OLT:
`GET /api/v1/olts/{id}/vlans`

```json
[
  {
    "vlan_id": 100,
    "name": "INTERNET_PPPOE",
    "description": "VLAN para clientes banda larga residencial",
    "tagged_ports": ["1/19/1", "1/19/2"],
    "_links": {
      "self": {"href": "/api/v1/olts/01a096d1-674b-7595-b5ab-f4adca3060bc/vlans", "method": "GET"}
    }
  },
  {
    "vlan_id": 200,
    "name": "VOIP_CORPORATIVO",
    "description": "Telefonia SIP",
    "tagged_ports": ["1/19/1"]
  }
]
```

#### Criar nova VLAN de serviço com gravação flash:
`POST /api/v1/olts/{id}/vlans`

```json
{
  "vlan_id": 500,
  "name": "VLAN_DEDICADO_CORP",
  "description": "Circuito dedicado cliente corporativo",
  "tagged_uplink_ports": ["1/19/1"]
}
```

**Resposta (`201 Created`):**
```json
{
  "success": true,
  "olt_id": "01a096d1-674b-7595-b5ab-f4adca3060bc",
  "vlan_id": 500,
  "name": "VLAN_DEDICADO_CORP",
  "message": "VLAN 500 criada e gravada na flash com sucesso na OLT OLT-FIBERHOME-CENTRAL.",
  "_links": {
    "vlans": {"href": "/api/v1/olts/01a096d1-674b-7595-b5ab-f4adca3060bc/vlans", "method": "GET"},
    "olt": {"href": "/api/v1/olts/01a096d1-674b-7595-b5ab-f4adca3060bc", "method": "GET"}
  }
}
```

---

### 12.3 Consulta de Profiles de Linha e DBA

Para que o provisionador ou ERP consulte os perfis de velocidade e tráfego pré-configurados no concentrador antes de ativar uma nova ONU:

#### Requisição:
`GET /api/v1/olts/{id}/profiles`

```json
[
  {
    "name": "LINE_500M",
    "profile_type": "line",
    "details": "Plano Banda Larga 500 Mbps Downloader",
    "_links": {
      "olt": {"href": "/api/v1/olts/01a096d1-674b-7595-b5ab-f4adca3060bc", "method": "GET"}
    }
  },
  {
    "name": "DBA_DEFAULT",
    "profile_type": "dba",
    "details": "Dynamic Bandwidth Allocation padrão"
  }
]
```

---

Dúvidas ou sugestões operacionais? Abra uma issue ou contribua através do nosso [Guia de Contribuição](https://github.com/RuyXingubit/oltapi/blob/master/CONTRIBUTING.md)!
