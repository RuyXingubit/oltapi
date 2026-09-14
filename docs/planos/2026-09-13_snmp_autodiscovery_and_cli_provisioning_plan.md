# Plano de Implementação: Auto-Descoberta e Provisionamento Automatizado de SNMP na OLT

## 1. Visão Geral do Objetivo
Alinhar a arquitetura de SNMP com o objetivo estratégico de longo prazo da plataforma: **eliminar a necessidade de o administrador e técnicos acessarem o terminal CLI das OLTs manualmente**.

O fluxo inteligente implementará:
1. **Auto-Descoberta Reversa via Running-Config / Backup:** Ao inspecionar ou analisar a OLT, se não houver comunidade SNMP válida na API, o sistema obtém a configuração do equipamento (running-config ou backup no banco) e analisa via driver do fabricante. Se houver comunidade em texto claro (Fiberhome, ZTE, Intelbras, VSOL), testa via UDP 161 e, se responder, atualiza e adota automaticamente no cadastro sem intervenção manual.
2. **Detecção de Comunidades Criptografadas (Huawei Cipher):** Se a OLT for Huawei e a comunidade estiver com hash (`snmp-server community read cipher %#%#...`), o sistema identifica o estado, sinaliza no diagnóstico e permite que o técnico informe a senha em texto plano.
3. **Provisionamento Automatizado pelo Admin (CLI ➔ Flash):** Caso a OLT não tenha SNMP ou a comunidade seja desconhecida, o Administrador pode definir uma nova comunidade diretamente pelo frontend. A API conecta via SSH/Telnet, aplica a sintaxe do fabricante em modo estritamente `RO` (Read-Only), salva na flash (`save`/`write`) e valida a porta UDP 161 no mesmo segundo.

---

## 2. Decisões Técnicas e Segurança

> [!IMPORTANT]
> **Permissão Estritamente Somente-Leitura (`RO`):**
> O comando gerado para todos os fabricantes sempre utilizará parâmetros de leitura (`read simple` na Huawei, `ro` na Fiberhome/ZTE/Intelbras/VSOL), garantindo que a comunidade não tenha permissões de escrita via SNMP v2c.

> [!NOTE]
> **RBAC / Controle de Acesso:**
> O endpoint de teste SNMP (`/snmp/test`) é permitido para operadores do NOC e Administradores. O endpoint de provisionamento de configuração na OLT (`/snmp/configure`) exige privilégio de `SUPER_ADMIN`.

---

## 3. Modificações Propostas

### A. Camada de Repositório e Modelos
- Adicionar método `update(olt: OLTInDB) -> OLTInDB` em `OLTRepository` e `SQLOLTRepository`.
- Adicionar campos de telemetria SNMP em `OLTXRayResponse` (`snmp_active`, `snmp_status`, `snmp_community`, `snmp_message`).
- Criar modelos `SNMPTestRequest`, `SNMPTestResponse`, `SNMPConfigureRequest`, `SNMPConfigureResponse` em `app/models/olt.py`.

### B. Camada de Drivers: Auto-Detecção e Configuração CLI
- **`BaseOLTDriver`**:
  - `extract_snmp_community(self, config_text: str) -> Tuple[Optional[str], bool]`
  - `configure_snmp(self, olt: OLTInDB, community: str, port: int = 161) -> bool`
- **`HuaweiVRPDriver`**:
  - Detecta cipher ou simple em `snmp-server community read ...`.
  - CLI: `system-view` ➔ `snmp-server sys-info version v2c` ➔ `snmp-server community read simple <community>` ➔ `return` ➔ `save \n y`.
- **`FiberhomeTL1Driver`**:
  - Detecta comunidade em running-config ou TL1.
  - CLI/TL1: `set-snmp-community` / telnet config ➔ persistência na flash.
- **`ZTEZXROSDriver`**, **`IntelbrasGSeriesDriver`**, **`Intelbras8820Driver`**, **`VSOLV1600Driver`**:
  - Regex de extração e comandos de provisionamento `RO` com gravação na flash (`write`).

### C. Camada de Serviços e API
- **`OLTTelemetryService`**:
  - Durante `inspect_chassis`: testa comunidade atual. Se falhar, faz auto-descoberta no running-config/backup. Se funcionar, salva no banco. Se for cipher, sinaliza no diagnóstico. Se não houver, sinaliza que o admin pode provisionar.
- **`app/api/v1/endpoints_olts.py`**:
  - `POST /api/v1/olts/{olt_id}/snmp/test`
  - `POST /api/v1/olts/{olt_id}/snmp/configure`

### D. Interface do Usuário (Frontend)
- Adicionar campos e botões para teste rápido e provisionamento direto no modal de OLT e na telemetria.

---

## 4. Plano de Verificação
- Testes unitários com `pytest tests/unit/test_chassis_telemetry_and_snmp.py`.
- Sincronização OpenAPI via `python -m scripts.export_openapi`.
