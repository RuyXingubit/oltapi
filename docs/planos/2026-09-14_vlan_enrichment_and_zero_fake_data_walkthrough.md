# Walkthrough: Eliminação de Dados Fictícios de VLAN e Motor de Enriquecimento em Segundo Plano

## Visão Geral da Execução
Concluímos a eliminação de todos os dados fictícios e fallbacks de VLAN, além de implementar o motor de enriquecimento em segundo plano (`ONUEnrichmentService`), com execução e validação completa diretamente na OLT física (VTX - FiberHome AN5516).

---

## 1. Modificações Realizadas

### A. Backend Core & Sync Service
1. **[app/core/circuit_id.py](file:///Volumes/240/Code/oltapi/app/core/circuit_id.py)**:
   - `generate_circuit_id(olt_name, port, onu_id, vlan=None)` agora aceita `vlan` opcional (`None`).
   - Quando `vlan` for nulo, gera estritamente `{clean_olt} eth {clean_port}:{onu_id}` de acordo com TR-101.
2. **[app/services/olt_sync_service.py](file:///Volumes/240/Code/oltapi/app/services/olt_sync_service.py)**:
   - Removido o fallback `or (vlan_ids[0] if vlan_ids else 100)`.
   - Se o comando rápido de autorização em lote da OLT não fornecer a VLAN, a ONU é salva com `vlan = None`, garantindo conformidade com a diretriz "Zero Dados Falsos".
3. **[app/services/onu_enrichment_service.py](file:///Volumes/240/Code/oltapi/app/services/onu_enrichment_service.py)**:
   - Criado serviço de enriquecimento gradual assíncrono.
   - Utiliza uma única sessão Telnet contínua (`client = driver._open_telnet_session(olt)`), navegando para o submodo `cd onu` e executando `show onu service-info slot {slot} pon {pon} onu {onu_id}` com intervalo de 50ms a 80ms para proteger a CPU da controladora da OLT.
   - Extrai a C-VLAN real configurada (suportando CVID em FE e Cvlan em VEIP) e atualiza o inventário e o `circuit_id`.
   - Suporta parâmetro `force=True` para reconciliar inventários pré-existentes.
4. **[app/api/v1/endpoints_olts.py](file:///Volumes/240/Code/oltapi/app/api/v1/endpoints_olts.py)**:
   - Endpoint `POST /api/v1/olts/{id}/sync`: agora recebe `background_tasks: BackgroundTasks` e despacha automaticamente o enriquecimento após a sincronização rápida.
   - Endpoint dedicado `POST /api/v1/olts/{id}/enrich-vlans`: permite acionar a varredura manual sob demanda com suporte a `force=True` e `max_onus`.
5. **[app/api/deps.py](file:///Volumes/240/Code/oltapi/app/api/deps.py)**:
   - Registrada a injeção de dependência `get_enrichment_service` com fallback automático caso chamada diretamente sem container de injeção.

### B. Frontend
1. **[app/static/js/app.js](file:///Volumes/240/Code/oltapi/app/static/js/app.js)**:
   - Removida a pré-seleção hardcoded `v === 301`.
   - Substituída por opção neutra desabilitada `<option value="" selected disabled>Selecione a VLAN...</option>`.

---

## 2. Validação na OLT Física Real (VTX - 561 ONUs)

Executamos a varredura e enriquecimento completo nas 561 ONUs cadastradas na OLT física AN5516.
- **Resultado:**
  - `total_scanned`: 561
  - `vlans_discovered`: 555
  - `duration_seconds`: 140.21s (~2.3 minutos para 561 ONUs em cadência suave)
  - `status`: `completed`
- **Distribuição Real de VLANs no Banco de Dados:**
  - VLAN 11: 244 ONUs
  - VLAN 1000: 231 ONUs
  - VLAN 301: 47 ONUs
  - VLAN 3000: 14 ONUs
  - VLAN 10: 8 ONUs
  - Sem VLAN configurada (`None`): 6 ONUs (exibidas como `-`)
  - VLAN 13: 4 ONUs
  - VLAN 12: 2 ONUs
  - VLAN 302: 2 ONUs
  - VLAN 2334: 2 ONUs
  - VLAN 20: 1 ONU

---

## 3. Testes Automatizados e Contrato OpenAPI
- **Testes Unitários:** 214/214 testes aprovados (`pytest tests/unit/`).
- **Contrato OpenAPI:** Atualizado com 65 endpoints e 79 esquemas em `docs/api_contracts/openapi.yaml` e `docs/api_contracts/openapi.json`.
