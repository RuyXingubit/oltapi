import logging
import re
import time
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse, StreamingResponse

from app.api.deps import (
    get_backup_storage,
    get_enrichment_service,
    get_ftp_repo,
    get_olt_repo,
    get_onboarding_service,
    get_security_context,
    get_sync_service,
    get_xray_service,
    require_api_key,
)
from app.core.rate_limit import limiter
from app.services.onu_enrichment_service import ONUEnrichmentService
from app.core.rbac import SecurityContext
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
    OLTCredentialsResponse,
    OLTInspectRequest,
    OLTInspectResponse,
    OLTOnboardRequest,
    OLTOnboardResponse,
    OLTResponse,
    OLTWizardOnboardRequest,
    OLTXRayResponse,
    SNMPConfigureRequest,
    SNMPConfigureResponse,
    SNMPTestRequest,
    SNMPTestResponse,
)
from app.services.connection_service import test_olt_connectivity
from app.services.ftp_service import FTPService
from app.services.snmp_collector import SNMPCollector
from app.storage.backup_storage import BackupStorage
from app.storage.olt_repository import OLTRepository
from app.storage.sql.ftp_repository import SQLFTPRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/olts", tags=["OLTs & Backups"], dependencies=[Depends(require_api_key)])


@router.get("", response_model=List[OLTResponse])
def list_olts(
    repo: OLTRepository = Depends(get_olt_repo),
    ctx: SecurityContext = Depends(get_security_context),
):
    """Lista todas as OLTs cadastradas permitidas para o usuário."""
    ctx.enforce_scope("olts:read")
    olts = repo.list_all()
    if ctx.allowed_olt_ids is not None:
        olts = [o for o in olts if o.id in ctx.allowed_olt_ids]

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


@router.post("/inspect", response_model=OLTInspectResponse, status_code=status.HTTP_200_OK)
def inspect_olt_endpoint(
    req: OLTInspectRequest,
    onboarding_service=Depends(get_onboarding_service),
    ctx: SecurityContext = Depends(get_security_context),
):
    """
    Pré-inspeção não-destrutiva de OLT (Bancada vs In-Band):
    Identifica o fabricante e analisa deterministicamente o running-config:
    - AUX_ONLY: OLT em bancada pura, acessada pela porta auxiliar física sem gerência in-band.
    - AUX_WITH_INBAND: Acessada via AUX, mas já possui gerência in-band configurada.
    - INBAND_ACTIVE: OLT já operando em produção via SVI in-band na rede do provedor.
    """
    ctx.enforce_scope("olts:admin")
    try:
        return onboarding_service.inspect_olt(request=req)
    except ConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Falha de conexão durante inspeção da OLT: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Erro inesperado na inspeção da OLT '{req.host}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro durante inspeção da OLT: {str(e)}",
        )


@router.post("/onboard-wizard", response_model=OLTOnboardResponse, status_code=status.HTTP_201_CREATED)
def onboard_olt_wizard_endpoint(
    req: OLTWizardOnboardRequest,
    response: Response,
    onboarding_service=Depends(get_onboarding_service),
    ctx: SecurityContext = Depends(get_security_context),
):
    """
    Onboarding Assistido via Wizard (V-SOL / Multi-Vendor):
    Executa o comissionamento estruturado com suporte a:
    1. Criação/migração de gerência In-Band (VLAN, SVI IP/Máscara e Gateway).
    2. Criação do pool de VLANs de serviço com propósitos específicos (Router HGU, Bridge SFU, Rede Neutra, LAN-to-LAN).
    3. Habilitação de Hairpin local (p2p enable) caso haja serviços LAN-to-LAN.
    4. Compilação dos perfis GPON com commit nativo e persistência via write.
    5. Ingestão de inventário e cálculo de Circuit ID TR-101 para todas as ONUs detectadas.
    """
    ctx.enforce_scope("olts:admin")
    try:
        tenant_name = ctx.tenant_name or "Provedor"
        result = onboarding_service.execute_wizard_onboarding(request=req, tenant_name=tenant_name)
        response.headers["Location"] = f"/api/v1/olts/{result.olt_id}"
        return result
    except ConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Falha de conexão durante o onboarding wizard: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Erro inesperado no onboarding wizard da OLT '{req.name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro durante o onboarding wizard da OLT: {str(e)}",
        )


