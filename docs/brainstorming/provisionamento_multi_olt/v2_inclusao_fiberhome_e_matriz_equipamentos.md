# Brainstorming: API Unificada de Provisionamento Multi-OLT
**Versão:** v2 (Inclusão de Fiberhome, Protocolos TL1 e Matriz de Fabricantes)  
**Data:** 2026-09-10  
**Autor:** Antigravity & Usuário  

---

## 1. Atualização do Escopo de Equipamentos de Teste
Com a inclusão da **Fiberhome**, a bancada de testes e suporte da API abrange 6 famílias de equipamentos:

1. **Intelbras G16** (GPON - 16 portas)
2. **Intelbras 8820** (GPON)
3. **Intelbras 4840** (EPON/GPON)
4. **Huawei SmartAX / MA5800** (X7 e X2)
5. **Fiberhome** (ex: Linha AN5516-01 / 04 / 06 / AN5116)
6. **Parks Fiberlink** (GPON)

---

## 2. Particularidades Técnicas da Fiberhome

A Fiberhome possui uma característica muito importante no mercado de provedores:
- **TL1 (Transaction Language 1):** A Fiberhome é amplamente conhecida por disponibilizar o protocolo TL1 (geralmente na porta TCP 3337). O TL1 é um protocolo de comando estruturado em texto baseado no padrão Bellcore/Telcordia.
  - *Exemplo de comando TL1:* `LST-UNCFGONT::OLTID=...` (listar não configuradas), `ADD-ONT::...` (autorizar ONU).
  - *Vantagem do TL1:* Resposta muito mais previsível e estruturada que fazer *scraping* de terminal CLI via Telnet/SSH.
- **CLI (SSH / Telnet):** Também possui CLI tradicional (`cd gpononu`, comandos de autorização), mas o prompt e navegação por diretórios/contextos da Fiberhome é mais complexo que o da Huawei.
- **SNMP:** Muito utilizado para telemetria de sinais e status.

> [!TIP]
> Para Fiberhome, utilizar **TL1** ou **CLI com driver dedicado** simplifica drasticamente a automação em relação a tentar interagir com a interface gráfica do UNM2000/ANM2000.

---

## 3. Matriz de Protocolos por Fabricante

| Fabricante / Família | Protocolo Primário Recomendado | Protocolo Secundário | Particularidade Principal |
| :--- | :--- | :--- | :--- |
| **Huawei (MA5800 X7/X2)** | **CLI via SSH** | SNMP | Perfis de serviço (`lineprofile`, `srvprofile`), comandos padronizados VRP. |
| **Fiberhome (AN5516)** | **TL1 (Porta 3337) ou CLI** | SNMP | Protocolo TL1 nativo e muito rápido para automação direta. |
| **Intelbras G16** | **CLI (SSH/Telnet) / SNMP** | Web API / HTTP | Provisionamento direto por porta PON e perfil GPON. |
| **Intelbras 8820** | **CLI (SSH/Telnet)** | SNMP | Base CLI com comandos específicos para autorização e alocação de ONU-ID. |
| **Intelbras 4840** | **CLI (SSH/Telnet)** | SNMP | Modelos EPON/GPON, sintaxe própria de autorização. |
| **Parks (Fiberlink)** | **CLI (CLIOS via SSH/Telnet)** | SNMP | Sintaxe estruturada baseada no sistema operacional CLIOS da Parks. |

---

## 4. Evolução da Camada de Drivers

A camada de drivers agora suporta três adaptadores de protocolo base:
1. **SSH / Telnet Transport:** Comandos interativos CLI com parser regex.
2. **TL1 Transport:** Sessão TCP persistente ou sob demanda enviando comandos TL1 estruturados (ideal para Fiberhome).
3. **SNMP Transport:** Para consultas rápidas de telemetria (sinal óptico Rx/Tx, status online/offline, uptime).

---

## 5. Próximos Passos
- Alinhar com o usuário qual é o modelo exato da Fiberhome disponível (ex: AN5516-01, AN5516-06B, etc.) e se o serviço TL1 está ativo.
- Definir a stack do projeto (Go vs Python vs outra) e persistência inicial.
