"""
Instalador automático dos Git Hooks para o repositório OLTAPI.
Garante que os hooks de pre-commit e pre-push estejam devidamente instalados na pasta .git/hooks.
"""

from pathlib import Path
import os
import stat

PRE_COMMIT_CONTENT = """#!/bin/sh
# Git Pre-commit Hook: Sincronização obrigatória do OpenAPI
set -e

echo "==> [Pre-commit] Executando sincronização do contrato OpenAPI..."

if [ -f "./.venv/bin/python" ]; then
    PYTHON_EXEC="./.venv/bin/python"
else
    PYTHON_EXEC="python"
fi

$PYTHON_EXEC -m scripts.export_openapi

git add docs/api_contracts/openapi.yaml docs/api_contracts/openapi.json
echo "==> [Pre-commit] Contratos OpenAPI sincronizados com sucesso."
"""

PRE_PUSH_CONTENT = """#!/bin/sh
# Git Pre-push Hook: Validação de sincronia do contrato OpenAPI
set -e

echo "==> [Pre-push] Validando integridade e sincronismo dos contratos OpenAPI..."

if [ -f "./.venv/bin/python" ]; then
    PYTHON_EXEC="./.venv/bin/python"
else
    PYTHON_EXEC="python"
fi

$PYTHON_EXEC -m scripts.export_openapi

if ! git diff --exit-code docs/api_contracts/ > /dev/null 2>&1; then
    echo "ERRO: Os contratos em docs/api_contracts/ estão desatualizados em relação ao código da API."
    echo "Execute 'git add docs/api_contracts/' e realize o commit antes do push."
    exit 1
fi

echo "==> [Pre-push] Contratos validados e sincronizados com sucesso."
"""


def install_hooks():
    git_dir = Path(".git")
    if not git_dir.exists():
        print("Diretório .git não encontrado.")
        return

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    pre_commit = hooks_dir / "pre-commit"
    pre_commit.write_text(PRE_COMMIT_CONTENT, encoding="utf-8")
    pre_commit.chmod(pre_commit.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    pre_push = hooks_dir / "pre-push"
    pre_push.write_text(PRE_PUSH_CONTENT, encoding="utf-8")
    pre_push.chmod(pre_push.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    print("[Git Hooks] Hooks pre-commit e pre-push instalados com sucesso!")


if __name__ == "__main__":
    install_hooks()
