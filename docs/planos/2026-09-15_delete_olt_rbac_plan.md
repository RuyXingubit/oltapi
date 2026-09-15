# Plano de Implementação: Exclusão Segura de OLT com RBAC e Confirmação Defensiva

Implementar a funcionalidade de exclusão de OLT na interface web e reforçar o controle de acesso (RBAC) no endpoint backend `DELETE /api/v1/olts/{olt_id}`, exigindo perfil de Administrador e um modal defensivo onde o usuário precisa digitar exatamente o nome da OLT para confirmar a ação.

## User Review Required

> [!IMPORTANT]
> **Regra de Segurança em Primeiro Lugar**:
> - O backend exige que o usuário possua papel de `SUPER_ADMIN` ou `TENANT_ADMIN` (ou Master Key ativa) e escopo `olts:admin`. Qualquer tentativa por operadores NOC ou técnicos de campo resulta em `403 Forbidden`.
> - Toda exclusão gera log de auditoria de segurança com IP e e-mail do executor.
> - No Frontend, o botão de apagar (`🗑️ Apagar`) só é visível para usuários administradores.
> - A exclusão exige que o usuário digite exatamente o nome da OLT no campo de texto para destravar o botão de confirmação, prevenindo acidentes.

---

## Proposed Changes

### Backend: Reforço de Segurança & Auditoria

#### [endpoints_olts.py](file:///Volumes/240/Code/oltapi/app/api/v1/endpoints_olts.py)
- Proteger o endpoint `@router.delete("/{olt_id}")`:
  - Injetar `ctx: SecurityContext = Depends(get_security_context)` e `request: Request`.
  - Validar escopo `ctx.enforce_scope("olts:admin")`.
  - Validar papel administrativo: `if not ctx.is_super_admin and ctx.role != "TENANT_ADMIN": raise 403`.
  - Validar multi-tenant: `if ctx.allowed_olt_ids and olt.id not in ctx.allowed_olt_ids: raise 403`.
  - Registrar log de auditoria: `[SECURITY AUDIT] Usuário ... EXCLUIU a OLT ...`.

#### [rbac.py](file:///Volumes/240/Code/oltapi/app/core/rbac.py) e [deps.py](file:///Volumes/240/Code/oltapi/app/api/deps.py)
- Correção de brecha no RBAC: `is_super_admin` passa a checar estritamente `role == "SUPER_ADMIN"`.
- `ROLE_DEFAULT_SCOPES` implementado para atribuir escopos estritos ao JWT de acordo com o papel do usuário.

---

### Frontend: Modal de Confirmação Defensivo & Integração UI

#### [index.html](file:///Volumes/240/Code/oltapi/app/static/index.html)
- Adicionar o modal `modal-delete-olt` com estilo de alerta de perigo (vermelho), contendo:
  - Título e avisos de impacto (desvinculação de ONUs e telemetria).
  - Indicação do nome da OLT a ser digitado.
  - Input de texto para confirmação (`input-confirm-delete-olt`).
  - Botão de exclusão inicialmente desabilitado (`btn-confirm-delete-olt`).

#### [app.js](file:///Volumes/240/Code/oltapi/app/static/js/app.js)
- Na tabela de OLTs (`loadOLTsList`):
  - Renderizar o botão `🗑️ Apagar` caso o usuário seja Administrador (`SUPER_ADMIN`, `TENANT_ADMIN` ou Master Key).
- Adicionar handlers para o fluxo de exclusão:
  - Ao clicar em `btn-delete-olt`: abre o modal, limpa o input e desabilita o botão vermelho.
  - No evento `input` do campo de confirmação: compara em tempo real se o texto digitado coincide exatamente com o nome da OLT; quando coincidir, destrava o botão vermelho.
  - Ao clicar em `btn-confirm-delete-olt`: dispara requisição `DELETE /api/v1/olts/{olt_id}`, fecha o modal, emite alerta de sucesso e recarrega a listagem de OLTs.

---

### Testes & Contratos

#### [test_rbac_multi_tenant.py](file:///Volumes/240/Code/oltapi/tests/unit/test_rbac_multi_tenant.py)
- Adicionar teste validando que usuários não-administradores recebem `403 Forbidden` ao tentar deletar uma OLT.
- Validar que Administrador (`SUPER_ADMIN` ou `TENANT_ADMIN`) executa `DELETE` com `204 No Content`.

#### [test_web_ui.py](file:///Volumes/240/Code/oltapi/tests/unit/test_web_ui.py)
- Adicionar validações de renderização do modal `modal-delete-olt` e do botão de confirmação defensiva.
