# Brainstorming: Wizard de Inicialização / Provisionamento Zero-Touch (Baseado na Ferramenta Oficial Intelbras)
**Versão:** v6 (Análise do Autoconfig Intelbras 8820i / G08 / G16 e Proposta de Bootstrap API)  
**Data:** 2026-09-10  
**Autor:** Antigravity & Usuário  

---

## 1. Contexto e Problema de Negócio
Muitos provedores contam com técnicos iniciantes ou equipes de NOC que não dominam a sintaxe complexa de CLI de OLTs virgens (recém-saídas da caixa ou resetadas).
Geralmente, o técnico consegue apenas plugar o cabo de gerência, definir o IP/usuário/senha padrão e cadastrar na API. A OLT, no entanto, ainda não possui:
- Configuração de portas de Uplink.
- VLANs de serviço e Bridges.
- Perfis de Bridge, perfis DBA e regras de tráfego.
- Ativação do serviço de Auto-Provisionamento (*auto-service*).

A Intelbras mantém uma ferramenta oficial de autoconfiguração:  
`https://olts-guias-e-manuais.intelbras.com.br/autoconfig-gpon-itbs/dist/index.html#/8820i`

---

## 2. Engenharia Reversa da Ferramenta Oficial Intelbras (8820i)

Analisamos o bundle da ferramenta oficial da Intelbras (`index-6b4740f9.js`). O assistente oficial opera sob dois modos principais:

### Modo 1: Apenas uma VLAN (Single VLAN para todas as PONs)
1. **Criação da Bridge de Uplink:**
   ```text
   bridge add <uplink_port> downlink vlan <vlan_id> <tagged/untagged>
   ```
2. **Criação dos Perfis de Bridge (Modo Bridge vs Modo Router):**
   ```text
   bridge-profile add default downlink vlan <vlan_id> tagged eth 1
   bridge-profile add default-router downlink vlan <vlan_id> tagged router
   ```
3. **Associação (Bind) para todas as ONUs homologadas da Intelbras:**
   ```text
   bridge-profile bind add default device intelbras-110
   bridge-profile bind add default device intelbras-110b
   bridge-profile bind add default device intelbras-110g
   bridge-profile bind add default device intelbras-default
   bridge-profile bind add default-router device intelbras-r1
   bridge-profile bind add default-router device intelbras-121w
   bridge-profile bind add default-router device intelbras-142ng
   bridge-profile bind add default-router device intelbras-142nw
   bridge-profile bind add default-router device intelbras-1420g
   bridge-profile bind add default-router device intelbras-120ac
   bridge-profile bind add default-router device intelbras-121ac
   bridge-profile bind add default-router device intelbras-1200r
   bridge-profile bind add default-router device intelbras-ax1800
   bridge-profile bind add default-router device intelbras-ax1800v
   ```
4. **Habilitação do Auto-Provisionamento na OLT:**
   ```text
   onu set auto
   auto-service enable
   yes
   onu show refresh
   write
   ```

### Modo 2: Uma VLAN por PON (VLANs dedicadas de PON 1 a 8)
Para cada porta PON $m$ (1 a 8):
```text
bridge add <uplink_port> downlink vlan <vlan_pon_m> tagged
bridge-profile add gpon{m}-default downlink vlan <vlan_pon_m> tagged eth 1
bridge-profile add gpon{m}-default-router downlink vlan <vlan_pon_m> tagged router
bridge-profile bind add gpon{m}-default device intelbras-110b gpon {m}
bridge-profile bind add gpon{m}-default-router device intelbras-121w gpon {m}
...
```

---

## 3. Análise de Segurança & Prós e Contras

### 3.1 Avaliação de Segurança (Diretriz Global)
- **Aumenta ou diminui a segurança?**
  - **Aumenta a segurança:** Reduz drasticamente o erro humano na configuração manual de VLANs, evita portas abertas indevidamente, garante que o `auto-service` seja configurado de acordo com as boas práticas da fabricante e força o salvamento em memória (`write memory`).
  - **Cuidados Mandatórios:**
    1. A OLT deve passar por uma confirmação explícita do técnico antes de aplicar (evitar sobrescrever acidentalmente uma OLT que já está em produção).
    2. O endpoint deve oferecer um modo **Dry-Run / Preview** (retornar os comandos para conferência antes de aplicar na caixa física).

---

## 4. Proposta de Design na API (Endpoints de Bootstrap)

### 4.1 Endpoint 1: Preview do Script (Simulação / Dry-Run)
`POST /api/v1/olts/{id}/bootstrap/preview`
- **Objetivo:** O ERP ou técnico no Postman envia os parâmetros básicos (ex: porta de uplink, VLAN única ou lista de VLANs por PON, modo bridge/router) e recebe a lista exata de comandos CLI que serão executados.

### 4.2 Endpoint 2: Aplicação na OLT Física (Execução)
`POST /api/v1/olts/{id}/bootstrap/apply`
- **Payload:**
  ```json
  {
    "mode": "single_vlan",
    "uplink_port": "1",
    "vlan": 100,
    "default_onu_mode": "router"
  }
  ```
- **Fluxo:**
  1. A API verifica se a OLT existe e se está acessível.
  2. Executa a sequência com segurança via SSH/CLI.
  3. Salva a configuração na memória permanente da OLT.
  4. Gera automaticamente um backup inicial (com **UUIDv7**) como ponto de restauração imediato.
