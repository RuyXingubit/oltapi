# Brainstorming: Especificação Técnica do Driver Fiberhome (AN5516 / AN6000)
**Versão:** v10 (Arquitetura TL1, Estrutura de Mensagens Bellcore, Parsers e Bootstrap)  
**Data:** 2026-09-11  
**Autor:** Antigravity & Usuário  

---

## 1. Contexto do Fabricante Fiberhome
A **Fiberhome** é uma das maiores fornecedoras de infraestrutura de telecomunicações do Brasil, amplamente utilizada por operadoras regionais e redes neutras.
Principais famílias de OLT:
- **AN5516 Series:** AN5516-01 (16 slots), AN5516-06 (6 slots), AN5516-04 (4 slots / mini-chassis).
- **AN6000 Series:** AN6000-7, AN6000-15, AN6000-17.

---

## 2. Protocolo de Gerência: TL1 (Transaction Language 1)
Diferente da Intelbras e Huawei (que utilizam primariamente emulação de terminal CLI estilo Cisco/VRP), a Fiberhome possui como padrão nativo de automação de engenharia e NMS (UNM2000 / ANM2000) o protocolo **TL1** (Porta TCP 3337 ou sobre SSH).

### 2.1 Vantagens do TL1 para o OLTAPI
1. **Determinismo Estruturado:** As respostas chegam no formato Bellcore delimitado por ponto-e-vírgula (`;`), eliminando problemas de paginação de terminal (`--More--`) ou prompts variáveis.
2. **Respostas com Código de Sucesso/Falha Explícito:**
   - `COMPLD` (Completed com sucesso)
   - `DENY` (Acesso negado)
   - `PRTL` (Completado parcialmente)

---

## 3. Matriz de Comandos TL1

### 3.1 Login e Logout
- **Login:** `LOGIN:::1::UN={user},PWD={password};`
- **Logout:** `LOGOUT:::1::;`

### 3.2 Descoberta de ONUs Não Autorizadas (`LST-UNREGONU`)
- **Comando:** `LST-UNREGONU::DEV=ALL:1::;`
- **Exemplo de Resposta:**
  ```text
  IP 0
  M  1 COMPLD
  SLOTNO=1  PORTNO=1  ONUID=1  MAC=FHTT12345678  AUTHTYPE=MAC  DEVTYPE=AN5506-01-A
  SLOTNO=1  PORTNO=3  ONUID=1  MAC=FHTT87654321  AUTHTYPE=MAC  DEVTYPE=AN5506-02-B
  SLOTNO=2  PORTNO=1  ONUID=1  MAC=INCL99887766  AUTHTYPE=MAC  DEVTYPE=110B
  ;
  ```

### 3.3 Listagem de ONUs de uma Porta (`LST-ONU`)
- **Comando:** `LST-ONU::OLTID={slot},PONID={pon}:1::;`
- **Exemplo de Resposta:**
  ```text
  IP 0
  M  1 COMPLD
  SLOTNO=1  PORTNO=1  ONUID=1  NAME=Cliente_01  MAC=FHTT12345678  STATUS=up  RX=-19.50
  SLOTNO=1  PORTNO=1  ONUID=2  NAME=Cliente_02  MAC=FHTT87654321  STATUS=down  RX=--
  ;
  ```

### 3.4 Diagnóstico Óptico (`MEAS-OPTICAL`)
- **Comando:** `MEAS-OPTICAL::OLTID={slot},PONID={pon},ONUID={onuid}:1::;`
- **Exemplo de Resposta:**
  ```text
  IP 0
  M  1 COMPLD
  RX=-19.45  TX=2.15  VOLTAGE=3.30  BIAS=15.00
  ;
  ```

### 3.5 Provisionamento de ONU (`ADD-ONU` e `SET-VLAN`)
- **Comandos:**
  ```text
  ADD-ONU::OLTID={slot},PONID={pon}:1::NAME="{name}",AUTHTYPE=MAC,MAC={mac},LINEPROF={profile};
  CFG-LANPORTVLAN::OLTID={slot},PONID={pon},ONUID={onuid}:1::PORT=1,MODE=TAG,VLAN={vlan};
  ```

---

## 4. Integração na Arquitetura
O driver `FiberhomeTL1Driver` herdará de `BaseOLTDriver` e será instanciado pela `DriverFactory` para qualquer OLT Fiberhome (`an5516`, `an6000` ou `fiberhome`).
