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

## 5. Governança de Drivers & Orientação a Objetos Pura
Toda OLT adicionada DEVE herdar de `BaseOLTDriver`. Proibido utilizar `hasattr` ou checagens de `vendor` nos serviços de negócio. Cada driver deve cumprir a suíte obrigatória de conformidade (`BaseDriverComplianceTest`) cobrindo: `get_running_config`, `backup_config`, `get_chassis_interfaces` (sem dados inventados), `get_onu_details` (sinal óptico real), `provision_onu`, `deprovision_onu`, `suspend_onu`, `resume_onu`, `reboot_onu` e `configure_snmp`.

## 6. Desacoplamento API-First & Zero Hardcode
O backend é 100% REST JSON. O client e os serviços nunca presumem portas, perfis ou formatos hardcoded; todo dado operacional deve ser derivado diretamente do hardware ou da API.