@router.post("/onboard", response_model=OLTOnboardResponse, status_code=status.HTTP_201_CREATED)
def onboard_olt(
    req: OLTOnboardRequest,
    response: Response,
    onboarding_service=Depends(get_onboarding_service),
    ctx: SecurityContext = Depends(get_security_context),
):
    """
    Onboarding Contínuo Zero-Touch de OLT (À Prova de Erro Humano):
    1. Probe automático de conectividade (SSH :22 -> Telnet :23).
    2. Fingerprinting e identificação de fabricante/modelo via prompt CLI.
    3. Cadastro atômico e criação obrigatória do Snapshot Baseline v0.
    4. Auto-detecção e provisionamento dinâmico de SNMP (comunidade da empresa/tenant).
    5. Ingestão completa de interfaces físicas, VLANs e ONUs com Circuit ID TR-101.
    6. Retorno consolidado de telemetria e card resumo.
    """
    ctx.enforce_scope("olts:admin")
    try:
        tenant_name = ctx.tenant_name or "Provedor"
        result = onboarding_service.execute_onboarding(request=req, tenant_name=tenant_name)
        response.headers["Location"] = f"/api/v1/olts/{result.olt_id}"
        return result
    except ConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Falha de conexão durante o onboarding: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Erro inesperado no pipeline de onboarding da OLT '{req.name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro durante o onboarding da OLT: {str(e)}",
        )


