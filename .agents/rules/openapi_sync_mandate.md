# DIRETRIZ MANDATÓRIA: SINCRONIZAÇÃO OBRIGATÓRIA DO CONTRATO OPENAPI

Antes de realizar QUALQUER commit ou push no repositório, é MANDATÓRIO executar o script de sincronização e exportação do OpenAPI:

```bash
python -m scripts.export_openapi
```

## Diretrizes de Execução:
1. **Sincronização Contínua**: O comando acima regenera automaticamente `docs/api_contracts/openapi.yaml` e `docs/api_contracts/openapi.json` diretamente do schema em tempo de execução do FastAPI.
2. **Inclusão no Commit**: Se houver qualquer alteração em rotas, parâmetros, modelos Pydantic ou documentação, os arquivos gerados em `docs/api_contracts/` DEVEM ser incluídos no mesmo commit (`git add docs/api_contracts/`).
3. **Validação nos Testes**: A suíte de testes (`pytest`) contém o teste `tests/unit/test_openapi_sync.py` que falhará se houver incompatibilidades no schema.
4. **Proteção de CI/CD**: O pipeline do GitHub Actions valida que o diff de `docs/api_contracts/` é zero após rodar o script; alterações submetidas sem a execução do script serão rejeitadas.
