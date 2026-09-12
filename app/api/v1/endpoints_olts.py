import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import FileResponse

from app.api.deps import (
    get_backup_storage,
    get_ftp_repo,
    get_olt_repo,
    get_sync_service,
    require_api_key,
)
from app.drivers.factory import DriverFactory
from app.models.vlan import SyncOLTResponse
from app.models.backup import (
    BackupAuditReport,
    BackupDiffResult,
    BackupMetadata,
    PurgePolicy,
    PurgeResult,
)
from app.models.hateoas import Link
from app.models.olt import (
    ConnectionTestResult,
    OLTConfigResponse,
    OLTCreateRequest,
    OLTResponse,
)
from app.services.connection_service import test_olt_connectivity
from app.services.ftp_service import FTPService
from app.storage.backup_storage import BackupStorage
from app.storage.olt_repository import OLTRepository
from app.storage.sql.ftp_repository import SQLFTPRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/olts", tags=["OLTs & Backups"], dependencies=[Depends(require_api_key)])


@router.get("", response_model=List[OLTResponse])
def list_olts(repo: OLTRepository = Depends(get_olt_repo)):
    """Lista todas as OLTs cadastradas com links de navegação rápida."""
    olts = repo.list_all()
    return [
        OLTResponse(
            id=o.id,
            name=o.name,
            vendor=o.vendor,
            model=o.model,
            host=o.host,
            port=o.port,
            protocol=o.protocol,
            created_at=o.created_at,
            status="registered",
            links={
                "self": Link(href=f"/api/v1/olts/{o.id}", method="GET", description="Detalhes da OLT"),
                "config": Link(href=f"/api/v1/olts/{o.id}/config", method="GET", description="Running-config e interfaces"),
                "unauthorized_onus": Link(href=f"/api/v1/olts/{o.id}/unauthorized", method="GET", description="ONUs pendentes"),
                "backups": Link(href=f"/api/v1/olts/{o.id}/backups", method="GET", description="Histórico de backups"),
            },
        )
        for o in olts
    ]


@router.post("", response_model=OLTResponse, status_code=status.HTTP_201_CREATED)
async def create_olt(
    req: OLTCreateRequest,
    response: Response,
    repo: OLTRepository = Depends(get_olt_repo),
):
    """
    Cadastra uma nova OLT no inventário, executa teste de conectividade rápido
    e retorna o cabeçalho Location e links de fluxo guiados pelo status de conexão.
    """
    olt = repo.create(req)
    response.headers["Location"] = f"/api/v1/olts/{olt.id}"

    # Validação rápida de conectividade para guiar os próximos passos
    conn_result = await test_olt_connectivity(olt_id=olt.id, host=olt.host, port=olt.port)
    olt_status = "online" if conn_result.reachable else "unreachable"

    return OLTResponse(
        id=olt.id,
        name=olt.name,
        vendor=olt.vendor,
        model=olt.model,
        host=olt.host,
        port=olt.port,
        protocol=olt.protocol,
        status=olt_status,
        connection_message=conn_result.message,
        created_at=olt.created_at,
        links=conn_result.links,
    )


@router.get("/{olt_id}", response_model=OLTResponse)
def get_olt(olt_id: str, repo: OLTRepository = Depends(get_olt_repo)):
    """Consulta os detalhes cadastrais de uma OLT específica com seus links de ação."""
    olt = repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    return OLTResponse(
        id=olt.id,
        name=olt.name,
        vendor=olt.vendor,
        model=olt.model,
        host=olt.host,
        port=olt.port,
        protocol=olt.protocol,
        status="registered",
        created_at=olt.created_at,
        links={
            "self": Link(href=f"/api/v1/olts/{olt.id}", method="GET", description="Detalhes desta OLT"),
            "config": Link(href=f"/api/v1/olts/{olt.id}/config", method="GET", description="Running-config e interfaces"),
            "unauthorized_onus": Link(href=f"/api/v1/olts/{olt.id}/unauthorized", method="GET", description="ONUs pendentes"),
            "backups": Link(href=f"/api/v1/olts/{olt.id}/backups", method="GET", description="Histórico de backups"),
            "test_connection": Link(href=f"/api/v1/olts/{olt.id}/test-connection", method="POST", description="Retestar conexão TCP"),
        },
    )


