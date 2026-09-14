# Plano de Implementação: Onboarding Contínuo de OLTs Zero-Touch (À Prova de Erro Humano)

**Data:** 2026-09-13  
**Status:** Aprovado pelo Usuário  
**Documento de Origem:** [docs/PRD_onboarding_olt_zero_touch.md](file:///Volumes/240/Code/oltapi/docs/PRD_onboarding_olt_zero_touch.md)

---

## 1. Visão Geral

Implementar um pipeline automatizado de onboarding de OLTs que elimina formulários manuais complexos e substitui etapas fragmentadas por um fluxo sequencial contínuo: o usuário apenas informa Nome, IP, Login e Senha; a API detecta o protocolo (SSH/Telnet), reconhece o fabricante, gera o backup Baseline v0, configura/adota o SNMP dinamicamente com base na empresa do setup inicial, sincroniza todas as portas, VLANs e ONUs no banco de dados, e apresenta a OLT pronta com um card resumo.

---

## 2. Componentes e Arquivos

1. **`app/models/olt.py`:** Modelos Pydantic `OLTOnboardRequest`, `OnboardingStepStatus`, `OLTOnboardResponse`.
2. **`app/services/olt_onboarding_service.py`:** Serviço central com probe de SSH/Telnet, fingerprinting de fabricante, backup preventivo Baseline v0, inteligência SNMP dinâmica (zero hardcode) e ingestão relacional com Circuit ID TR-101.
3. **`app/api/v1/endpoints_olts.py`:** Endpoint `POST /api/v1/olts/onboard`.
4. **`app/static/index.html`:** Simplificação do modal de cadastro, adição do Stepper visual com checklist em tempo real e remoção do botão `Confirmar Importação & Criar Baseline v0` da telemetria.
5. **`app/static/css/style.css`:** Estilos do Stepper visual, badges, estados animados e card de conclusão.
6. **`app/static/js/app.js`:** Lógica de execução do Onboarding, animação do checklist e limpeza dos bindings da telemetria.
7. **`tests/unit/test_olt_onboarding_pipeline.py`:** Cobertura de testes unitários com mocks de conexão, fingerprinting e pipeline end-to-end.
