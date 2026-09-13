"""
Testes unitários para verificação e sincronização contínua do contrato OpenAPI.
Garante que o contrato OpenAPI estático em docs/api_contracts/
reflete exatamente as rotas e modelos Pydantic da aplicação FastAPI.
"""

from pathlib import Path
import yaml

from app.main import app
from scripts.export_openapi import export_openapi


def test_openapi_contract_sync(tmp_path: Path):
    """Verifica que a rotina de exportação gera arquivos válidos e parseáveis em YAML e JSON."""
    yaml_path, json_path = export_openapi(output_dir=tmp_path)

    assert yaml_path.exists(), "O arquivo openapi.yaml deve ser criado"
    assert json_path.exists(), "O arquivo openapi.json deve ser criado"
    assert yaml_path.stat().st_size > 0, "O arquivo openapi.yaml não pode estar vazio"
    assert json_path.stat().st_size > 0, "O arquivo openapi.json não pode estar vazio"

    # Valida integridade do YAML gerado
    with open(yaml_path, "r", encoding="utf-8") as f:
        spec = yaml.safe_load(f)

    live_openapi = app.openapi()
    assert spec["openapi"].startswith("3."), "Versão da especificação deve ser OpenAPI 3.x"
    assert spec["info"]["title"] == live_openapi["info"]["title"]
    assert spec["info"]["version"] == live_openapi["info"]["version"]

    # Valida que todos os endpoints registrados no FastAPI estão presentes no contrato gerado
    assert len(spec.get("paths", {})) == len(live_openapi.get("paths", {}))
    for path_key in live_openapi["paths"]:
        assert path_key in spec["paths"], f"Endpoint {path_key} ausente no contrato gerado"


def test_live_openapi_contracts_in_docs_exist_and_match():
    """Garante que a documentação oficial em docs/api_contracts/ está consistente e válida."""
    yaml_path, _ = export_openapi(output_dir=Path("docs/api_contracts"))
    assert yaml_path.exists()

    with open(yaml_path, "r", encoding="utf-8") as f:
        spec = yaml.safe_load(f)

    assert len(spec.get("paths", {})) >= 50, "Deve haver ao menos 50 endpoints na API"
