# Walkthrough — Onda A: Onboarding Wizard (2 Fases), Raio-X de Chassi & Gestão de VLANs

**Data:** 2026-10-14  
**Referência SDD:** Seção 5.1 / 5.2 de [`docs/SDD.md`](file:///Volumes/240/Code/oltapi/docs/SDD.md)  
**Plano:** [`docs/planos/2026-10-14_onda_a_onboarding_raio_x_vlans_plan.md`](file:///Volumes/240/Code/oltapi/docs/planos/2026-10-14_onda_a_onboarding_raio_x_vlans_plan.md)

---

## 1. Resumo das Entregas

1. **Modelos de Domínio (`frontend/lib/models/`)**:
   - [`vlan_model.dart`](file:///Volumes/240/Code/oltapi/frontend/lib/models/vlan_model.dart): Implementação de [`VlanMetricsModel`](file:///Volumes/240/Code/oltapi/frontend/lib/models/vlan_model.dart#L1-L31) e [`VlanHistoryModel`](file:///Volumes/240/Code/oltapi/frontend/lib/models/vlan_model.dart#L33-L75).
   - [`olt_model.dart`](file:///Volumes/240/Code/oltapi/frontend/lib/models/olt_model.dart): Implementação de [`OltPortStatusItem`](file:///Volumes/240/Code/oltapi/frontend/lib/models/olt_model.dart#L96-L129), [`OltXRayModel`](file:///Volumes/240/Code/oltapi/frontend/lib/models/olt_model.dart#L131-L209), [`SyncOltResultModel`](file:///Volumes/240/Code/oltapi/frontend/lib/models/olt_model.dart#L211-L247), [`ExistingSviItem`](file:///Volumes/240/Code/oltapi/frontend/lib/models/olt_model.dart#L249-L273), [`OltInspectResultModel`](file:///Volumes/240/Code/oltapi/frontend/lib/models/olt_model.dart#L275-L317), [`OnboardingStepModel`](file:///Volumes/240/Code/oltapi/frontend/lib/models/olt_model.dart#L319-L340) e [`OltOnboardResultModel`](file:///Volumes/240/Code/oltapi/frontend/lib/models/olt_model.dart#L342-L408).

2. **Cliente HTTP (`frontend/lib/core/network/api_client.dart`)**:
   - Adição dos métodos [`inspectOlt`](file:///Volumes/240/Code/oltapi/frontend/lib/core/network/api_client.dart#L179-L189), [`onboardOltWizard`](file:///Volumes/240/Code/oltapi/frontend/lib/core/network/api_client.dart#L191-L201), [`onboardOltZeroTouch`](file:///Volumes/240/Code/oltapi/frontend/lib/core/network/api_client.dart#L203-L213), [`getOltTelemetry`](file:///Volumes/240/Code/oltapi/frontend/lib/core/network/api_client.dart#L215-L224), [`syncOlt`](file:///Volumes/240/Code/oltapi/frontend/lib/core/network/api_client.dart#L226-L235), [`enrichOltVlans`](file:///Volumes/240/Code/oltapi/frontend/lib/core/network/api_client.dart#L237-L246), [`getOltVlanMetrics`](file:///Volumes/240/Code/oltapi/frontend/lib/core/network/api_client.dart#L248-L263), [`createOltVlan`](file:///Volumes/240/Code/oltapi/frontend/lib/core/network/api_client.dart#L265-L275) e [`getOltVlanHistory`](file:///Volumes/240/Code/oltapi/frontend/lib/core/network/api_client.dart#L277-L292).

3. **Telas e Diálogos Operacionais (`frontend/lib/screens/olts/`)**:
   - [`olt_onboard_wizard_dialog.dart`](file:///Volumes/240/Code/oltapi/frontend/lib/screens/olts/olt_onboard_wizard_dialog.dart): Wizard em 2 Fases (Fase 1: Inspeção de arquitetura AUX vs In-Band, SVIs L3 e VLANs; Fase 2: Configuração de SVI Inband, VLANs de serviço e QoS; Fase 3: Trilha de auditoria do comissionamento) + opção Zero-Touch em 1 clique.
   - [`olt_xray_dialog.dart`](file:///Volumes/240/Code/oltapi/frontend/lib/screens/olts/olt_xray_dialog.dart): Painel de Raio-X físico do chassi, status SNMP, grade de portas PON e Uplink, VLANs ativas na flash e botão de Sincronização Brownfield (`Flash -> DB`).
   - [`olt_vlans_dialog.dart`](file:///Volumes/240/Code/oltapi/frontend/lib/screens/olts/olt_vlans_dialog.dart): Catálogo de VLANs com métricas de ocupação de ONUs, criação de VLAN na OLT (hardware + banco), enriquecimento assíncrono e histórico de auditoria por VLAN.
   - [`olts_screen.dart`](file:///Volumes/240/Code/oltapi/frontend/lib/screens/olts/olts_screen.dart) e [`olt_form_dialog.dart`](file:///Volumes/240/Code/oltapi/frontend/lib/screens/olts/olt_form_dialog.dart): Integração dos novos modais com constraints defensivas anti-overflow e remoção de fabricantes teóricos do fallback (`['fiberhome', 'vsol', 'parks']`).

---

## 2. Validação e Testes Automatizados

- `flutter analyze`: **0 issues found**.
- `flutter test`: **15/15 testes aprovados** ([`models_test.dart`](file:///Volumes/240/Code/oltapi/frontend/test/models_test.dart) e [`widget_test.dart`](file:///Volumes/240/Code/oltapi/frontend/test/widget_test.dart), incluindo validação de abertura dos 3 diálogos da Onda A sem overflow de pixels).
