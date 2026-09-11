# Brainstorming: Especificação Técnica da OLT V-SOL V1600GT
**Versão:** v12 (Hardware de Bancada: V1600GT, Portas PON, Uplinks 10G e CLI)  
**Data:** 2026-09-11  
**Autor:** Antigravity & Usuário  

---

## 1. Hardware de Bancada: V-SOL V1600GT Series
O equipamento disponível fisicamente para validação é o **V-SOL V1600GT**:
- **Família:** GPON OLT Pizza-box Standalone 1U.
- **Sufixo "GT":** Indica portas PON GPON de alta capacidade com uplinks ópticos **10G SFP+** (`xe` / `tg` / `10ge`).
- **Capacidade PON:** Tipicamente 4, 8 ou 16 portas GPON (Classe B+ / C+ / C++).
- **Taxa de Divisão (Split):** 1:128 por porta PON (até 1024 ONUs em 8 PONs, ou 2048 em 16 PONs).

---

## 2. Padrões de CLI e Terminal na V1600GT

### 2.1 Conexão e Sessão
- **Acesso:** SSH (porta 22) ou Telnet (porta 23).
- **Usuário Padrão de Fábrica:** `admin` / `admin`.
- **Modo de Paginação:**
  ```text
  terminal length 0
  ```

### 2.2 Descoberta de ONUs Não Autorizadas (*Autofind*)
- **Comando:**
  ```text
  show ont autofind all
  ```
- **Formato de Saída V1600GT:**
  ```text
  -----------------------------------------------------------------------------
  Port       ONT-SN            Vendor     Model           Time
  -----------------------------------------------------------------------------
  gpon 0/1   VSOL12345678      VSOL       V2801SG         2026-09-11 10:15:30
  gpon 0/1   HWTC88776655      HWTC       EG8145V5        2026-09-11 10:18:22
  gpon 0/2   INCL99887766      INCL       110B            2026-09-11 10:20:05
  -----------------------------------------------------------------------------
  ```

### 2.3 Listagem de ONUs Cadastradas
- **Comando:**
  ```text
  show ont info 0/{pon} all
  ```
- **Formato de Saída V1600GT:**
  ```text
  -----------------------------------------------------------------------------
  Port    ONT-ID  Serial-Number     Status    Distance(m)  RxPower(dBm)  Description
  -----------------------------------------------------------------------------
  0/1     1       VSOL12345678      online    450          -19.50        Cliente_01
  0/1     2       VSOL87654321      offline   --           --            Cliente_02
  -----------------------------------------------------------------------------
  ```

### 2.4 Diagnóstico Óptico de Nível de Fibra (Rx/Tx)
- **Comando:**
  ```text
  show ont optical-info 0/{pon} {ont_id}
  ```
- **Formato de Saída:**
  ```text
  ONT optical info:
  Rx optical power(dBm)                 : -19.45
  Tx optical power(dBm)                 : 2.15
  OLT Rx optical power(dBm)             : -20.10
  ```

### 2.5 Provisionamento na V1600GT
- **Comandos:**
  ```text
  configure terminal
  interface gpon 0/{pon}
  ont add {ont_id} sn-auth {serial} vlan {vlan} desc "{desc}"
  exit
  write
  ```

---

## 3. Estrutura do Driver no OLTAPI
- Classe: `VSOLV1600Driver`
- Compatível com modelos: `V1600GT`, `V1600G`, `V1600G1`, `V1600G2`.
- Parametrização para suportar tanto portas GPON `0/1` a `0/16` quanto interfaces de uplink 10G (`xe 0/1`, `tg 0/1` ou portas GE).
