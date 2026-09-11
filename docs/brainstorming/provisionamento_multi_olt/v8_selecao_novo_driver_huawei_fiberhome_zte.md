# Brainstorming: Expansão Multi-Vendor - Seleção do Próximo Fabricante
**Versão:** v8 (Análise e Levantamento de Comandos: Huawei vs Fiberhome vs ZTE)  
**Data:** 2026-09-11  
**Autor:** Antigravity & Usuário  

---

## 1. Contexto e Objetivo
Com a família Intelbras (8820, 8820i, G08 e G16) 100% implementada, testada e homologada na arquitetura de drivers do OLTAPI, iniciamos a expansão para outros fabricantes presentes no mercado brasileiro de ISPs.

O objetivo desta etapa é definir qual ecossistema atacaremos agora e alinhar a especificação técnica dos comandos de CLI/protocolo.

---

## 2. Panorama dos Fabricantes Candidatos

| Fabricante | Modelos Principais | Protocolos de Acesso | Complexidade | Presença de Mercado |
| :--- | :--- | :--- | :--- | :--- |
| **Huawei** | MA5800 (X2, X7, X15, X17)<br>MA5608T / MA5680T / MA5683T | SSH / Telnet (VRP CLI)<br>TL1 / NETCONF (YANG) | Média (CLI madura e previsível) | **Altíssima** (Líder em ISPs médios/grandes) |
| **Fiberhome** | AN5516-01 / 04 / 06<br>AN6000-7 / 15 / 17 | TL1 (Porta 3337) ou CLI (SSH/Telnet) | Média/Alta (TL1 estruturado ou CLI proprietária) | **Alta** (Muito forte em redes neutras e ISPs) |
| **ZTE** | C300 / C320 / C600 / C620 | SSH / Telnet (ZXROS CLI)<br>SNMP | Média (Sintaxe parecida com Cisco IOS) | **Média/Alta** |

---

## 3. Detalhamento Técnico: Huawei (MA5800 / MA5608T)

Caso a escolha seja **Huawei**, o driver padronizado via CLI (SSH/Telnet) implementará os seguintes comandos canônicos:

### 3.1 Descoberta de ONUs Não Autorizadas (*Autofind*)
```text
display ont autofind all
```
*Saída típica VRP:*
```text
  ----------------------------------------------------------------------------
  Number F/S/P  Autofind SN       Password         Vendor-ID Equip-ID Logic-SN
  ----------------------------------------------------------------------------
  1      0/1/0  48575443ABC12345  0x0000000000...  HWTC      EG8145V5 -
  ----------------------------------------------------------------------------
```

### 3.2 Provisionamento de ONU (Ativação)
```text
interface gpon 0/{slot}
ont add {port} sn-auth {serial_number} omci ont-lineprofile-name {line_profile} ont-srvprofile-name {srv_profile} desc "{description}"
quit
service-port vlan {vlan} gpon 0/{slot}/{port} ont {ont_id} gemport 1 multi-service user-vlan {vlan} tag-transform translate
```

### 3.3 Desprovisionamento (Remoção)
```text
undo service-port port 0/{slot}/{port} ont {ont_id}
interface gpon 0/{slot}
ont delete {port} {ont_id}
quit
```

### 3.4 Diagnóstico Óptico (Sinal Rx/Tx)
```text
display ont optical-info 0/{slot} {port} {ont_id}
```

### 3.5 Obtenção do Running Config
```text
display current-configuration
```

---

## 4. Detalhamento Técnico: Fiberhome (AN5516 / AN6000)

Caso a escolha seja **Fiberhome**, há duas abordagens:
1. **TL1 (Porta TCP 3337):** Comandos estruturados do tipo:
   - Login: `LOGIN:::1::UN={user},PWD={pass};`
   - Descoberta: `LST-UNREGONU::DEV=ALL:1::;`
   - Adição: `ADD-ONU::OLTID={olt},PONID={pon}:1::NAME={desc},AUTHTYPE=MAC,MAC={serial},LINEPROF={line};`
2. **CLI (SSH):**
   - `cd gpononu`
   - `show unreg-onu slot {slot} pon {pon}`

---

## 5. Recomendação

A recomendação técnica é priorizar **Huawei (MA5800 e MA5608T)**:
- É o fabricante mais requisitado do ecossistema de ISPs.
- Possui CLI (VRP) extremamente consistente entre as versões de firmware.
- O mapeamento de `slot/pon/ont_id` se encaixa perfeitamente no contrato OpenAPI que já desenhamos.
