from datetime import datetime, timezone
import ftplib
import time
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_ftp_repo, get_olt_repo, require_api_key
from app.core.config import settings
from app.db.models import BackupMetadataModel, OLTModel
from app.models.ftp import (
    FTPBoundOLTItem,
    FTPOverviewResponse,
    FTPServerCreate,
    FTPServerResponse,
    FTPServerUpdate,
    OLTFTPBindingRequest,
    OLTFTPDestinationResponse,
)
from app.models.hateoas import Link
from app.storage.sql.ftp_repository import SQLFTPRepository
from app.storage.sql.olt_repository import SQLOLTRepository

router = APIRouter(tags=["Servidores FTP & Destinos de Backup"], dependencies=[Depends(require_api_key)])


def _attach_links(server: FTPServerResponse) -> FTPServerResponse:
    server.links = {
        "self": Link(
            href=f"/api/v1/ftp-servers/{server.id}",
            method="GET",
            description="Consultar detalhes do servidor FTP",
        ),
        "test": Link(
            href=f"/api/v1/ftp-servers/{server.id}/test",
            method="POST",
            description="Testar conectividade e credenciais com o servidor FTP",
        ),
        "update": Link(
            href=f"/api/v1/ftp-servers/{server.id}",
            method="PUT",
            description="Atualizar configurações do servidor FTP",
        ),
        "delete": Link(
            href=f"/api/v1/ftp-servers/{server.id}",
            method="DELETE",
            description="Remover servidor FTP",
        ),
    }
    return server


@router.get("/ftp-servers/overview", response_model=FTPOverviewResponse)
def get_ftp_overview(
    repo: SQLFTPRepository = Depends(get_ftp_repo),
    db: Session = Depends(get_db),
):
    """Retorna diagnóstico consolidado do servidor FTP ativo (.env ou DB), saúde e backups por equipamento."""
    all_servers = repo.list_all(active_only=True)
    server = all_servers[0] if all_servers else None

    source = "database" if server else ("env" if settings.FTP_DEFAULT_HOST else "none")
    configured = server is not None or bool(settings.FTP_DEFAULT_HOST)

    name = server.name if server else (settings.FTP_DEFAULT_NAME or "FTP Central (.env)")
    host = server.host if server else settings.FTP_DEFAULT_HOST
    port = server.port if server else (settings.FTP_DEFAULT_PORT or 21)
    username = server.username if server else settings.FTP_DEFAULT_USER
    password = (repo.get_raw_by_id(server.id).password if server else settings.FTP_DEFAULT_PASS)
    base_path = server.base_path if server else (settings.FTP_DEFAULT_BASE_PATH or "/")
    is_global = server.is_global_default if server else settings.FTP_DEFAULT_IS_GLOBAL

    is_online = False
    latency_ms = None
    status_message = "Nenhum servidor FTP configurado" if not configured else "Falha na conexão com o servidor FTP"
    banner = None

    if configured and host and username:
        start_time = time.time()
        try:
            ftp = ftplib.FTP(timeout=2)
            ftp.connect(host, port)
            banner = ftp.getwelcome()
            if password:
                ftp.login(username, password)
            else:
                ftp.login(username)
            ftp.quit()
            is_online = True
            latency_ms = round((time.time() - start_time) * 1000, 2)
            status_message = "Servidor FTP operando normalmente com resposta rápida"
        except Exception as e:
            latency_ms = round((time.time() - start_time) * 1000, 2)
            status_message = f"Erro na conexão FTP ({host}:{port}): {str(e)}"

    total_backups = db.query(BackupMetadataModel).count()
    total_bytes = db.query(func.coalesce(func.sum(BackupMetadataModel.size_bytes), 0)).scalar() or 0

    olts = db.query(OLTModel).order_by(OLTModel.name.asc()).all()
    bound_olts = []
    for olt in olts:
        b_count = db.query(BackupMetadataModel).filter(BackupMetadataModel.olt_id == olt.id).count()
        latest_b = (
            db.query(BackupMetadataModel)
            .filter(BackupMetadataModel.olt_id == olt.id)
            .order_by(BackupMetadataModel.created_at.desc())
            .first()
        )
        bound_olts.append(
            FTPBoundOLTItem(
                olt_id=olt.id,
                olt_name=olt.name,
                vendor=olt.vendor,
                model=olt.model,
                host=olt.host,
                backup_count=b_count,
                last_backup_at=latest_b.created_at if latest_b else None,
            )
        )

    return FTPOverviewResponse(
        configured=configured,
        source=source,
        server_id=server.id if server else None,
        name=name,
        host=host,
        port=port,
        username=username,
        base_path=base_path,
        is_global_default=is_global,
        is_active=True,
        is_online=is_online,
        latency_ms=latency_ms,
        status_message=status_message,
        banner=banner,
        last_checked_at=datetime.now(timezone.utc),
        total_backups_count=total_backups,
        total_backups_bytes=total_bytes,
        bound_olts=bound_olts,
        links={
            "self": Link(href="/api/v1/ftp-servers/overview", method="GET", description="Visão geral do FTP"),
        },
    )


