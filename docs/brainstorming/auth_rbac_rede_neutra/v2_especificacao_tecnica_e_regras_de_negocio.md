# Brainstorming: Especificação Técnica, RBAC & Rede Neutra Granular (v2)

**Data:** 12/09/2026  
**Status:** Especificação Consolidada pós-Feedback do Usuário  
**Autor:** Antigravity AI & Ruy

---

## 1. Decisões Consolidadas

Com base nas definições do usuário:
1. **Inquilinos e Usuários criados pelo Admin:**
   - O Admin cadastra o Inquilino (`Tenant`), define seu tipo (`PROVIDER_OWNER` ou `NEUTRAL_OPERATOR`), cria o usuário principal e vincula a uma ou mais OLTs com suas respectivas VLANs permitidas.
   - Usuários do Provedor (NOC / Master) possuem acesso irrestrito a todas as OLTs e VLANs.
2. **Descoberta de ONUs Flexível (Web e API):**
   - Suporte a listagem geral de ONUs não autorizadas da OLT permitida (`GET /api/v1/olts/{olt_id}/unauthorized`) E filtro direto por serial (`GET /api/v1/olts/{olt_id}/unauthorized?serial={serial}`).
   - Na API (ERP), o cliente faz polling até o serial aparecer.
   - Na Web UI (quando for construída), o operador digita o serial e a tela monitora em tempo real até a ONU sincronizar no slot/pon.
   - Ao autorizar, o usuário escolhe:
     - Modo: **Router** (PPPoE/IPv4/IPv6) ou **Bridge**;
     - Perfil de Fabricante: **Padrão** ou **Terceiro** (ex: perfil VEIP para Fiberhome com Intelbras/Huawei/ZTE);
     - VLAN: Selecionada a partir das VLANs autorizadas para aquele operador naquela OLT.
3. **Escopos Granulares de API Keys:**
   - Quanto mais granular melhor. As chaves de API podem ser emitidas limitando ações pontuais (ex: apenas leitura de potência óptica, ou apenas provisionamento).

---

## 2. Dicionário de Escopos Granulares (Scopes)

| Escopo | Descrição | Endpoints Abrangidos |
| :--- | :--- | :--- |
| `olts:read` | Consultar status, portas e lista de OLTs autorizadas | `GET /olts`, `GET /olts/{id}` |
| `olts:admin` | Gerenciar configurações e conexões de OLT | `POST /olts`, `PUT /olts/{id}`, etc. |
| `onus:read` | Listar inventário de ONUs e consultar detalhes | `GET /onus`, `GET /onus/{id}`, `GET /olts/{id}/ports/{port}/onus` |
| `onus:discover` | Consultar ONUs não autorizadas na OLT | `GET /olts/{id}/unauthorized` |
| `onus:provision` | Provisionar e autorizar novas ONUs | `POST /olts/{id}/onus` |
| `onus:deprovision` | Desprovisionar e remover ONUs da OLT | `DELETE /olts/{id}/onus/{serial}` |
| `onus:actions` | Ações de controle (reiniciar, suspender, reativar) | `POST /olts/{id}/onus/{serial}/reboot`, `/suspend`, `/resume` |
| `diagnostics:read` | Leitura de potência óptica e status de enlace | `GET /olts/{id}/onus/{serial}/optical-power`, `GET /diagnostics/...` |
| `backups:read` | Listar metadados e baixar backups | `GET /olts/{id}/backups`, `GET /backups/...` |
| `backups:create` | Disparar coleta de backup sob demanda | `POST /olts/{id}/backups` |
| `vlans:read` | Listar VLANs cadastradas e alocadas | `GET /olts/{id}/vlans` |
| `api_keys:manage` | Criar e revogar chaves de API secundárias | `GET /api-keys`, `POST /api-keys`, `DELETE /api-keys/{id}` |

---

## 3. Modelo Relacional & Estrutura das Tabelas (SQLAlchemy / PostgreSQL)

Todas as chaves primárias usam **UUIDv7** (`app.core.uuid.uuid7_str`):

### 3.1. `tenants`
- `id` (VARCHAR(36), PK): UUIDv7
- `name` (VARCHAR(64), UNIQUE, NOT NULL): Ex: "Provedor Dono", "Operadora Alpha"
- `type` (VARCHAR(32), NOT NULL): `"PROVIDER_OWNER"` ou `"NEUTRAL_OPERATOR"`
- `is_active` (BOOLEAN, NOT NULL, DEFAULT TRUE)
- `created_at` (TIMESTAMP WITH TIME ZONE, NOT NULL)

### 3.2. `users`
- `id` (VARCHAR(36), PK): UUIDv7
- `tenant_id` (VARCHAR(36), FK `tenants.id`, ON DELETE CASCADE, NOT NULL)
- `name` (VARCHAR(128), NOT NULL)
- `email` (VARCHAR(128), UNIQUE, INDEX, NOT NULL)
- `password_hash` (VARCHAR(256), NOT NULL)
- `role` (VARCHAR(32), NOT NULL): `"SUPER_ADMIN"`, `"NOC"`, `"FIELD_TECH"`, `"TENANT_ADMIN"`, `"TENANT_TECH"`
- `is_active` (BOOLEAN, NOT NULL, DEFAULT TRUE)
- `created_at` (TIMESTAMP WITH TIME ZONE, NOT NULL)
- `updated_at` (TIMESTAMP WITH TIME ZONE, NOT NULL)

