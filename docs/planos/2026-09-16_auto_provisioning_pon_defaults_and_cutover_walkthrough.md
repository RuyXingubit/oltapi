# Walkthrough: Configurações Default por PON & Tasks Temporizadas de Cutover (Multi-Fabricante)

Conclusão da funcionalidade de **Configurações Default por Porta PON (Smart Pre-fill)** e **Tasks Temporizadas de Auto-Provisionamento (Modo Cutover Zero-Touch)** no ecossistema OLTAPI (Backend FastAPI + Frontend NOC Flutter).

---

## 🚀 O que Foi Implementado

### 1. Backend Core & Banco de Dados (PostgreSQL 16)
- **Modelos SQLAlchemy com UUIDv7:**
  - `OLTPonPolicyModel`: Configurações persistentes de VLAN, modo de operação e perfis padrão por porta física.
  - `AutoProvisionTaskModel`: Controle do ciclo de vida das tasks temporizadas de cutover (`RUNNING`, `COMPLETED`, `CANCELLED`), com timestamp de expiração (`expires_at`) e contador de ONUs ativadas.
- **Repositório SQL & Alembic:**
  - `SQLPonPolicyRepository` implementado e registrado no contêiner de injeção de dependências.
  - Migração Alembic `d83f92e6a1b2_add_pon_policies_and_tasks.py` aplicada e testada.
- **AutofindScannerService:**
  - O worker autônomo inspeciona periodicamente as portas da OLT; ao encontrar ONUs não autorizadas, verifica se há janela ativa de cutover ou auto-autorização habilitada.
  - Aloca o próximo ONU ID livre na porta, executa a ativação no hardware, dispara o webhook `onu.auto_provisioned` e grava o running-config na flash.

### 2. Multi-Fabricante & Schema-Driven (Sem Hardcode)
- Adicionado `get_provisioning_schema(olt)` na interface canônica `BaseOLTDriver`.
- No driver V-SOL (`VSOLV1600Driver`), implementada a leitura dinâmica das VLANs cadastradas e perfis de linha e serviço ativos.
- O frontend consome o schema retornado pela API (`GET /api/v1/olts/{id}/provisioning-schema`), eliminando completamente condicionais de marca na camada de visualização.

### 3. Frontend NOC Flutter
- **Modelos e API Client:** `PonPolicyModel`, `AutoProvisionTaskModel` e `ProvisioningSchemaModel` integrados com serialização tolerante e getters de alto nível.
- **Diálogo de Políticas PON (`PonPoliciesDialog`):**
  - Lista todas as portas físicas da OLT.
  - Permite configurar a VLAN padrão, modo e perfis de cada porta.
  - Permite disparar uma janela de Cutover temporizada (30min, 1h, 2h, 4h).
- **OltsScreen:** Botão 'Políticas PON' adicionado na tabela de OLTs.
- **UnconfiguredScreen (Smart Pre-fill & Cutover Banner):**
  - Quando o operador clica em 'Autorizar', a janela abre já preenchida com a VLAN e perfil padrão definidos para a porta.
  - Quando há janela de cutover ativa, um banner de aviso em tempo real é exibido com contador de ONUs ativadas, tempo restante regressivo e botão de encerramento rápido (*Kill Switch*).

---

## 🧪 Validação e Testes

1. **Testes Unitários do Backend (Pytest):**
   - `tests/unit/test_pon_policies.py`: 4 novos testes unitários cobrindo CRUD, expiração de tasks e cálculo de tempo restante.
   - Suíte Completa: **223 testes passando (100% de sucesso)**.
2. **Testes do Frontend (Flutter Test):**
   - `frontend/test/models_test.dart`: 3 novos testes unitários adicionados.
   - Suíte Completa: **11 testes passando (100% de sucesso)**.
3. **Análise Estática (Flutter Analyze):**
   - `flutter analyze` executado com zero warnings ou erros.
4. **Build de Produção Web:**
   - `flutter build web --release` compilado com sucesso.
5. **OpenAPI Sync:**
   - `python -m scripts.export_openapi` executado com sucesso (73 endpoints e 96 esquemas gerados em `docs/api_contracts/`).
6. **Documentação MkDocs:**
   - `docs/frontend_noc.md` e site gerados com sucesso via `mkdocs build`.
