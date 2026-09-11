# Brainstorming: Estudo Técnico para Suporte às OLTs V-SOL (Linha V1600)
**Versão:** v11 (Arquitetura, Famílias V1600G/D, Sintaxe CLI, Parsers e Roadmap)  
**Data:** 2026-09-11  
**Autor:** Antigravity & Usuário  

---

## 1. Contexto e Relevância no Mercado Brasileiro

A **V-SOL (Guangzhou V-Solution)** conquistou enorme fatia de mercado no Brasil, principalmente entre **provedores regionais (ISPs pequenos e médios)**, devido a:
1. **Baixo Custo de Entrada (CAPEX):** Preço altamente competitivo se comparado a chassis modulares grandes.
2. **Operação Standalone ("Pizzabox"):** OLTs compactas de 1U ideais para POPs remotos e cidades menores.
3. **Compatibilidade Ampla de ONUs:** Boa interoperabilidade com ONUs de terceiros (Intelbras, Huawei, ZTE, Fiberhome e marcas OEM).

---

## 2. Famílias e Modelos Principais da V-SOL

| Linha | Tecnologia | Modelos Populares | Portas PON | Protocolo de Gerência |
| :--- | :--- | :--- | :---: | :--- |
| **V1600G Series** | **GPON** | V1600G0, V1600G1, V1600G1-B, V1600G2-B | 4, 8 ou 16 GPON | SSH (Porta 22) / Telnet (23) / Web / SNMP |
| **V1600D Series** | **EPON** | V1600D4, V1600D8, V1600D16 | 4, 8 ou 16 EPON | SSH / Telnet / Web / SNMP |
| **V1600X / Combo** | **XGS-PON / Combo** | V1600X-08, V1600GS | 8 a 16 PON | SSH / Telnet |

> [!NOTE]
> O foco prioritário deve ser a linha **V1600G (GPON)**, que representa a esmagadora maioria das ativações modernas de fibra óptica no Brasil.

---

## 3. Análise da Interface de Linha de Comando (CLI da V-SOL)

O sistema operacional da VSOL utiliza uma CLI proprietária com estrutura híbrida (semelhanças com Cisco IOS e Huawei):

### 3.1 Níveis de Acesso e Terminal
```text
OLT> enable
Password: ****
OLT# configure terminal
OLT(config)#
```
- Desativação de paginação:
  - `terminal length 0` ou `terminal page-break disable`

### 3.2 Descoberta de ONUs Não Autorizadas (*Autofind*)
- Comando de varredura global:
  ```text
  show ont autofind all
  ```
- *Saída típica na V1600G:*
  ```text
  -----------------------------------------------------------------------------
  Port       ONT-SN            Vendor     Model           Time
  -----------------------------------------------------------------------------
  gpon 0/1   VSOL12345678      VSOL       V2801SG         2026-09-11 10:15:30
  gpon 0/1   HWTC88776655      HWTC       EG8145V5        2026-09-11 10:18:22
  gpon 0/2   INCL99887766      INCL       110B            2026-09-11 10:20:05
  -----------------------------------------------------------------------------
  ```
- *Saída alternativa em firmwares anteriores:*
  ```text
  show ont unauth
  ```

### 3.3 Listagem de ONUs de uma Porta GPON
- Comando:
  ```text
  show ont info 0/1 all
  ```
- *Saída típica:*
  ```text
  -----------------------------------------------------------------------------
  Port    ONT-ID  Serial-Number     Status    Distance(m)  RxPower(dBm)  Description
  -----------------------------------------------------------------------------
  0/1     1       VSOL12345678      online    450          -19.50        Cliente_01
  0/1     2       VSOL87654321      offline   --           --            Cliente_02
  -----------------------------------------------------------------------------
  ```

### 3.4 Diagnóstico Óptico em Tempo Real
- Comando:
  ```text
  show ont optical-info 0/1 1
  ```
- *Saída típica:*
  ```text
  -----------------------------------------------------------------------------
  ONT optical info:
  -----------------------------------------------------------------------------
  Rx optical power(dBm)                 : -19.45
  Tx optical power(dBm)                 : 2.15
  OLT Rx optical power(dBm)             : -20.10
  Working temperature(C)                : 42.0
  Supply voltage(V)                     : 3.30
  -----------------------------------------------------------------------------
  ```

### 3.5 Provisionamento de ONU
- Comandos na interface da porta GPON:
  ```text
  interface gpon 0/{port}
  ont add {ont_id} sn-auth {serial} ont-lineprofile-id 1 ont-srvprofile-id 1 desc "{description}"
  exit
  ```
- Ou mapeamento com atribuição de VLAN direta:
  ```text
  interface gpon 0/{port}
  ont add {ont_id} sn-auth {serial} vlan {vlan} desc "{description}"
  exit
  write
  ```

### 3.6 Coleta de Running-Config e Backup
- Comando:
  ```text
  show running-config
  ```
- Gravação de alterações na memória flash:
  ```text
  write
  ```

---

## 4. O Que Precisa Ser Ajustado no OLTAPI

1. **Enum `OLTVendor`:**
   - Adicionar o valor `VSOL = "vsol"` em [app/models/olt.py](file:///Volumes/240/Code/oltapi/app/models/olt.py).
2. **Novo Driver `VSOLV1600Driver`:**
   - Pacote `app/drivers/vsol/vsol_v1600.py`.
   - Implementação de `BaseOLTDriver`.
   - Parsers puros para `show ont autofind`, `show ont info` e `show ont optical-info`.
3. **Mapeamento na `DriverFactory`:**
   - Mapear `vendor == OLTVendor.VSOL.value` para instanciar `VSOLV1600Driver`.
4. **Assistente de Bootstrap da VSOL:**
   - Geração de perfis DBA, line profile, criação de VLANs e gravação `write`.
5. **Cobertura de Testes Unitários:**
   - Criar `tests/unit/test_vsol_driver.py` com saídas reais de CLI da VSOL.
