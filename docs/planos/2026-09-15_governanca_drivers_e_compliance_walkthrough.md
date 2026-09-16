# Walkthrough: Saneamento Arquitetural de Drivers, Conformidade e API-First

## Resumo Executivo
Executada a refatoração completa da camada de adaptadores de hardware (OLT Drivers) do OLTAPI, consolidando o princípio de Inversão de Dependência (SOLID / Ports & Adapters), eliminando 100% dos códigos teóricos não testados em bancada física, desacoplando o backend de arquivos estáticos legados e garantindo conformidade via testes unitários e sincronização OpenAPI.

## Alterações Realizadas

### 1. Inversão de Dependência & Dynamic Registry
- **`app/drivers/registry.py`**: Criado `DriverRegistry` dinâmico com decorador `@DriverRegistry.register` para auto-descoberta e registro isolado dos drivers.
- **`app/drivers/factory.py`**: Refatorado para consultar exclusivamente `DriverRegistry.get_driver_class(olt.vendor)`. Eliminados todos os `if/elif` por fabricante.
- **`app/drivers/base.py`**: Adicionada propriedade canônica `handles_primary_ftp_upload: bool = False` e métodos polimórficos canônicos `inspect_management_arch` e `execute_wizard_commissioning`.

### 2. Extirpação de Fabricantes Teóricos ("Zero Dados Falsos")
- Removidos do repositório:
  - `app/drivers/huawei/`
  - `app/drivers/zte/`
  - `app/drivers/intelbras/`
  - `tests/unit/test_huawei_driver.py`
  - `tests/unit/test_zte_driver.py`
  - `tests/unit/test_intelbras_8820_parser.py`
  - `tests/unit/test_intelbras_gseries.py`
- Drivers ativos no repositório:
  - **FiberhomeTL1Driver** (`vendor=OLTVendor.FIBERHOME`): Homologado em bancada física.
  - **VSOLV1600Driver** (`vendor=OLTVendor.VSOL`): Homologado na bancada atual.

### 3. Padrão Canônico de Backup (FTP Nativo + Fallback Gracioso)
- Ambos os drivers e a camada de serviço (`BackupService`) implementam o fluxo:
  1. Tentativa primária de upload para o servidor FTP cadastrado via sintaxe CLI nativa da OLT.
  2. Caso nenhum FTP esteja configurado ou ocorra falha de rede/credencial, fallback imediato para captura do `running-config` pelo terminal display (SSH/Telnet) e criptografia AES-128 Fernet em disco.

### 4. Saneamento dos Serviços (Eliminação de hasattr e regex de marca)
- `app/services/backup_service.py`: Substituído `if vendor == "fiberhome"` por `if driver.handles_primary_ftp_upload`.
- `app/services/olt_onboarding_service.py`: Removidos todos os `hasattr(driver, ...)` e fallbacks com regex específico de marca. Toda inspeção e comissionamento trafega exclusivamente pela interface polimórfica `BaseOLTDriver`.
- `app/services/olt_telemetry_service.py`: Removida geração de firmware sintético/fake (`f"{olt.vendor.upper()}-V2.1.0-BUILD2026"`). Retorna `None` quando a OLT física não reporta versão de firmware.

### 5. Desacoplamento Radical API-First
- Removida pasta `app/static/` (`style.css`, `index.html`, `app.js`).
- `app/main.py`: Eliminadas importações e montagem de `/static`. A rota raiz `GET /` agora retorna exclusivamente JSON operacional padronizado.
- `tests/unit/test_web_ui.py`: Refatorado para validar os contratos da raiz REST JSON e a injeção dos cabeçalhos OWASP (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `X-XSS-Protection`).

### 6. Suíte de Conformidade de Drivers
- Criado `tests/unit/test_driver_compliance.py` implementando a classe abstrata `BaseDriverComplianceTest` com 12 testes de conformidade obrigatórios para cada driver ativo:
  1. `test_compliance_get_running_config`
  2. `test_compliance_backup_primary_ftp`
  3. `test_compliance_backup_fallback_terminal`
  4. `test_compliance_chassis_interfaces_no_fake_data`
  5. `test_compliance_onu_details_optical_power`
  6. `test_compliance_onu_lifecycle_provision`
  7. `test_compliance_onu_lifecycle_deprovision`
  8. `test_compliance_onu_lifecycle_suspend`
  9. `test_compliance_onu_lifecycle_resume`
  10. `test_compliance_onu_lifecycle_reboot`
  11. `test_compliance_configure_snmp`
  12. `test_compliance_list_all_authorized_onus`

## Validação e Resultados
- **Testes Unitários:** 219/219 testes aprovados (100% de sucesso).
- **Contratos OpenAPI:** Exportados e validados em `docs/api_contracts/openapi.yaml` e `docs/api_contracts/openapi.json`.
- **Governança:** Regras atualizadas em `AGENTS.md` e `.agents/rules/governanca_drivers_e_api_first.md`.