### 3.3. `user_olt_permissions`
- `id` (VARCHAR(36), PK): UUIDv7
- `user_id` (VARCHAR(36), FK `users.id`, ON DELETE CASCADE, NOT NULL)
- `olt_id` (VARCHAR(36), FK `olts.id`, ON DELETE CASCADE, NOT NULL)
- `created_at` (TIMESTAMP WITH TIME ZONE, NOT NULL)
- *Índice Único:* `(user_id, olt_id)`

### 3.4. `tenant_vlan_allocations`
- `id` (VARCHAR(36), PK): UUIDv7
- `tenant_id` (VARCHAR(36), FK `tenants.id`, ON DELETE CASCADE, NOT NULL)
- `olt_id` (VARCHAR(36), FK `olts.id`, ON DELETE CASCADE, NOT NULL)
- `vlan_id` (INTEGER, NOT NULL): 1 a 4094
- `description` (VARCHAR(128), NULLABLE): Ex: "VLAN 100 FTTH VTX"
- `created_at` (TIMESTAMP WITH TIME ZONE, NOT NULL)
- *Índice Único:* `(tenant_id, olt_id, vlan_id)`

### 3.5. `api_keys`
- `id` (VARCHAR(36), PK): UUIDv7
- `tenant_id` (VARCHAR(36), FK `tenants.id`, ON DELETE CASCADE, NOT NULL)
- `user_id` (VARCHAR(36), FK `users.id`, ON DELETE CASCADE, NOT NULL)
- `name` (VARCHAR(64), NOT NULL): Ex: "ERP IXC Operadora Alpha"
- `key_prefix` (VARCHAR(16), INDEX, NOT NULL): Ex: `olt_live_vtx1a_`
- `key_hash` (VARCHAR(128), UNIQUE, INDEX, NOT NULL): SHA-256 da chave completa
- `scopes` (TEXT, NOT NULL): JSON serializado com os escopos autorizados
- `is_active` (BOOLEAN, NOT NULL, DEFAULT TRUE)
- `expires_at` (TIMESTAMP WITH TIME ZONE, NULLABLE)
- `last_used_at` (TIMESTAMP WITH TIME ZONE, NULLABLE)
- `created_at` (TIMESTAMP WITH TIME ZONE, NOT NULL)

### 3.6. Atualização em `onus_inventory`
- `tenant_id` (VARCHAR(36), FK `tenants.id`, ON DELETE SET NULL, NULLABLE, INDEX): Permite atribuir a titularidade direta de cada ONU no inventário.

---

## 4. Algoritmo de Validação do SecurityContext

A dependência FastAPI `get_current_security_context` avalia o chamador e gera um objeto imutável `SecurityContext`:

```python
class SecurityContext:
    caller_type: str # "MASTER_KEY", "DYNAMIC_API_KEY", "USER_JWT"
    user_id: Optional[str]
    tenant_id: Optional[str]
    role: str
    scopes: Set[str] # ["*"] para Master Key / SUPER_ADMIN
    allowed_olt_ids: Optional[Set[str]] # None significa todas
    allowed_vlans: Optional[Dict[str, Set[int]]] # {olt_id: {100, 101}}

    def enforce_scope(self, required_scope: str):
        if "*" in self.scopes or required_scope in self.scopes:
            return
        raise HTTPException(status_code=403, detail=f"Escopo insuficiente: requer '{required_scope}'")

    def enforce_olt(self, olt_id: str):
        if self.allowed_olt_ids is None or olt_id in self.allowed_olt_ids:
            return
        raise HTTPException(status_code=403, detail=f"Acesso não autorizado à OLT '{olt_id}'")

    def enforce_vlan(self, olt_id: str, vlan: int):
        if self.allowed_vlans is None:
            return # Acesso irrestrito a VLANs (admin / NOC)
        olt_vlans = self.allowed_vlans.get(olt_id, set())
        if vlan not in olt_vlans:
            raise HTTPException(
                status_code=403,
                detail=f"VLAN {vlan} não autorizada para seu operador nesta OLT. VLANs permitidas: {sorted(list(olt_vlans))}"
            )
```

---

## 5. Seed Inicial / Bootstrap Automático

Na inicialização (`init_db()`):
1. Verifica se a tabela `tenants` está vazia.
2. Cria o Tenant Matriz: `id: uuid7_str()`, `name: "Provedor Matriz"`, `type: "PROVIDER_OWNER"`.
3. Cria o usuário Admin padrão: `email: "admin@oltapi.local"`, vinculado ao Tenant Matriz com perfil `SUPER_ADMIN`.
4. Garante que se o chamador utilizar a `API_KEY` do `.env`, ela sempre receberá o `SecurityContext` com `SUPER_ADMIN` e escopo `["*"]`.
