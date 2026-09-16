# OLTAPI - Regras e Diretrizes do Projeto para Agentes e Desenvolvedores

## 1. Sincronização Obrigatória do OpenAPI antes de Commit & Push
Antes de qualquer commit e push, é MANDATÓRIO executar o script de exportação do contrato OpenAPI:
```bash
python -m scripts.export_openapi
```
Os contratos gerados em `docs/api_contracts/openapi.yaml` e `docs/api_contracts/openapi.json` devem ser adicionados ao commit.

## 2. Cobertura de Testes Unitários
Sempre que uma feature ou correção for criada, execute `pytest` para certificar que 100% dos testes passam e nenhuma regressão ocorreu.

## 3. Segurança em Primeiro Lugar
Toda alteração deve manter ou aumentar os padrões de segurança (sanitização de inputs, validação de tokens JWT, chaves de API com hash e RBAC multi-tenant).

## 4. Histórico de Planos Aprovados (`docs/planos/`)
Somente planos de implementação aprovados explicitamente pelo usuário (e seus respectivos walkthroughs de conclusão) devem ser arquivados em `docs/planos/` (ex: `docs/planos/YYYY-MM-DD_<tema>_plan.md` e `docs/planos/YYYY-MM-DD_<tema>_walkthrough.md`) e commitados no repositório Git. Rascunhos ou planos em debate descartados não devem poluir a pasta.

## 5. Governança de Drivers, Inversão de Dependência & Zero Código Teórico
- Toda OLT adicionada DEVE herdar de `BaseOLTDriver` e se auto-registrar no `DriverRegistry` via `@register_driver`.
- **Proibição de Fabricantes Teóricos:** É TERMINANTEMENTE PROIBIDO adicionar novos drivers de fabricantes sem acesso a hardware físico de bancada para homologação real. Drivers só entram na árvore do projeto após teste de bancada física aprovado pelo usuário.
- **Isolamento Radical (Ports & Adapters):** Um driver nunca deve importar outro driver. Proibido utilizar `hasattr(driver, ...)` ou condicionais de fabricante (`if olt.vendor == ...`) nos serviços de negócio. A camada de serviço conversa exclusivamente com métodos polimórficos da interface `BaseOLTDriver`.
- **Padrão Canônico de Backup:** Todo driver deve tentar prioritariamente o envio por FTP com a sintaxe nativa da OLT; caso nenhum FTP esteja vinculado ou o upload falhe, o driver DEVE fazer fallback automático para captura do `running-config` pelo terminal (SSH/Telnet).
- **Suíte de Conformidade (`BaseDriverComplianceTest`):** Todo driver ativo deve passar na suíte de conformidade cobrindo: `get_running_config`, `backup_config` (FTP + fallback), `get_chassis_interfaces` (sem dados inventados), `get_onu_details` (sinal óptico real), `provision_onu`, `deprovision_onu`, `suspend_onu`, `resume_onu`, `reboot_onu`, `configure_snmp`, `list_all_authorized_onus`, `inspect_management_arch` e `execute_wizard_commissioning`.

## 6. Desacoplamento API-First & Zero Hardcode
O backend é 100% REST JSON. O client e os serviços nunca presumem portas, perfis ou formatos hardcoded; todo dado operacional deve ser derivado diretamente do hardware ou da API. É proibido manter arquivos estáticos ou páginas web servidas pelo backend (`app/static/`).