@router.get("/ftp-servers", response_model=List[FTPServerResponse])
def list_ftp_servers(
    active_only: bool = Query(default=False, description="Listar apenas servidores ativos"),
    repo: SQLFTPRepository = Depends(get_ftp_repo),
):
    """Lista todos os servidores FTP cadastrados no OLTAPI."""
    servers = repo.list_all(active_only=active_only)
    return [_attach_links(s) for s in servers]


@router.post("/ftp-servers", response_model=FTPServerResponse, status_code=status.HTTP_201_CREATED)
def create_ftp_server(
    req: FTPServerCreate,
    response: Response,
    repo: SQLFTPRepository = Depends(get_ftp_repo),
):
    """Cadastra um novo servidor FTP para recebimento de backups de OLTs."""
    existing = repo.get_by_name(req.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Servidor FTP com o nome '{req.name}' já cadastrado.",
        )
    created = repo.create(req)
    _attach_links(created)
    response.headers["Location"] = f"/api/v1/ftp-servers/{created.id}"
    return created


@router.get("/ftp-servers/{ftp_id}", response_model=FTPServerResponse)
def get_ftp_server(
    ftp_id: str,
    repo: SQLFTPRepository = Depends(get_ftp_repo),
):
    """Consulta detalhes de um servidor FTP cadastrado."""
    server = repo.get_by_id(ftp_id)
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Servidor FTP '{ftp_id}' não encontrado.",
        )
    return _attach_links(server)


@router.put("/ftp-servers/{ftp_id}", response_model=FTPServerResponse)
def update_ftp_server(
    ftp_id: str,
    req: FTPServerUpdate,
    repo: SQLFTPRepository = Depends(get_ftp_repo),
):
    """Atualiza configurações de um servidor FTP."""
    updated = repo.update(ftp_id, req)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Servidor FTP '{ftp_id}' não encontrado.",
        )
    return _attach_links(updated)


@router.delete("/ftp-servers/{ftp_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ftp_server(
    ftp_id: str,
    repo: SQLFTPRepository = Depends(get_ftp_repo),
):
    """Remove um servidor FTP do sistema."""
    if not repo.delete(ftp_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Servidor FTP '{ftp_id}' não encontrado.",
        )
    return None


@router.post("/ftp-servers/{ftp_id}/test")
def test_ftp_server_connection(
    ftp_id: str,
    repo: SQLFTPRepository = Depends(get_ftp_repo),
):
    """Testa a conectividade e autenticação com o servidor FTP."""
    raw = repo.get_raw_by_id(ftp_id)
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Servidor FTP '{ftp_id}' não encontrado.",
        )

    start_time = time.time()
    try:
        ftp = ftplib.FTP(timeout=8)
        ftp.connect(raw.host, raw.port)
        banner = ftp.getwelcome()
        ftp.login(raw.username, raw.password)
        pwd = ftp.pwd()
        ftp.quit()
        latency_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "success": True,
            "message": "Conexão e autenticação FTP bem-sucedidas.",
            "banner": banner,
            "working_directory": pwd,
            "latency_ms": latency_ms,
        }
    except Exception as e:
        latency_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "success": False,
            "message": f"Falha na conexão FTP: {str(e)}",
            "latency_ms": latency_ms,
        }


@router.post("/olts/{olt_id}/ftp-servers", response_model=OLTFTPDestinationResponse)
def bind_olt_to_ftp_servers(
    olt_id: str,
    req: OLTFTPBindingRequest,
    olt_repo: SQLOLTRepository = Depends(get_olt_repo),
    ftp_repo: SQLFTPRepository = Depends(get_ftp_repo),
):
    """Vincula servidores FTP específicos a uma OLT."""
    olt = olt_repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"OLT '{olt_id}' não encontrada.",
        )

    ftp_repo.bind_olt(olt_id, req.ftp_server_ids)
    destinations = ftp_repo.get_destinations_for_olt(olt_id)
    for s in destinations.effective_destinations:
        _attach_links(s)
    return destinations


@router.get("/olts/{olt_id}/ftp-servers", response_model=OLTFTPDestinationResponse)
def get_olt_ftp_destinations(
    olt_id: str,
    olt_repo: SQLOLTRepository = Depends(get_olt_repo),
    ftp_repo: SQLFTPRepository = Depends(get_ftp_repo),
):
    """Consulta os servidores FTP de destino para uma OLT (específicos + globais)."""
    olt = olt_repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"OLT '{olt_id}' não encontrada.",
        )

    destinations = ftp_repo.get_destinations_for_olt(olt_id)
    for s in destinations.effective_destinations:
        _attach_links(s)
    return destinations
