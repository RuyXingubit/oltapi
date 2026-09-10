# Brainstorming: Suporte aos Concentradores Intelbras OLT G08 e G16
**Versão:** v7 (Arquitetura, Comandos CLI e Assistente Autoconfig G08/G16)  
**Data:** 2026-09-10  
**Autor:** Antigravity & Usuário  

---

## 1. Contexto e Equipamentos
Após o piloto da **Intelbras 8820 / 8820i**, expandimos o suporte para a família de chassis modernos **Intelbras G-Series**:
1. **Intelbras OLT G08:** 8 portas GPON (interface `gpon 0/1` a `0/8`).
2. **Intelbras OLT G16:** 16 portas GPON (interface `gpon 0/1` a `0/16`).

Ambos os concentradores compartilham o mesmo sistema operacional e sintaxe de comandos (*G-Series CLI*), diferindo principalmente pela quantidade de portas PON.

---

## 2. Diferenças Arquiteturais de CLI (8820 vs G-Series G08/G16)

| Funcionalidade | Intelbras 8820 / 8820i | Intelbras G08 / G16 |
| :--- | :--- | :--- |
| **Arquitetura de Perfis** | `bridge add`, `bridge-profile add`, `bridge-profile bind` | `deploy profile dba`, `deploy profile vlan`, `deploy profile line` |
| **Identificadores de Perfil** | Nomes de bridge (`default`, `default-router`) | `aim <id> name <nome>` |
| **Uplink** | `bridge add <uplink> downlink vlan <vlan>` | `uplink add <port> vlan <vlan>` |
| **Modo de Tráfego** | `eth 1` ou `router` | `mapping 1 port veip vlan X` (Router) ou `mapping 1 port eth 1 vlan X` (Bridge) |
| **Auto-Provisionamento** | `auto-service enable` | `ont auto-config name ... line ... interface gpon 0/X` + `ont-find interface gpon all` |
| **Varredura Descoberta** | `show gpon onu uncfg` | `show ont autofind all` / `show ont unassigned` |
| **Diagnóstico Óptico** | `show gpon onu optical-info` | `show ont optical-info 0/X Y` |

---

## 3. Especificação do Driver Intelbras G-Series (`IntelbrasGSeriesDriver`)

O driver atenderá tanto a **G08** quanto a **G16** parametrizando o total de portas (`total_pons = 8` ou `total_pons = 16`):

### 3.1 Script de Bootstrap / Autoconfiguração Oficial
1. **DBA Profile:**
   ```text
   deploy profile dba
   aim 1 name DBA-DEFAULT
   type 4 max 1200000
   active
   exit
   ```
2. **VLAN Profiles:**
   - Criação de perfis de translação de VLAN (`translate old-vlan X new-vlan X`).
3. **Line Profiles:**
   - Associação de TCONT 1 ao DBA 1.
   - GEM Port 1 com mapeamento VEIP (Router) ou ETH (Bridge).
4. **Regras de Auto-Configuração por Porta PON:**
   - `ont-find interface gpon all`
   - `ont-find list-age time 60 interface gpon all`
   - Para cada PON $m$ (1 a 8 no G08, 1 a 16 no G16):
     - `ont auto-config name ROUTER-VLAN-{vlan} line {aim_line} interface gpon 0/{m}`
     - `ont auto-config name TERCEIROS-{m} all-ont line {aim_line} interface gpon 0/{m}`
5. **Gravação:**
   - `write`

---

## 4. Integração na DriverFactory
A `DriverFactory` resolverá automaticamente:
- `model` contendo `"g08"` ou `"g8"` ➔ `IntelbrasGSeriesDriver(total_pons=8, model_name="G08")`
- `model` contendo `"g16"` ➔ `IntelbrasGSeriesDriver(total_pons=16, model_name="G16")`
