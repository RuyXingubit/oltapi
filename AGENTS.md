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
