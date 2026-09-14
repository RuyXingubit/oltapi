# Walkthrough - Onboarding Zero-Touch de OLTs & Telemetria Limpa

Implementação do fluxo contínuo e à prova de erro humano para Onboarding de OLTs, com probe automático de protocolo (SSH -> Telnet), fingerprinting de fabricante/modelo via CLI, backup Baseline v0 imediato, configuração dinâmica de SNMP (zero hardcode) e ingestão de inventário com TR-101 Circuit ID.
Além disso, removemos o botão indevido *"Confirmar Importação & Criar Baseline v0"* do cockpit de Telemetria (`subview-xray`), mantendo a Telemetria 100% focada em diagnóstico e leitura em tempo real.

---

## 1. O que Mudou

### 1.1 Backend & Modelos
- **`app/models/olt.py`**:
  - Criado o modelo `OLTOnboardRequest` recebendo apenas os campos essenciais: `name`, `host`, `username`, `password` e `port` opcional (None = detecção automática).
  - Criados os modelos `OnboardingStepItem` e `OLTOnboardResponse` para retorno detalhado do pipeline com status por etapa, logs e inventário inicial.
- **`app/services/olt_onboarding_service.py`**:
  - `probe_connectivity(host, port)`: Testa porta 22 (SSH) com timeout de 4s; em caso de falha/porta fechada, faz fallback para porta 23 (Telnet).
  - `fingerprint_vendor_and_model(host, port, protocol, username, password)`: Executa conexão e analisa o banner/prompt para identificar automaticamente se é `fiberhome`, `huawei`, `zte`, `intelbras` ou `vsol`.
  - `slugify_community(company_name, olt_name)`: Gera a community SNMP dinâmica baseada no Tenant/Provedor configurado no sistema (ex: `alpha_fibra_olt_central`), com **zero hardcode**.
  - `execute_onboarding(request, ctx)`: Orquestra o pipeline completo em 5 etapas:
    1. Probe de Conectividade (SSH -> Telnet)
    2. Fingerprint de Fabricante e Modelo
    3. Conexão e Backup Baseline v0
    4. Validação / Provisionamento SNMP Dinâmico
    5. Ingestão de Inventário e Circuit ID TR-101
- **`app/api/deps.py`**:
  - Registrada a factory `get_onboarding_service`.
- **`app/api/v1/endpoints_olts.py`**:
  - Endpoint `POST /api/v1/olts/onboard` integrado ao RBAC e documentado no OpenAPI.

### 1.2 Frontend & Experiência do Usuário (UI/UX)
- **`app/static/index.html`**:
  - **Modal de Cadastro de OLT (`modal-new-olt`)**: Redesenhado como assistente de Onboarding Zero-Touch contendo apenas Nome, IP/Host, Usuário, Senha e um accordion opcional para porta NAT customizada.
  - **Stepper Visual (`onboarding-stepper-section`)**: Componente dinâmico de 5 etapas com animações de pulso/execução, ícones de sucesso, aviso e erro, além de terminal de logs em tempo real.
  - **Card de Resumo (`onboarding-summary-card`)**: Apresenta os resultados consolidados (Fabricante, Protocolo, Backup v0, SNMP e ONUs descobertas) com botão de acesso direto à OLT.
  - **Cockpit de Telemetria (`subview-xray`)**: Removido o botão de importação/baseline do header, eliminando confusão operacional.
- **`app/static/css/style.css`**:
  - Estilos modernos com glassmorphism para `.onboarding-stepper`, `.stepper-step`, badges de status e terminal escuro de logs.
- **`app/static/js/app.js`**:
  - Funções `resetOnboardingModal()` e `handleStartOnboarding()` para controle do stepper, envio do payload enxuto e atualização imediata da lista de OLTs.

---

## 2. Validação e Testes

### 2.1 Testes Unitários (`pytest`)
- Foram executados todos os **204 testes** do projeto com **100% de sucesso**:
  ```bash
  ./.venv/bin/pytest
  # ======================= 204 passed, 2 warnings in 48.37s =======================
  ```
- Destaque para `tests/unit/test_olt_onboarding_pipeline.py`:
  - `test_probe_connectivity_ssh_success`: Valida prioridade do SSH na porta 22.
  - `test_probe_connectivity_fallback_to_telnet`: Valida fallback automático para porta 23 quando 22 está fechada.
  - `test_probe_connectivity_all_unreachable`: Valida erro defensivo quando o host está inacessível.
  - `test_fingerprint_vendor_and_model`: Valida identificação de banners Fiberhome AN5516, Huawei MA5608T, ZTE C320, Intelbras e VSOL.
  - `test_slugify_community_zero_hardcode`: Valida sanitização da community SNMP a partir do nome da empresa/tenant.
  - `test_execute_onboarding_full_success`: Valida orquestração de ponta a ponta gerando OLT, Baseline v0 e inventário.
  - `test_api_endpoint_onboard_olt`: Valida o endpoint REST `POST /api/v1/olts/onboard`.
- Destaque para `tests/unit/test_web_ui.py`:
  - Valida a existência do stepper, remoção do botão na telemetria e manipuladores JavaScript.

### 2.2 Sincronização OpenAPI
- Contratos sincronizados:
  ```bash
  ./.venv/bin/python -m scripts.export_openapi
  # [OpenAPI Sync] Exportado com sucesso: 63 endpoints e 78 esquemas salvos em docs/api_contracts/openapi.yaml e docs/api_contracts/openapi.json.
  ```

### 2.3 Container Docker Local
- Container `oltapi` reconstruído com sucesso:
  ```bash
  docker compose up -d --build --no-deps oltapi
  # Image oltapi-oltapi Built 
  # Container oltapi Recreated
  # Container oltapi Started
  ```
- Healthcheck verificado:
  `{"status":"healthy","service":"OLT Provisioning & Diagnostics API","version":"1.0.0"}`
