# Brainstorming: API Unificada de Provisionamento Multi-OLT
**Versão:** v1 (Visão Geral, Requisitos e Abstração de Drivers)  
**Data:** 2026-09-10  
**Autor:** Antigravity & Usuário  

---

## 1. Objetivo do Projeto
Criar uma API REST simples, segura e padronizada para que sistemas externos (ERPs de provedor, scripts de automação ou técnicos via Postman/cURL) possam realizar o ciclo de vida básico de provisionamento de ONUs/ONTs em diferentes fabricantes e modelos de OLT, sem precisar conhecer a sintaxe CLI ou particularidades de cada equipamento.

---

## 2. Equipamentos no Escopo Inicial de Testes
O ambiente conta com disponibilidade para testes reais dos seguintes modelos:
1. **Intelbras 8820** (GPON)
2. **Intelbras 4840** (EPON/GPON)
3. **Intelbras G16** (GPON 16 portas)
4. **Huawei SmartAX / MA5800 (X7 e X2)** (GPON)
5. **Parks Fiberlink** (GPON)

---

## 3. Desafios Principais Identificados

### 3.1 Heterogeneidade de Protocolos e Comandos
- **Huawei (MA5800 X7/X2):** VRP CLI poderoso via SSH/Telnet, SNMP rico, suporte a perfis (`ont-lineprofile`, `ont-srvprofile`).
- **Intelbras G16:** CLI própria / SNMP / Web. Comandos específicos de provisionamento de GPON.
- **Intelbras 8820 / 4840:** Interfaces CLI distintas baseadas em chipsets específicos (ex: Broadcom/Fiberhome/Zhone dependendo da série/firmware).
- **Parks:** CLI baseada no sistema CLIOS / Telnet / SSH / SNMP.

### 3.2 Segurança e Credenciais
- OLTs são a espinha dorsal de rede do provedor. A API não deve expor senhas em texto puro nem permitir injeção de comandos (CLI command injection).
- Autenticação na API (API Key ou Bearer Token) para isolar o acesso do ERP e dos técnicos.
- Gestão centralizada de inventário das OLTs (IP, porta, credenciais criptografadas) para que o ERP apenas envie `olt_id`.

---

## 4. Arquitetura Proposta: Driver / Adapter Pattern

```
           +-----------------------------+
           |     ERP / Postman / App     |
           +--------------+--------------+
                          | (JSON / REST)
                          v
           +-----------------------------+
           |       API Gateway / Core    |
           | - Auth (Token/API Key)      |
           | - Validação de Entrada      |
           | - Orquestrador de Tarefas   |
           +--------------+--------------+
                          |
                          v
           +-----------------------------+
           |    Driver Factory / Router  |
           +--------------+--------------+
                          |
       +------------------+------------------+------------------+
       |                  |                  |                  |
       v                  v                  v                  v
+--------------+   +--------------+   +--------------+   +--------------+
| HuaweiDriver |   | IntelbrasG16 |   | Intelbras8820|   | ParksDriver  |
|  (SSH/CLI)   |   | (CLI/SNMP)   |   |   (CLI/SSH)  |   |  (CLI/SSH)   |
+--------------+   +--------------+   +--------------+   +--------------+
       |                  |                  |                  |
       +------------------+------------------+------------------+
                          |
                          v
                OLTs Físicas na Rede
```

### Contrato Unificado (Interface Básica de Driver)
Cada driver deve implementar uma interface comum:
- `find_unauthorized(olt)`: Lista ONUs não autorizadas / descobertas na PON.
- `provision_onu(olt, payload)`: Provisiona a ONU com perfil, VLAN, serial e modo.
- `get_onu_status(olt, serial_ou_id)`: Consulta status operacional e potência óptica (Rx/Tx dBm).
- `delete_onu(olt, serial_ou_id)`: Remove ou desprovisiona a ONU da OLT.

---

## 5. Operações do MVP (Foco em Simplicidade - YAGNI)
1. **Descoberta:** `GET /api/v1/olts/{id}/unauthorized` -> Retorna serial, slot/pon e modelo das ONUs soltas na rede.
2. **Provisionamento:** `POST /api/v1/olts/{id}/onus` -> Recebe JSON com `serial`, `pon`, `vlan`, `profile` e aplica os comandos no equipamento.
3. **Diagnóstico Óptico:** `GET /api/v1/olts/{id}/onus/{serial}/signal` -> Retorna sinal óptico Rx/Tx para o técnico validar no ato.
4. **Remoção/Cancelamento:** `DELETE /api/v1/olts/{id}/onus/{serial}` -> Libera a porta e desassocia a ONU.

---

## 6. Próximos Passos no Brainstorming
1. Definir a stack tecnológica (linguagem/framework) com base em facilidade de concorrência e bibliotecas de SSH/SNMP robustas.
2. Definir o mecanismo de persistência e cadastro das OLTs (Banco de dados relacional com UUIDv7 ou arquivo de configuração simplificado para início).
3. Escolher o primeiro equipamento para ser o piloto/protótipo de ponta a ponta (ex: Intelbras G16 ou Huawei).