@router.post("/onboard/stream")
async def onboard_olt_stream(
    req: OLTOnboardRequest,
    onboarding_service=Depends(get_onboarding_service),
    ctx: SecurityContext = Depends(get_security_context),
):
    """
    Onboarding Contínuo Zero-Touch via Server-Sent Events (SSE).
    Emite eventos em tempo real com status granular de cada etapa para animação do stepper e logs.
    """
    ctx.enforce_scope("olts:admin")
    tenant_name = ctx.tenant_name or "Provedor"
    return StreamingResponse(
        onboarding_service.execute_onboarding_stream(request=req, tenant_name=tenant_name),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("", response_model=OLTResponse, status_code=status.HTTP_201_CREATED)
async def create_olt(
    req: OLTCreateRequest,
    response: Response,
    repo: OLTRepository = Depends(get_olt_repo),
    ctx: SecurityContext = Depends(get_security_context),
):
    """
    Cadastra uma nova OLT no inventário (apenas usuários com permissão administrativa).
    """
    ctx.enforce_scope("olts:admin")
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
def get_olt(
    olt_id: str,
    repo: OLTRepository = Depends(get_olt_repo),
    ctx: SecurityContext = Depends(get_security_context),
):
    """Consulta os detalhes cadastrais de uma OLT específica com seus links de ação."""
    ctx.enforce_scope("olts:read")
    ctx.enforce_olt(olt_id)
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
@limiter.limit("15/minute")
async def test_connection(request: Request, olt_id: str, repo: OLTRepository = Depends(get_olt_repo)):
    """Executa teste de conectividade sob demanda e retorna diagnóstico e links de fluxo."""
    olt = repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    return await test_olt_connectivity(olt_id=olt.id, host=olt.host, port=olt.port)


@router.get("/{olt_id}/config", response_model=OLTConfigResponse)
def get_olt_config(
    olt_id: str,
    repo: OLTRepository = Depends(get_olt_repo),
    storage: BackupStorage = Depends(get_backup_storage),
):
    """Coleta e visualiza o running-config completo da OLT."""
    olt = repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    try:
        driver = DriverFactory.get_driver(olt)
        config_text = ""
        try:
            config_text = driver.get_running_config(olt)
        except Exception as driver_err:
            latest_backups = storage.list_by_olt(olt.id)
            if latest_backups:
                content = storage.get_backup_content(olt.id, latest_backups[0].backup_id)
                if content:
                    config_text = content
            if not config_text:
                raise driver_err

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


@router.post("/{olt_id}/telemetry", response_model=OLTXRayResponse)
@limiter.limit("10/minute")
def inspect_olt_telemetry(
    request: Request,
    olt_id: str,
    xray_service=Depends(get_xray_service),
    ctx: SecurityContext = Depends(get_security_context),
):
    """
    Telemetria e Diagnóstico Físico de Chassi de OLT:
    - Uptime em dias/horas;
    - Versão de software/firmware da controladora;
    - Mapeamento físico de TODAS as portas (PON e Uplink) e seus estados operacionais (up, down, loss_of_signal);
    - Detecção de ONUs na fibra e VLANs de serviço;
    - Preview do running-config vivo.
    """
    ctx.enforce_scope("olts:read")
    ctx.enforce_olt(olt_id)
    try:
        return xray_service.inspect_olt(olt_id=olt_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao executar telemetria de chassi na OLT: {str(e)}",
        )


@router.post("/{olt_id}/xray", response_model=OLTXRayResponse, deprecated=True)
def inspect_olt_xray(
    request: Request,
    olt_id: str,
    xray_service=Depends(get_xray_service),
    ctx: SecurityContext = Depends(get_security_context),
):
    """Alias retrocompatível para telemetria e diagnóstico de chassi."""
    return inspect_olt_telemetry(request=request, olt_id=olt_id, xray_service=xray_service, ctx=ctx)


@router.post("/{olt_id}/sync", response_model=SyncOLTResponse)
@limiter.limit("10/minute")
def sync_olt(
    request: Request,
    olt_id: str,
    background_tasks: BackgroundTasks,
    sync_service=Depends(get_sync_service),
    enrichment_service: ONUEnrichmentService = Depends(get_enrichment_service),
):
    """
    Onboarding e Ingestão Reversa de OLT Brownfield:
    1. Realiza Snapshot v0 preventivo e obrigatório da configuração da OLT.
    2. Descobre todas as ONUs ativas no chassi via hardware.
    3. Cadastra/atualiza ONUs no inventário com cálculo de Circuit ID (TR-101).
    4. Descobre VLANs configuradas.
    5. Dispara enriquecimento gradual de VLANs individuais em segundo plano.
    """
    try:
        res = sync_service.sync_olt(olt_id=olt_id)
        background_tasks.add_task(enrichment_service.enrich_olt_onus, olt_id)
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao sincronizar OLT: {str(e)}",
        )


@router.post("/{olt_id}/enrich-vlans")
@limiter.limit("5/minute")
def enrich_olt_vlans(
    request: Request,
    olt_id: str,
    background_tasks: BackgroundTasks,
    force: bool = Query(default=False, description="Forçar nova consulta mesmo se a ONU já tiver VLAN"),
    enrichment_service: ONUEnrichmentService = Depends(get_enrichment_service),
    ctx: SecurityContext = Depends(get_security_context),
):
    """
    Dispara varredura e enriquecimento assíncrono em segundo plano para
    descobrir a VLAN de serviço real de cada ONU configurada no chassi.
    """
    background_tasks.add_task(enrichment_service.enrich_olt_onus, olt_id, force)
    return {
        "status": "scheduled",
        "message": "Enriquecimento gradual de VLANs iniciado em segundo plano.",
        "olt_id": olt_id,
    }


