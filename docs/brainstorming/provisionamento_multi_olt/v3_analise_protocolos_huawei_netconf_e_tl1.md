# Brainstorming: API Unificada de Provisionamento Multi-OLT
**Versão:** v3 (Análise de Protocolos Huawei: NETCONF, TL1 e CLI)  
**Data:** 2026-09-10  
**Autor:** Antigravity & Usuário  

---

## 1. Suporte a NETCONF na Huawei MA5800 (X7 / X2)

Sim, a linha **Huawei MA5800** suporta **NETCONF** (RFC 6241 sobre SSH, geralmente na porta 830), especialmente a partir das versões de firmware V800R018C00 / V800R019C00+.

A Huawei utiliza o NETCONF integrado com modelos de dados **YANG** (família de schemas `huawei-access-gpon`, `huawei-devm`, etc.), sendo o protocolo base que o software de gerência da Huawei (iMaster NCE / U2000) usa para orquestração em larga escala.

---

## 2. Comparativo de Protocolos na Huawei MA5800

| Protocolo | Porta Padrão | Formato dos Dados | Requisitos na OLT | Complexidade de Integração |
| :--- | :--- | :--- | :--- | :--- |
| **CLI (SSH / VRP)** | TCP 22 | Texto puro (comandos VRP) | Habilitado por padrão (`ssh server enable`) | **Baixa/Média:** Universal, suportado em qualquer firmware e sem custo/licença extra. |
| **NETCONF** | TCP 830 | XML estruturado (RFC 6241 / YANG) | Requer `netconf agent enable` e compatibilidade de firmware | **Alta:** Excelente transacionalidade, mas schemas XML da Huawei são densos e variam entre patches de firmware. |
| **TL1** | TCP 9819 | Texto estruturado (Bellcore) | Requer `tl1 service enable` na OLT | **Média:** Mensagens padronizadas, sem necessidade de interpretar prompts de terminal. |
| **SNMP** | UDP 161 | OIDs binárias | Comunidade SNMP configurada | **Baixa (Apenas Leitura):** Ótimo para telemetria de sinal óptico, mas lento/complexo para escrita e provisionamento de perfis. |

---

## 3. Prós e Contras do NETCONF para a Nossa API

### Vantagens (Prós)
1. **Transacionalidade e Atomicidade:** Suporta operações do tipo `<edit-config>` com validação de commit e rollback caso algo falhe.
2. **Sem interpretação de terminal (Screen Scraping):** As respostas chegam em XML padronizado, eliminando o risco de quebras causadas por mudanças de prompt (`MA5800(config)#`, paginação de `--More--`, etc.).
3. **Padrão de Indústria:** Protocolo moderno adotado em SDN e automação de redes de grande porte.

### Desvantagens e Armadilhas (Contras)
1. **Compatibilidade de Campo:** Em provedores de internet, muitas OLTs estão com firmwares antigas ou sem os módulos YANG ativados. A CLI (SSH) funciona em 100% dos equipamentos sem depender de configuração prévia complexa na OLT.
2. **Curva de Desenvolvimento Inicial:** Montar os envelopes XML com namespaces específicos da Huawei leva mais tempo do que enviar a sequência comprovada de comandos de provisionamento.
3. **Diagnóstico:** Erros em XML do NETCONF da Huawei às vezes são opacos (ex: erro genérico `application: operation-failed`) comparados à mensagem direta que a CLI cospe na tela (ex: `Failure: The ONT SN already exists`).

---

## 4. Estratégia de Arquitetura Recomendada

Graças ao padrão **Driver Pattern** que desenhamos no `v1`, a API fica 100% isolada do protocolo subjacente:

```
[ ERP / Postman ] -> [ POST /api/v1/olts/{id}/onus ]
                           │
                           ▼
                 [ Driver Huawei ]
                     │        │
      (Opção Rápida) │        │ (Evolução Futura)
                     ▼        ▼
                [ CLI/SSH ] [ NETCONF/XML ]
```

### Recomendação Prática:
1. **Fase 1 (MVP Rápido e Seguro):** Implementar o driver da Huawei via **CLI (SSH)**. Isso garante que a API funcione de imediato na sua MA5800-X7 / X2 sem depender de ajustar parâmetros de NETCONF na OLT física.
2. **Fase 2 (Plug & Play):** Adicionar uma flag na configuração da OLT (ex: `driver_mode: "ssh"` ou `driver_mode: "netconf"`). Se a OLT suportar NETCONF, a API pode chavear sem que o ERP precise mudar uma única linha de código.
