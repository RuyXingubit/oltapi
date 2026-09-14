# Walkthrough: Onboarding Zero-Touch com Streaming SSE, Telemetria SNMP e Diagnóstico Óptico

Data: 14/09/2026

## 1. Contexto e Objetivos Alcançados
- **Observabilidade em Tempo Real (SSE Streaming)**: O onboarding de OLTs agora emite eventos contínuos via Server-Sent Events (`POST /api/v1/olts/onboard/stream`), mantendo a interface web 100% responsiva e animando o stepper de 5 etapas segundo a segundo.
- **Diagnóstico SNMP Multi-Padrão (Zero Hardcode)**:
  - Consulta física via CLI em `cd service` (`show snmp community`) no chassi Fiberhome AN5516.
  - Varredura em cascata de comunidades dinâmicas geradas a partir do provedor/tenant (`olt_{slug}`, `oltCamelCase`, `{slug}`, `adsl`, `public`).
  - Provisionamento seguro via CLI (`set snmp community readonly <str>`, `save`) caso o chassi não possua comunidade ativa.
- **Mapeamento Dinâmico de Portas e Slots**: Portas ativas e total de portas calculados a partir dos slots e portas das ONUs descobertas, evitando `0 / 0 UP`.
- **Diagnóstico Óptico em Tempo Real ("📶 Sinal")**:
  - Correção da rota no frontend para `GET /api/v1/olts/{olt_id}/onus/{serial}`.
  - Medição relâmpago de ~150ms na Fiberhome com `show onu opticalpower-info phy-id <serial>`.
- **Mapeamento de VLANs de Serviço**:
  - Preenchimento da coluna de VLANs no inventário e consulta de CVID via `show onu service-info`.

## 2. Arquivos Modificados
- `app/services/olt_onboarding_service.py`
- `app/api/v1/endpoints_olts.py`
- `app/drivers/fiberhome/fiberhome_tl1.py`
- `app/services/olt_sync_service.py`
- `app/models/onu.py`
- `app/static/js/app.js`
- `tests/unit/test_fiberhome_telnet_cli.py`
- `tests/unit/test_olt_onboarding_pipeline.py`
- `tests/unit/test_olt_sync_and_vlans.py`
- `docs/api_contracts/openapi.yaml` e `docs/api_contracts/openapi.json`

## 3. Validação
- **Pytest**: 210 testes unitários aprovados (100% pass).
- **OpenAPI**: 64 endpoints e 78 schemas sincronizados.
- **Produção Live**: Validado com sucesso na OLT física Fiberhome AN5516.