@router.post("/{olt_id}/test-connection", response_model=ConnectionTestResult)
async def test_connection(olt_id: str, repo: OLTRepository = Depends(get_olt_repo)):
    """Executa teste de conectividade sob demanda e retorna diagnóstico e links de fluxo."""
    olt = repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    return await test_olt_connectivity(olt_id=olt.id, host=olt.host, port=olt.port)


@router.get("/{olt_id}/config", response_model=OLTConfigResponse)
def get_olt_config(olt_id: str, repo: OLTRepository = Depends(get_olt_repo)):
    """Coleta e visualiza o running-config completo da OLT."""
    olt = repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    try:
        driver = DriverFactory.get_driver(olt)
        config_text = driver.get_running_config(olt)
        return OLTConfigResponse(
            olt_id=olt.id,
            config_text=config_text,
            links={
                "self": Link(href=f"/api/v1/olts/{olt.id}/config", method="GET", description="Running-config da OLT"),
                "olt": Link(href=f"/api/v1/olts/{olt.id}", method="GET", description="Detalhes cadastrais da OLT"),
                "trigger_backup": Link(href=f"/api/v1/olts/{olt.id}/backups", method="POST", description="Salvar configuração atual em backup"),
                "backups": Link(href=f"/api/v1/olts/{olt.id}/backups", method="GET", description="Listar histórico de backups"),
            },
        )
    except ConnectionError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao obter configuração: {str(e)}")


@router.get("/{olt_id}/backups", response_model=List[BackupMetadata])
def list_backups(
    olt_id: str,
    repo: OLTRepository = Depends(get_olt_repo),
    storage: BackupStorage = Depends(get_backup_storage),
):
    """Lista o histórico de backups realizados para a OLT com links de download e comparação."""
    olt = repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")
    backups = storage.list_by_olt(olt_id)
    for b in backups:
        b.links = {
            "download": Link(href=f"/api/v1/olts/{olt_id}/backups/{b.backup_id}/download", method="GET", description="Download do arquivo .cfg"),
            "compare": Link(href=f"/api/v1/olts/{olt_id}/backups/compare?target_id={b.backup_id}", method="GET", description="Comparar com backup anterior"),
        }
    return backups


@router.post("/{olt_id}/backups", response_model=BackupMetadata, status_code=status.HTTP_201_CREATED)
def trigger_backup(
    olt_id: str,
    response: Response,
    repo: OLTRepository = Depends(get_olt_repo),
    storage: BackupStorage = Depends(get_backup_storage),
    ftp_repo: SQLFTPRepository = Depends(get_ftp_repo),
):
    """Dispara a rotina de backup na OLT, salva em disco e retorna Location header e links de download e diff."""
    olt = repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    # Busca destinos FTP efetivos (específicos vinculados + globais padrão)
    raw_ftps = []
    if ftp_repo:
        try:
            destinations = ftp_repo.get_destinations_for_olt(olt.id)
            for d in destinations.effective_destinations:
                raw = ftp_repo.get_raw_by_id(d.id)
                if raw and raw.is_active:
                    raw_ftps.append(raw)
        except Exception as e:
            logger.warning(f"Erro ao obter destinos FTP para OLT {olt.id}: {e}")

    try:
        driver = DriverFactory.get_driver(olt)
        content = driver.backup_config(olt, ftp_servers=raw_ftps)
        metadata = storage.save_backup(olt_id=olt.id, content=content)

        # Replicação para servidores FTP secundários / adicionais
        if raw_ftps:
            vendor_str = olt.vendor.value if hasattr(olt.vendor, "value") else str(olt.vendor)
            targets_to_mirror = raw_ftps[1:] if vendor_str.lower() == "fiberhome" else raw_ftps

            for target in targets_to_mirror:
                try:
                    remote_name = f"backup_{olt.id}_{metadata.backup_id}.cfg"
                    FTPService.upload_file(
                        host=target.host,
                        port=target.port,
                        username=target.username,
                        password=target.password,
                        remote_filename=remote_name,
                        content=content,
                        base_path=target.base_path or "/",
                    )
                    logger.info(f"Backup replicado com sucesso para FTP secundário '{target.name}' ({target.host})")
                except Exception as e:
                    logger.error(f"Erro ao replicar backup para FTP '{target.name}': {e}")

        # Cabeçalho Location e links HATEOAS
        response.headers["Location"] = f"/api/v1/olts/{olt.id}/backups/{metadata.backup_id}/download"
        metadata.links = {
            "download": Link(href=f"/api/v1/olts/{olt.id}/backups/{metadata.backup_id}/download", method="GET", description="Download direto do arquivo de backup"),
            "compare": Link(href=f"/api/v1/olts/{olt.id}/backups/compare?target_id={metadata.backup_id}", method="GET", description="Comparar alterações em relação ao backup anterior"),
            "audit": Link(href=f"/api/v1/olts/{olt.id}/backups/audit", method="GET", description="Auditar integridade de backups desta OLT"),
        }
        return metadata
    except ConnectionError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao realizar backup: {str(e)}")



