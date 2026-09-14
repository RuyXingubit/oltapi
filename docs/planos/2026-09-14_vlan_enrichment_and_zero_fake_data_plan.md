# Plano: Eliminação de Dados Fictícios de VLAN e Motor de Enriquecimento em Segundo Plano

## Contexto e Diagnóstico
Identificou-se que todas as ONUs descobertas na OLT física AN5516 estavam sendo cadastradas e exibidas no inventário com a VLAN `301`.
A causa raiz identificada foi um fallback artificial no método de sincronização em lote (`app/services/olt_sync_service.py`), onde o primeiro ID retornado pelo comando `show vlan all` (`vlan_ids[0]`, que correspondia a 301) era atribuído arbitrariamente a todas as ONUs cuja listagem sumária de autorização não continha a coluna de VLAN.

Além disso, o modal de provisionamento no frontend (`app/static/js/app.js`) continha um comportamento legado que pré-selecionava a VLAN `301`.

## Objetivos
1. **Diretriz Mandatória "Zero Dados Falsos"**:
   - Remover qualquer fallback arbitrário no backend (`vlan = None` caso a listagem sumária não informe).
   - Suportar formatação do `circuit_id` (TR-101) sem VLAN (`{olt} eth {port}:{onu_id}`) quando a VLAN for nula.
   - Remover pré-seleção hardcoded no frontend, exibindo estado neutro de seleção.
2. **Motor de Enriquecimento Assíncrono (`ONUEnrichmentService`)**:
   - Desenvolver serviço dedicado com cadência controlada (80ms entre requisições) para consultar `show onu service-info slot {slot} pon {pon} onu {onu_id}`.
   - Integrar enriquecimento automático em segundo plano (`BackgroundTasks`) ao término do sync/onboarding da OLT.
   - Fornecer endpoint explícito `POST /api/v1/olts/{id}/enrich-vlans`.
3. **Reconciliação e Qualidade**:
   - Realizar varredura e atualização de 100% das ONUs cadastradas na base.
   - Cobertura de testes unitários com 100% de aprovação (214/214 testes).
   - Sincronização automática do contrato OpenAPI (`scripts.export_openapi`).
