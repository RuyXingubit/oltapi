# Plano de Implementação — Onda C: Supervisão Autônoma (Scanner), Timeline TR-101, Webhooks HMAC & Governança RBAC Multi-Tenant

**Data:** 2026-10-14  
**Referência SDD:** Seção 5.2 de [`docs/SDD.md`](file:///Volumes/240/Code/oltapi/docs/SDD.md)

---

## 1. Arquivos Criados / Modificados

1. **Modelos (`frontend/lib/models/governance_models.dart`)**:
   - `ScannerOltSummaryModel`, `ScannerRunResultModel`, `ScannerStatusModel`
   - `OnuMigrationEventModel`, `ReconcileFieldEventResultModel`
   - `WebhookSubscriptionModel`, `WebhookDeliveryLogModel`
   - `TenantVlanAllocationModel`, `TenantModel`
   - `UserAccountModel`
   - `ApiKeyModel`, `ApiKeyCreatedModel`
2. **Cliente HTTP (`frontend/lib/core/network/api_client.dart`)**:
   - Métodos do Autofind Scanner (`getScannerStatus`, `startScanner`, `stopScanner`, `runScannerNow`, `updateScannerInterval`)
   - Métodos de Timeline & Reconciliação TR-101 (`getGlobalOnuHistory`, `reconcileFieldEvent`)
   - Métodos de Webhooks (`getWebhooks`, `createWebhook`, `deleteWebhook`, `pingWebhook`, `getWebhookDeliveries`)
   - Métodos de RBAC & Rede Neutra (`getTenants`, `createTenant`, `allocateTenantVlan`, `deallocateTenantVlan`, `getUsers`, `createUser`, `updateUser`, `deleteUser`, `getApiKeys`, `createApiKey`, `revokeApiKey`)
3. **Tela de Governança & Automação (`frontend/lib/screens/governance/governance_screen.dart`)**:
   - Sub-aba 1: **Scanner & Timeline TR-101**
   - Sub-aba 2: **Webhooks ERP (HMAC)**
   - Sub-aba 3: **Inquilinos & Rede Neutra**
   - Sub-aba 4: **Usuários & API Keys**
   - Integrada ao [`app_shell.dart`](file:///Volumes/240/Code/oltapi/frontend/lib/screens/shell/app_shell.dart) com constraints 100% defensivas (`Expanded`, `Flexible`, `SingleChildScrollView`, `Wrap`, `TextOverflow.ellipsis`).
4. **Testes Unitários e de Widget**:
   - Novos testes em [`frontend/test/models_test.dart`](file:///Volumes/240/Code/oltapi/frontend/test/models_test.dart) e [`frontend/test/widget_test.dart`](file:///Volumes/240/Code/oltapi/frontend/test/widget_test.dart).
