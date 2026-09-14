# Plano de Implementação: Onboarding com Streaming SSE em Tempo Real & Suporte Fiberhome

Este plano estabelece a implementação do feedback em tempo real (Server-Sent Events) para o Onboarding Zero-Touch de OLTs, incorpora a sintaxe nativa de SNMP da família Fiberhome AN5516 (`cd service`), garante o reconhecimento 100% dinâmico de slots e portas físicas, e mantém estrita segurança contra interferência em equipamentos ativos.

---

## 1. Contexto e Objetivos

1. **Streaming em Tempo Real (SSE):**
   - Como a leitura e o processamento de centenas de ONUs em OLTs ativas leva de 30 a 50 segundos de comunicação Telnet/CLI real, uma requisição síncrona monótona deixava a interface estática.
   - Implementar endpoint de **Server-Sent Events (SSE)** em `POST /api/v1/olts/onboard/stream`.
   - O backend transmite o progresso evento a evento (Passos 1 a 5), permitindo que o stepper avance ao vivo e o terminal de logs exiba mensagens segundo a segundo.
2. **Sintaxe Nativa do SNMP da Família AN5516 (`cd service`):**
   - O driver da AN5516 navega até o diretório correto:
     ```bash
     cd service
     show snmp community
     ```
     para ler a comunidade de leitura configurada de forma não-intrusiva.
   - Para provisionamento (quando necessário), executa:
     ```bash
     cd service
     set snmp community readonly <comunidade>
     cd ..
     save
     ```
3. **Mapeamento 100% Dinâmico de Slots e Portas Físicas:**
   - **Zero slots fixos em código:** O sistema extrai dinamicamente todos os slots físicos e portas PON a partir das placas identificadas no hardware e das ONUs sincronizadas (ex: `slots = sorted(list({o.slot for o in onus}))`).
   - Apresenta a contagem real de portas no Card de Resumo, eliminando qualquer leitura vazia (`0 / 0 UP`).
4. **Isolamento Modular de Modelos (AN5516 vs AN6000):**
   - A AN5516 permanece isolada em seu driver com comandos de diretório `cd service`.
   - Futuros chassis da nova geração AN6000 utilizarão seu respectivo driver modular via Factory Pattern (`system-view` ➔ `snmp-agent community read`), sem interferir na estabilidade de outros equipamentos.

---

## 2. Mudanças Propostas

### Backend

#### [fiberhome_tl1.py](file:///Volumes/240/Code/oltapi/app/drivers/fiberhome/fiberhome_tl1.py)
- Ajustar `configure_snmp` para Telnet CLI (`cd service`, `set snmp community readonly <community>`, `save`).
- Implementar leitura direta da comunidade no hardware (`show snmp community` dentro de `cd service`), capturando a string entre colchetes (`Read-only Community String is :[(.*?)]`).
- Adicionar leitura de potência óptica Rx/Tx em `get_onu_details` via `show onu opticalpower-info phy-id <serial>`.
- Adicionar leitura de serviço/VLAN via `show onu service-info slot <slot> pon <pon> onu <onu_id>`.

#### [olt_onboarding_service.py](file:///Volumes/240/Code/oltapi/app/services/olt_onboarding_service.py)
- Implementar gerador assíncrono para streaming: `execute_onboarding_stream(request, tenant_name)`.
- Emitir eventos estruturados Server-Sent Events (`step_update` e `completed`).

#### [endpoints_olts.py](file:///Volumes/240/Code/oltapi/app/api/v1/endpoints_olts.py)
- Adicionar endpoint de streaming `POST /api/v1/olts/onboard/stream`.

---

### Frontend & UI/UX

#### [app.js](file:///Volumes/240/Code/oltapi/app/static/js/app.js)
- Consumo de streaming SSE em `handleStartOnboarding()`.
- Atualização em tempo real do stepper e do terminal de logs.
- Correção da rota do botão de medição óptica (`checkOpticalPower`).
- Atualização ao vivo da célula de VLAN na tabela de inventário.

---

## 3. Plano de Verificação

- 210 testes unitários passando 100% via `pytest`.
- Exportação e sincronização do contrato OpenAPI (`python -m scripts.export_openapi`).
