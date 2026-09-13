# Brainstorming v1: Próximos Passos Pós-Preparo da Fiberhome AN5516-01

**Data:** 12/09/2026  
**Contexto:** Conclusão da implementação dos comandos oficiais de provisionamento (Router, Bridge, VEIP de terceiros), ciclo de vida (deprovision, suspend, resume, reboot), backups multi-FTP e alinhamento transparente da documentação. 163 testes automatizados aprovados (100% de sucesso).

---

## 1. Status Consolidado do Ecossistema

| Frente | Situação | Observações |
| :--- | :---: | :--- |
| **Fiberhome AN5516-01 (Bancada)** | 🟡 Pronto para Teste Físico | Leitura, backups FTP, running-config e comandos CLI Telnet homologados. Aguardando ONU física de teste do técnico. |
| **Modo Router (PPPoE)** | 🟢 Implementado & Testado | Injeta WAN cfg, IP stack dual e credenciais PPPoE. |
| **Modo Bridge Padrão** | 🟢 Implementado & Testado | Injeta VLAN tag na porta 1. |
| **Modo Bridge VEIP (Terceiros)** | 🟢 Implementado & Testado | Injeta `mac_num_limit 30`, `speed 1000m` e `onuveip` (compatibilidade Huawei/ZTE/Intelbras). |
| **Ciclo de Vida (Lock/Unlock/Del/Reboot)** | 🟢 Implementado & Testado | Execução no diretório `cd onu` via Telnet CLI. |
| **Documentação & Matriz Real** | 🟢 Sincronizado no Git | Status honesto de homologação (`🟡 Em Validação de Bancada` vs `🔵 Driver Implementado`). |
| **Qualidade & Segurança** | 🟢 100% Aprovado | 163 testes unitários passando. Zero credenciais expostas no Git. |

---

## 2. Opções Estratégicas de Próximos Passos para Decisão

### Opção A: Checklist & Roteiro de Teste de Bancada para a Nova ONU (Amanhã / Segunda)
- **Objetivo:** Deixar o fluxo de validação da nova ONU 100% esquematizado para o momento em que o técnico ligar a fibra.
- **Etapas do Roteiro:**
  1. Conexão física da fibra na porta PON da bancada (Slot 1 ou 11).
  2. Execução da varredura de não-autorizadas (`GET /api/v1/olts/{id}/unauthorized`).
  3. Verificação dos dados capturados (MAC/Serial, modelo de hardware e porta PON).
  4. Teste 1: Provisionamento em modo Bridge (com VLAN de teste).
  5. Teste 2: Diagnóstico de sinal óptico (`GET /api/v1/olts/{id}/onus/{serial}`).
  6. Teste 3: Suspensão administrativa (`POST /api/v1/olts/{id}/onus/{serial}/suspend`) -> validar perda de tráfego.
  7. Teste 4: Reativação (`POST /api/v1/olts/{id}/onus/{serial}/resume`) -> validar retorno do tráfego.
  8. Teste 5: Reboot remoto OMCI (`POST /api/v1/olts/{id}/onus/{serial}/reboot`).
  9. Teste 6: Desprovisionamento limpo (`DELETE /api/v1/olts/{id}/onus/{serial}`).
  10. Teste 7: Provisionamento em modo Router PPPoE ou modo VEIP.

---

### Opção B: Autofind Scanner em Segundo Plano (Supervisão Proativa)
- **Objetivo:** O sistema não depender de cliques manuais para descobrir novas ONUs.
- **Como funciona:**
  - Um worker assíncrono em background consulta periodicamente a lista de não-autorizadas (`show unauthlist` / `show discovery`).
  - Ao detectar uma nova ONU na fibra, emite um Webhook criptografado (HMAC SHA-256) para o ERP informando: *"Nova ONU acendeu na porta 1/1, serial FHTT..."*.
  - Se a ONU pertencer a um contrato ativo no ERP, o motor de conciliação pode auto-provisionar ou deixar o botão de aprovação pronto.

---

### Opção C: Dashboard / Web UI Minimalista de Bancada para o Técnico
- **Objetivo:** Interface visual limpa e responsiva para o técnico de campo/bancada operar sem precisar abrir Swagger, Postman ou terminal.
- **Recursos:**
  - Cartão de status da OLT (latência, portas, status).
  - Tabela ao vivo de ONUs pendentes com botão "Provisionar Agora".
  - Formulário rápido: seleciona Modo (Router / Bridge / VEIP), digita a VLAN e salva.
  - Indicadores de potência óptica (Rx/Tx dBm) coloridos (verde/amarelo/vermelho).

---

### Opção D: Planejamento de Homologação do Próximo Fabricante
- **Objetivo:** Se houver outra OLT física disponível no laboratório (ex: Intelbras G08/G16, Huawei MA5800/MA5600T, V-SOL ou ZTE), iniciar os testes de conexão e leitura nela.