@router.post(
    "/{olt_id}/reveal-credentials",
    response_model=OLTCredentialsResponse,
    summary="Revelar credenciais de acesso da OLT (apenas Administradores)",
    description="Permite que usuários com privilégio SUPER_ADMIN ou TENANT_ADMIN recuperem a senha administrativa da OLT. Toda consulta gera registro na trilha de auditoria.",
)
@limiter.limit("5/minute")
def reveal_olt_credentials(
    request: Request,
    olt_id: str,
    repo: OLTRepository = Depends(get_olt_repo),
    ctx: SecurityContext = Depends(get_security_context),
):
    """Revela credenciais da OLT para administradores autorizados com log de auditoria."""
    ctx.enforce_scope("olts:admin")
    if not ctx.is_super_admin and ctx.role != "TENANT_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: apenas Administradores podem revelar credenciais de hardware.",
        )

    olt = repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"OLT com ID '{olt_id}' não encontrada.",
        )

    if ctx.allowed_olt_ids is not None and olt.id not in ctx.allowed_olt_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado para esta OLT.",
        )

    client_ip = request.client.host if request.client else "unknown"
    logger.warning(
        f"[SECURITY AUDIT] Usuário '{ctx.user_email or ctx.caller_type}' (Role: {ctx.role}) "
        f"revelou as credenciais da OLT '{olt.name}' (ID: {olt.id}) a partir do IP {client_ip}."
    )

    return OLTCredentialsResponse(
        olt_id=olt.id,
        olt_name=olt.name,
        host=olt.host,
        port=olt.port,
        protocol=olt.protocol.value if hasattr(olt.protocol, "value") else str(olt.protocol),
        username=olt.username,
        password=olt.password,
    )


