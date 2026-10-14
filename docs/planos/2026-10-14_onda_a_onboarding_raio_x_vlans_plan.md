# Plano de Implementação: Onda A — Onboarding Wizard, Raio-X de Chassi & Gestão de VLANs (`frontend/`)

**Data:** 2026-10-14  
**Status:** Em Execução

---

## 1. Objetivo
Implementar a **Onda A** do [System Design & Specification Document (`docs/SDD.md`)](../SDD.md) na Central de Operações NOC em Flutter (`frontend/`), entregando:
1. **Wizard de Onboarding Zero-Touch em 2 Fases (`OltOnboardWizardDialog`)**
2. **Painel de Raio-X de Chassi, Telemetria SNMP e Sync Brownfield (`OltXRayDialog`)**
3. **Gestão de VLANs na Flash, Métricas de Ocupação e Histórico de Seriais (`OltVlansDialog`)**
4. **Integração na Tela de Concentradores (`OltsScreen`)** e correção dos fallbacks de fabricantes em `OltFormDialog`.

---

## 2. Arquivos Criados e Modificados

- [`frontend/lib/models/olt_model.dart`](../../frontend/lib/models/olt_model.dart): Adição de `OltPortStatusItem`, `OltXRayModel`, `SyncOltResultModel`, `ExistingSviItem`, `OltInspectResultModel`, `OnboardingStepModel` e `OltOnboardResultModel`.
- [`frontend/lib/models/vlan_model.dart`](../../frontend/lib/models/vlan_model.dart): Criação dos modelos `VlanMetricsModel` e `VlanHistoryModel`.
- [`frontend/lib/core/network/api_client.dart`](../../frontend/lib/core/network/api_client.dart): Adição dos métodos HTTP `inspectOlt`, `onboardOltWizard`, `onboardOltZeroTouch`, `getOltTelemetry`, `syncOlt`, `enrichOltVlans`, `getOltVlanMetrics`, `createOltVlan` e `getOltVlanHistory`.
- [`frontend/lib/screens/olts/olt_onboard_wizard_dialog.dart`](../../frontend/lib/screens/olts/olt_onboard_wizard_dialog.dart): Modal interativo para pré-inspeção não-destrutiva (`inspect`), comissionamento assistido (`onboard-wizard`) e onboarding 1-clique (`onboard`).
- [`frontend/lib/screens/olts/olt_xray_dialog.dart`](../../frontend/lib/screens/olts/olt_xray_dialog.dart): Modal de diagnóstico físico do chassi, portas PON/Uplink, status SNMP e botão de sincronização brownfield (`sync`).
- [`frontend/lib/screens/olts/olt_vlans_dialog.dart`](../../frontend/lib/screens/olts/olt_vlans_dialog.dart): Modal de catálogo e métricas de VLANs, criação de VLAN na flash, enriquecimento em segundo plano e visualização de histórico de seriais por VLAN.
- [`frontend/lib/screens/olts/olts_screen.dart`](../../frontend/lib/screens/olts/olts_screen.dart) e [`frontend/lib/screens/olts/olt_form_dialog.dart`](../../frontend/lib/screens/olts/olt_form_dialog.dart): Botão `Wizard Zero-Touch`, botões rápidos nos cards de OLT (`Raio-X`, `VLANs`, `Políticas PON`, `Backups`) com layout defensivo anti-overflow e limpeza de fabricantes teóricos no fallback.
- [`frontend/test/models_test.dart`](../../frontend/test/models_test.dart) e [`frontend/test/widget_test.dart`](../../frontend/test/widget_test.dart): Cobertura de testes unitários e de widgets para todos os novos modelos e diálogos da Onda A.
- [`docs/SDD.md`](../SDD.md) e [`docs/ROADMAP.md`](../ROADMAP.md): Marcação da Onda A como concluída.
