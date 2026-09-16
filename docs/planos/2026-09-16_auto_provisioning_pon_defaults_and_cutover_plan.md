# Plano de Implementação: Configurações Default por PON & Tasks Temporizadas de Cutover (Multi-Fabricante)

Este plano estabelece a arquitetura e o passo a passo de desenvolvimento para o gerenciamento inteligente de portas PON no **OLTAPI (Backend FastAPI + Frontend NOC Flutter)**. O recurso atende a três casos de uso complementares:
1. **Preenchimento Inteligente (Smart Pre-fill):** Formulário de autorização manual já abre pré-preenchido com a VLAN e perfis padrão configurados para aquela porta PON, permitindo alteração manual quando necessário.
2. **Tasks Temporizadas de Auto-Provisionamento (Modo Cutover Zero-Touch):** Janela programada por tempo (ex: 2h) onde todas as ONUs detectadas na fibra daquela porta sobem automaticamente com a configuração da PON, sem intervenção humana no NOC.
3. **Descoberta Dinâmica de Esquema por Fabricante (Multi-Vendor Schema):** A API e o frontend consultam o driver de cada concentrador (**V-SOL**, **Fiberhome** e futuros) para descobrir dinamicamente quais parâmetros, VLANs e perfis estão disponíveis no hardware físico, eliminando hardcodes e condicionais de fabricante.

---

## Governança e Segurança

- **Segurança & Controle de Acesso:** As Tasks de Auto-Provisionamento possuem **expiração obrigatória por tempo** (`expires_at`), garantindo que nenhuma porta PON permaneça em modo de auto-aprovação indefinidamente.
- O operador possui visibilidade em tempo real na interface NOC com contagem regressiva e botão de cancelamento imediato (*Kill Switch*).
- Toda ONU auto-provisionada é catalogada no banco com identificador de auditoria indicando a Task de origem.
- **Governança de Drivers (Ports & Adapters):** Nenhum serviço de negócio ou tela do frontend usa condicionais de fabricante (`if vendor == 'VSOL'`). O backend expõe o endpoint agnóstico `GET /api/v1/olts/{id}/provisioning-schema`, delegando a cada driver polimórfico a especificação dos campos suportados e valores pré-carregados da memória da OLT.

---

## Componentes Arquiteturais

### 1. Camada de Domínio e Banco de Dados Relacional (Core Backend)
- **Modelos SQLAlchemy em `app/db/models.py`:**
  - `OLTPonPolicyModel`: `id` (UUIDv7), `olt_id`, `port`, `default_vlan`, `default_mode`, `default_line_profile`, `default_srv_profile`, `vendor_parameters`, `auto_authorize_enabled`, timestamps.
  - `AutoProvisionTaskModel`: `id` (UUIDv7), `olt_id`, `pon_port`, `target_vlan`, `default_mode`, `default_line_profile`, `default_srv_profile`, `status` (`RUNNING`, `COMPLETED`, `CANCELLED`), `starts_at`, `expires_at`, `remaining_seconds`, `provisioned_count`, `created_by`.
- **Schemas Pydantic v2 em `app/models/pon_policy.py`:**
  - `PonPolicyCreateOrUpdate`, `PonPolicyItem`, `AutoProvisionTaskCreate`, `AutoProvisionTaskItem`, `ProvisioningSchemaResponse`.
- **Repositório SQLAlchemy em `app/storage/sql/pon_policy_repository.py`:**
  - CRUD de políticas de portas PON e gerenciamento do ciclo de vida das tasks temporizadas.
- **Migração Alembic:** `alembic/versions/d83f92e6a1b2_add_pon_policies_and_tasks.py`.

### 2. Drivers & Descoberta Dinâmica de Esquema
- `BaseOLTDriver.get_provisioning_schema(olt)`: Método padrão com fallback seguro.
- `VSOLV1600Driver.get_provisioning_schema(olt)` e `list_profiles(olt)`: Extração direta de VLANs e perfis configurados no hardware.

### 3. Endpoints REST da API (FastAPI)
- `GET /api/v1/olts/{id}/provisioning-schema`
- `GET /api/v1/olts/{id}/pon-policies`
- `GET /api/v1/olts/{id}/pon-policies/{port}`
- `PUT /api/v1/olts/{id}/pon-policies/{port}`
- `DELETE /api/v1/olts/{id}/pon-policies/{port}`
- `POST /api/v1/olts/{id}/tasks/auto-provision`
- `GET /api/v1/olts/{id}/tasks/auto-provision`
- `POST /api/v1/olts/{id}/tasks/auto-provision/{task_id}/cancel`

### 4. Background Worker (AutofindScanner)
- Auto-provisionamento imediato quando há task ativa ou política contínua habilitada.
- Registro automático de webhook `onu.auto_provisioned` e salvamento preventivo na flash da OLT.

### 5. Frontend Flutter NOC
- `frontend/lib/models/pon_policy_model.dart`: Modelos Dart resilientes com getters de compatibilidade.
- `frontend/lib/core/network/api_client.dart`: Integração completa com endpoints de políticas e cutover.
- `frontend/lib/screens/olts/pon_policies_dialog.dart`: Gestão visual de defaults por PON e disparo de janelas de cutover.
- `frontend/lib/screens/olts/olts_screen.dart`: Botão de acesso 'Políticas PON' na tabela de hardware.
- `frontend/lib/screens/unconfigured/unconfigured_screen.dart`: Smart Pre-fill ao abrir modal e Banner com contagem regressiva de Cutover e botão de encerramento rápido.
