# Brainstorming: Especificação Técnica do Driver ZTE (ZXA10 C300 / C320 / C600)
**Versão:** v14 (Arquitetura ZXROS, Nomenclatura gpon-olt_1/S/P, Parsers e Provisionamento)  
**Data:** 2026-09-11  
**Autor:** Antigravity & Usuário  

---

## 1. Contexto do Fabricante ZTE
A **ZTE** é uma das maiores gigantes globais de telecomunicações. No Brasil, tem presença expressiva em:
- **Redes Neutras:** V.tal, FiBrasil e operadoras atacadistas.
- **ISPs Médios e Grandes:** Chassis **ZXA10 C300** (alta densidade) e **ZXA10 C320** (mini-chassis compacto de 2 slots, muito popular em POPs).
- **Linha Titan (C600 / C620 / C650):** Plataformas modernas XGS-PON / Combo PON.

---

## 2. Sistema Operacional ZXROS e Sintaxe CLI

### 2.1 Conexão e Sessão
- **Acesso:** SSH (porta 22) ou Telnet (porta 23).
- **Prompt:** `ZXAN#`, `ZXAN(config)#`.
- **Desativação de Paginação:**
  ```text
  terminal length 0
  ```

### 2.2 Hierarquia de Portas GPON no ZXROS
A ZTE utiliza uma identificação modular de portas no formato:
`gpon-olt_1/{slot}/{port}` (ou `1/{slot}/{port}`)
E para instâncias de ONUs:
`gpon-onu_1/{slot}/{port}:{onu_id}`

### 2.3 Varredura de ONUs Não Autorizadas (*Autofind*)
- **Comando:**
  ```text
  show gpon onu uncfg
  ```
- **Saída Típica ZXROS:**
  ```text
  OnuIndex               Sn                  State
  ---------------------------------------------------------------------
  gpon-onu_1/1/1:1       ZTEGC1234567        uncfg
  gpon-onu_1/1/2:1       ZTEGC8765432        uncfg
  gpon-onu_1/2/1:1       HWTC11223344        uncfg
  ---------------------------------------------------------------------
  ```

### 2.4 Consulta de ONUs em uma Porta PON
- **Comando:**
  ```text
  show gpon onu state gpon-olt_1/{slot}/{port}
  ```
- **Saída Típica ZXROS:**
  ```text
  OnuIndex               AdminState  OperState    RxPower(dBm)  SN
  ---------------------------------------------------------------------
  gpon-onu_1/1/1:1       enable      online       -19.50        ZTEGC1234567
  gpon-onu_1/1/1:2       enable      offline      --            ZTEGC8765432
  ---------------------------------------------------------------------
  ```

### 2.5 Diagnóstico Óptico (Rx/Tx em dBm)
- **Comando:**
  ```text
  show gpon onu optical-info gpon-onu_1/{slot}/{port}:{onu_id}
  ```
- **Saída Típica ZXROS:**
  ```text
  optical-info:
  Rx optical power: -19.45 dBm
  Tx optical power: 2.15 dBm
  OLT Rx optical power: -20.10 dBm
  ```

### 2.6 Provisionamento de ONU no ZXROS
- **Sequência de Comandos:**
  ```text
  configure terminal
  interface gpon-olt_1/{slot}/{port}
  onu {onu_id} type auto sn {serial}
  exit
  interface gpon-onu_1/{slot}/{port}:{onu_id}
  name "{description}"
  tcont 1 profile 1G
  gemport 1 tcont 1
  service-port 1 vport 1 user-vlan {vlan} vlan {vlan}
  exit
  write
  ```

### 2.7 Coleta de Running-Config e Gravação
- **Running Config:** `show running-config`
- **Gravação:** `write` ou `write memory`

---

## 3. Integração no OLTAPI
1. **Enum `OLTVendor`:** Adicionar `ZTE = "zte"` em [app/models/olt.py](file:///Volumes/240/Code/oltapi/app/models/olt.py).
2. **Driver `ZTEDriver`:** Criar em `app/drivers/zte/zte_zxros.py`.
3. **Fábrica `DriverFactory`:** Mapear `vendor == OLTVendor.ZTE.value` reconhecendo modelos `c300`, `c320`, `c600`, `c620` e ZTE genérica.
4. **Testes Unitários:** Suíte completa em `tests/unit/test_zte_driver.py`.
