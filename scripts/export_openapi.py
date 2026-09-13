"""
Script de exportação e sincronização automática do contrato OpenAPI.
Exporta os esquemas OpenAPI 3.1 da aplicação FastAPI para:
- docs/api_contracts/openapi.yaml
- docs/api_contracts/openapi.json
"""

import json
import logging
from pathlib import Path
from typing import Tuple
import yaml

from app.main import app

logger = logging.getLogger(__name__)


def export_openapi(output_dir: Path = Path("docs/api_contracts")) -> Tuple[Path, Path]:
    """Exporta o schema OpenAPI dinâmico gerado pelo FastAPI para arquivos estáticos YAML e JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)
    schema = app.openapi()

    yaml_path = output_dir / "openapi.yaml"
    json_path = output_dir / "openapi.json"

    # Salva em formato YAML
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(schema, f, allow_unicode=True, sort_keys=False)

    # Salva em formato JSON formatado
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)

    total_paths = len(schema.get("paths", {}))
    total_schemas = len(schema.get("components", {}).get("schemas", {}))
    print(
        f"[OpenAPI Sync] Exportado com sucesso: {total_paths} endpoints e "
        f"{total_schemas} esquemas salvos em {yaml_path} e {json_path}."
    )
    return yaml_path, json_path


if __name__ == "__main__":
    export_openapi()