@router.get("/{olt_id}/backups/{backup_id}/download")
def download_backup(
    olt_id: str,
    backup_id: str,
    repo: OLTRepository = Depends(get_olt_repo),
    storage: BackupStorage = Depends(get_backup_storage),
):
    """Entrega o arquivo bruto de backup para download seguro pelo ERP ou técnico."""
    olt = repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    file_path = storage.get_backup_path(olt_id=olt_id, backup_id=backup_id)
    if not file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Backup '{backup_id}' não encontrado ou inválido.")

    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type="application/octet-stream",
    )


@router.get("/{olt_id}/backups/audit", response_model=BackupAuditReport)
def audit_olt_backups(
    olt_id: str,
    repo: OLTRepository = Depends(get_olt_repo),
    storage: BackupStorage = Depends(get_backup_storage),
):
    """Retorna relatório de integridade, contagem e detecção de alteração de configuração da OLT."""
    olt = repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")
    return storage.audit_olt(olt_id=olt.id, olt_name=olt.name)


@router.get("/{olt_id}/backups/compare", response_model=BackupDiffResult)
def compare_olt_backups(
    olt_id: str,
    base_id: Optional[str] = None,
    target_id: Optional[str] = None,
    repo: OLTRepository = Depends(get_olt_repo),
    storage: BackupStorage = Depends(get_backup_storage),
):
    """Compara dois backups da OLT calculando status de integridade SHA-256 e unified diff."""
    olt = repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    diff_res = storage.compare_backups(olt_id=olt_id, base_backup_id=base_id, target_backup_id=target_id)
    if not diff_res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Não foi possível comparar os backups. Verifique se existem backups suficientes ou se os IDs informados são válidos.",
        )
    return diff_res


@router.post("/{olt_id}/backups/purge", response_model=PurgeResult)
def purge_olt_backups(
    olt_id: str,
    policy: Optional[PurgePolicy] = None,
    repo: OLTRepository = Depends(get_olt_repo),
    storage: BackupStorage = Depends(get_backup_storage),
):
    """Aplica política de expurgo e retenção de backups para a OLT especificada."""
    olt = repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    p = policy or PurgePolicy()
    return storage.purge_backups(
        olt_id=olt.id,
        max_backups_per_olt=p.max_backups_per_olt,
        max_age_days=p.max_age_days,
    )


@router.post("/{olt_id}/sync", response_model=SyncOLTResponse)
def sync_olt(
    olt_id: str,
    sync_service=Depends(get_sync_service),
):
    """
    Onboarding e Ingestão Reversa de OLT Brownfield:
    1. Realiza Snapshot v0 preventivo e obrigatório da configuração da OLT.
    2. Descobre todas as ONUs ativas no chassi via hardware.
    3. Cadastra/atualiza ONUs no inventário com cálculo de Circuit ID (TR-101).
    4. Descobre VLANs configuradas.
    """
    try:
        return sync_service.sync_olt(olt_id=olt_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao sincronizar OLT: {str(e)}",
        )


@router.delete("/{olt_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_olt(olt_id: str, repo: OLTRepository = Depends(get_olt_repo)):
    """Remove uma OLT cadastrada no inventário."""
    deleted = repo.delete(olt_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")
    return None


