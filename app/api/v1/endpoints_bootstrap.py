from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_backup_storage, get_olt_repo, require_api_key
from app.drivers.factory import DriverFactory
from app.models.bootstrap import (
    BootstrapApplyResponse,
    BootstrapPreviewResponse,
    BootstrapRequest,
)
from app.storage.backup_storage import BackupStorage
from app.storage.olt_repository import OLTRepository

router = APIRouter(prefix="/olts", tags=["Bootstrap & Autoconfig Inicial"], dependencies=[Depends(require_api_key)])


@router.post("/{olt_id}/bootstrap/preview", response_model=BootstrapPreviewResponse)
def preview_bootstrap(
    olt_id: str,
    req: BootstrapRequest,
    repo: OLTRepository = Depends(get_olt_repo),
):
    """
    Gera o script CLI de inicialização (Dry-Run / Simulação) para conferência antes de aplicar na OLT.
    Baseado nas diretrizes oficiais da ferramenta de auto-configuração da Intelbras.
    """
    olt = repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    try:
        driver = DriverFactory.get_driver(olt)
        commands = driver.generate_bootstrap_commands(req)
        script_text = "\n".join(commands)

        return BootstrapPreviewResponse(
            olt_id=olt.id,
            mode=req.mode,
            commands=commands,
            script_text=script_text,
            total_commands=len(commands),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except NotImplementedError as e:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao gerar preview: {str(e)}")


@router.post("/{olt_id}/bootstrap/apply", response_model=BootstrapApplyResponse, status_code=status.HTTP_200_OK)
def apply_bootstrap(
    olt_id: str,
    req: BootstrapRequest,
    repo: OLTRepository = Depends(get_olt_repo),
    storage: BackupStorage = Depends(get_backup_storage),
):
    """
    Aplica a configuração inicial na OLT física (Zero-Touch Provisioning):
    1. Executa a sequência de comandos CLI na OLT via SSH.
    2. Habilita o auto-service para provisionamento automático das ONUs.
    3. Grava as alterações na memória não-volátil da OLT ('write').
    4. Gera e salva automaticamente um backup inicial com UUIDv7 e hash SHA-256 para restauração.
    """
    olt = repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    try:
        driver = DriverFactory.get_driver(olt)

        # Executa a configuração inicial
        total_executed = driver.apply_bootstrap(olt, req)

        # Gera backup de ponto de restauração imediato após aplicação
        backup_content = driver.backup_config(olt)
        backup_meta = storage.save_backup(olt_id=olt.id, content=backup_content)

        return BootstrapApplyResponse(
            success=True,
            olt_id=olt.id,
            backup_id=backup_meta.backup_id,
            total_commands_executed=total_executed,
            message=f"Configuração inicial aplicada com sucesso na OLT '{olt.name}'. Backup de segurança gerado ({backup_meta.backup_id}).",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except NotImplementedError as e:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao aplicar bootstrap: {str(e)}")