@router.delete("/{olt_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_olt(
    olt_id: str,
    request: Request,
    repo: OLTRepository = Depends(get_olt_repo),
    ctx: SecurityContext = Depends(get_security_context),
):
    """Remove uma OLT cadastrada no inventário (Exclusivo para Administradores com auditoria)."""
    ctx.enforce_scope("olts:admin")
    if not ctx.is_super_admin and ctx.role != "TENANT_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: apenas Administradores (SUPER_ADMIN ou TENANT_ADMIN) podem excluir uma OLT.",
        )

    olt = repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    if ctx.allowed_olt_ids is not None and olt.id not in ctx.allowed_olt_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado para esta OLT.",
        )

    deleted = repo.delete(olt_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    client_ip = request.client.host if request.client else "unknown"
    logger.warning(
        f"[SECURITY AUDIT] Usuário '{ctx.user_email or ctx.caller_type}' (Role: {ctx.role}) "
        f"EXCLUIU permanentemente a OLT '{olt.name}' (ID: {olt.id}) a partir do IP {client_ip}."
    )
    return None


@router.post("/{olt_id}/snmp/test", response_model=SNMPTestResponse)
def test_olt_snmp(
    olt_id: str,
    req: Optional[SNMPTestRequest] = None,
    repo: OLTRepository = Depends(get_olt_repo),
    ctx: SecurityContext = Depends(get_security_context),
):
    """
    Testa a conectividade SNMP v2c via UDP 161 na OLT física:
    - Valida se o agente SNMP está respondendo e obtém sysUpTime;
    - Permite testar uma comunidade específica (ex: descoberta por um técnico);
    - Opcionalmente adota e salva a comunidade no cadastro se o teste for bem-sucedido.
    """
    ctx.enforce_scope("olts:read")
    ctx.enforce_olt(olt_id)
    olt = repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    test_req = req or SNMPTestRequest()
    community = test_req.community or olt.snmp_community or "public"
    port = test_req.port or olt.snmp_port or 161

    start_t = time.perf_counter()
    uptime = SNMPCollector.get_sys_uptime(host=olt.host, community=community, port=port, timeout=1.2)
    latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
    reachable = uptime is not None

    saved_to_db = False
    if reachable and test_req.save_if_successful:
        ctx.enforce_scope("olts:write")
        olt.snmp_community = community
        olt.snmp_port = port
        repo.update(olt)
        saved_to_db = True

    msg = (
        f"Agente SNMP respondendo via UDP {port} (sysUpTime: {uptime}s, latência: {latency_ms}ms)."
        if reachable
        else f"Agente SNMP não respondeu em {olt.host}:{port} com a comunidade informada."
    )
    if saved_to_db:
        msg += " Comunidade adotada e salva no cadastro da OLT com sucesso."

    links = {
        "self": Link(href=f"/api/v1/olts/{olt.id}/snmp/test", rel="self", method="POST"),
        "olt": Link(href=f"/api/v1/olts/{olt.id}", rel="olt", method="GET"),
        "telemetry": Link(href=f"/api/v1/olts/{olt.id}/telemetry", rel="telemetry", method="POST"),
    }

    return SNMPTestResponse(
        olt_id=olt.id,
        host=olt.host,
        port=port,
        community=community,
        reachable=reachable,
        latency_ms=latency_ms if reachable else None,
        uptime_seconds=uptime,
        saved_to_db=saved_to_db,
        message=msg,
        links=links,
    )


@router.post("/{olt_id}/snmp/configure", response_model=SNMPConfigureResponse)
def configure_olt_snmp(
    olt_id: str,
    req: SNMPConfigureRequest,
    repo: OLTRepository = Depends(get_olt_repo),
    ctx: SecurityContext = Depends(get_security_context),
):
    """
    Provisiona comunidade SNMP Read-Only (RO) diretamente na OLT física via CLI/driver
    e persiste na memória flash permanente (save/write):
    - Requer privilégio de SUPER_ADMIN;
    - Valida contra injeção CLI;
    - Aplica sintaxe do fabricante em modo estritamente RO;
    - Executa teste UDP 161 imediato e atualiza o cadastro da OLT.
    """
    ctx.enforce_scope("olts:write")
    if not ctx.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas administradores (SUPER_ADMIN) têm autorização para provisionar comandos CLI de SNMP na OLT.",
        )
    ctx.enforce_olt(olt_id)

    olt = repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    # Sanitização estrita contra injeção CLI
    clean_comm = req.community.strip()
    if not re.match(r"^[A-Za-z0-9_\.\-]{3,64}$", clean_comm):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Comunidade SNMP inválida. Use de 3 a 64 caracteres alfanuméricos, ponto, traço ou sublinhado, sem espaços.",
        )

    port = req.port or olt.snmp_port or 161
    driver = DriverFactory.get_driver(olt)

    configured = driver.configure_snmp(olt, clean_comm, port)
    if not configured:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha ao executar comandos de provisionamento SNMP no equipamento {olt.name}.",
        )

    # Teste de conectividade pós-configuração
    uptime = SNMPCollector.get_sys_uptime(host=olt.host, community=clean_comm, port=port, timeout=1.5)
    tested_ok = uptime is not None

    # Atualiza dados no repositório
    olt.snmp_community = clean_comm
    olt.snmp_port = port
    repo.update(olt)

    msg = (
        f"Comunidade SNMP '{clean_comm}' configurada como RO na OLT {olt.name} e gravada na flash com sucesso. "
        + (f"Agente SNMP validado (sysUpTime: {uptime}s)." if tested_ok else "Aguardando agente subir ou liberar porta UDP.")
    )

    links = {
        "self": Link(href=f"/api/v1/olts/{olt.id}/snmp/configure", rel="self", method="POST"),
        "test": Link(href=f"/api/v1/olts/{olt.id}/snmp/test", rel="test", method="POST"),
        "telemetry": Link(href=f"/api/v1/olts/{olt.id}/telemetry", rel="telemetry", method="POST"),
    }

    return SNMPConfigureResponse(
        olt_id=olt.id,
        host=olt.host,
        community=clean_comm,
        configured_in_cli=configured,
        saved_to_flash=True,
        tested_ok=tested_ok,
        uptime_seconds=uptime,
        message=msg,
        links=links,
    )


