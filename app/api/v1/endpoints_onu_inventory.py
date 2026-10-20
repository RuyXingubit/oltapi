from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import (
    get_olt_repo,
    get_onu_repo,
    get_preset_repo,
    get_security_context,
    get_topology_repo,
    get_webhook_dispatcher,
    require_api_key,
)
from app.core.circuit_id import generate_circuit_id
from app.core.rbac import SecurityContext
from app.core.security import sanitize_port, sanitize_safe_string, sanitize_serial, sanitize_vlan
from app.models.hateoas import Link
from app.models.onu_inventory import (
    ONUInventoryItem,
    ONUMigrationEvent,
    ReconcileFieldEventRequest,
    ReconcileFieldEventResponse,
    RegisterONUInventoryRequest,
    UpdateONUInventoryRequest,
)
from app.models.optical_telemetry import (
    DegradedONUReportItem,
    OpticalTelemetryHistoryResponse,
)
from app.models.presets import PreProvisionONURequest
from app.models.topology import ONUTopologyAssignRequest
from app.services.onu_reconciliation_service import ONUReconciliationService
from app.services.webhook_dispatcher import WebhookDispatcher
from app.storage.olt_repository import OLTRepository
from app.storage.onu_repository import ONUInventoryRepository
from app.storage.sql.preset_repository import SQLPresetRepository
from app.storage.sql.topology_repository import SQLTopologyRepository

router = APIRouter(prefix="/onus", tags=["Inventário Global & Auto-Recuperação de ONUs"], dependencies=[Depends(require_api_key)])



@router.get("", response_model=List[ONUInventoryItem])
def list_onus(
    olt_id: Optional[str] = Query(default=None, description="Filtrar por OLT"),
    port: Optional[str] = Query(default=None, description="Filtrar por porta PON"),
    contract_status: Optional[str] = Query(default=None, description="Filtrar por status do contrato: ACTIVE, SUSPENDED, CANCELLED, IN_STOCK"),
    contract_id: Optional[str] = Query(default=None, description="Filtrar por código de contrato"),
    repo: ONUInventoryRepository = Depends(get_onu_repo),
    ctx: SecurityContext = Depends(get_security_context),
):
    """Lista todas as ONUs do inventário global com dados de contrato, Circuit ID (TR-101) e coordenadas."""
    ctx.enforce_scope("onus:read")
    if olt_id:
        ctx.enforce_olt(olt_id)

    items = repo.list_all(olt_id=olt_id, port=port, contract_status=contract_status, contract_id=contract_id)

    # Filtragem por OLTs permitidas para o usuário (ex: técnico de POP específico)
    if ctx.allowed_olt_ids is not None:
        items = [i for i in items if i.current_olt_id in ctx.allowed_olt_ids]

    # Isolamento de Rede Neutra: inquilino só visualiza ONUs de suas VLANs autorizadas
    if ctx.tenant_type == "NEUTRAL_OPERATOR" and ctx.allowed_vlans is not None:
        filtered = []
        for i in items:
            if not i.current_olt_id or not i.vlan:
                continue
            olt_vlans = ctx.allowed_vlans.get(i.current_olt_id, set())
            if i.vlan in olt_vlans:
                filtered.append(i)
        items = filtered
    for item in items:
        item.links = {
            "details": Link(
                href=f"/api/v1/onus/{item.serial}",
                method="GET",
                description="Ver detalhes 360º desta ONU",
            ),
            "history": Link(
                href=f"/api/v1/onus/{item.serial}/history",
                method="GET",
                description="Histórico de movimentações físicas e auto-recuperações",
            ),
        }
        if item.current_olt_id:
            item.links["olt"] = Link(
                href=f"/api/v1/olts/{item.current_olt_id}",
                method="GET",
                description="Dados da OLT onde está fixada",
            )
        if item.current_olt_id and item.current_port:
            item.links["port_onus"] = Link(
                href=f"/api/v1/olts/{item.current_olt_id}/ports/{item.current_port}/onus",
                method="GET",
                description="Listar ONUs da mesma porta",
            )
    return items


@router.get("/history", response_model=List[ONUMigrationEvent])
def list_global_history(
    serial: Optional[str] = Query(default=None, description="Filtrar por serial"),
    from_olt_id: Optional[str] = Query(default=None, description="Filtrar por OLT de origem"),
    to_olt_id: Optional[str] = Query(default=None, description="Filtrar por OLT de destino"),
    limit: int = Query(default=100, ge=1, le=500, description="Limite de eventos retornados"),
    repo: ONUInventoryRepository = Depends(get_onu_repo),
    ctx: SecurityContext = Depends(get_security_context),
):
    """Linha do Tempo Global de Movimentações (NOC Timeline): relatório de manobras, inversões e auto-recuperações."""
    ctx.enforce_scope("onus:read")
    events = repo.list_history(serial=serial, from_olt_id=from_olt_id, to_olt_id=to_olt_id, limit=limit)
    for ev in events:
        ev.links = {
            "onu": Link(
                href=f"/api/v1/onus/{ev.serial}",
                method="GET",
                description="Consultar cadastro da ONU",
            ),
            "onu_history": Link(
                href=f"/api/v1/onus/{ev.serial}/history",
                method="GET",
                description="Histórico individual desta ONU",
            ),
        }
    return events


@router.post("/reconcile-field-event", response_model=ReconcileFieldEventResponse)
def reconcile_field_event(
    req: ReconcileFieldEventRequest,
    onu_repo: ONUInventoryRepository = Depends(get_onu_repo),
    olt_repo: OLTRepository = Depends(get_olt_repo),
    webhook_dispatcher: WebhookDispatcher = Depends(get_webhook_dispatcher),
    ctx: SecurityContext = Depends(get_security_context),
):
    """
    Motor de Auto-Recuperação Reativa de Campo.
    Detecta inversões de fusão, trocas de porta ou mudanças físicas de bastidor:
    - Se o contrato está ATIVO: provisiona na nova PON, desprovisiona na antiga, recalcula o Circuit ID TR-101 e audita a movimentação.
    - Se o contrato está INATIVO/ESTOQUE: bloqueia a herança indevida de dados do titular anterior.
    """
    ctx.enforce_scope("onus:provision")
    ctx.enforce_olt(req.detected_olt_id)
    try:
        clean_serial = sanitize_serial(req.serial)
        clean_port = sanitize_port(req.detected_port)
        clean_req = ReconcileFieldEventRequest(
            serial=clean_serial,
            detected_olt_id=req.detected_olt_id,
            detected_port=clean_port,
            detected_onu_id=req.detected_onu_id,
            latitude=req.latitude,
            longitude=req.longitude,
            reason=req.reason,
        )

        service = ONUReconciliationService(
            olt_repo=olt_repo,
            onu_repo=onu_repo,
            webhook_dispatcher=webhook_dispatcher,
        )
        return service.reconcile_field_event(clean_req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro na reconciliação de campo: {str(e)}")


@router.post("", response_model=ONUInventoryItem, status_code=status.HTTP_201_CREATED)
def register_onu(
    req: RegisterONUInventoryRequest,
    response: Response,
    onu_repo: ONUInventoryRepository = Depends(get_onu_repo),
    olt_repo: OLTRepository = Depends(get_olt_repo),
    ctx: SecurityContext = Depends(get_security_context),
):
    """Cadastra ou vincula uma ONU ao inventário associando a contrato, OLT, VLAN e coordenadas geográficas."""
    ctx.enforce_scope("onus:provision")
    clean_serial = sanitize_serial(req.serial)

    target_olt_id = req.olt_id or req.current_olt_id
    if target_olt_id:
        ctx.enforce_olt(target_olt_id)
    target_port = req.port or req.current_port
    target_onu_id = req.onu_id if req.onu_id is not None else req.current_onu_id
    target_desc = req.description or req.notes

    circuit_id = None
    clean_port = None
    clean_vlan = sanitize_vlan(req.vlan) if req.vlan is not None else None
    if target_olt_id and clean_vlan:
        ctx.enforce_vlan(target_olt_id, clean_vlan)

    if target_olt_id and target_port and target_onu_id is not None and clean_vlan:
        clean_port = sanitize_port(target_port)
        olt = olt_repo.get_by_id(target_olt_id)
        if not olt:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{target_olt_id}' não encontrada.")
        circuit_id = generate_circuit_id(olt.name, clean_port, target_onu_id, clean_vlan)

    existing = onu_repo.get_by_serial(clean_serial)
    if existing:
        existing.contract_id = req.contract_id
        existing.subscriber_name = req.subscriber_name
        existing.contract_status = req.contract_status or "ACTIVE"
        existing.vlan = clean_vlan
        existing.profile = req.profile or "DEFAULT"
        existing.description = target_desc
        existing.latitude = req.latitude
        existing.longitude = req.longitude
        existing.current_olt_id = target_olt_id
        existing.current_port = clean_port
        existing.current_onu_id = target_onu_id
        existing.circuit_id = circuit_id
        item = onu_repo.upsert(existing)
    else:
        item = ONUInventoryItem(
            serial=clean_serial,
            contract_id=req.contract_id,
            subscriber_name=req.subscriber_name,
            contract_status=req.contract_status or "ACTIVE",
            vlan=clean_vlan,
            profile=req.profile or "DEFAULT",
            description=target_desc,
            latitude=req.latitude,
            longitude=req.longitude,
            current_olt_id=target_olt_id,
            current_port=clean_port,
            current_onu_id=target_onu_id,
            circuit_id=circuit_id,
        )
        item = onu_repo.upsert(item)

    response.headers["Location"] = f"/api/v1/onus/{item.serial}"
    item.links = {
        "self": Link(
            href=f"/api/v1/onus/{item.serial}",
            method="GET",
            description="Consultar cadastro da ONU",
        ),
        "history": Link(
            href=f"/api/v1/onus/{item.serial}/history",
            method="GET",
            description="Histórico de movimentações",
        ),
    }
    return item


@router.get("/degraded", response_model=List[DegradedONUReportItem])
def list_degraded_onus(
    olt_id: Optional[str] = Query(default=None, description="Filtrar por OLT"),
    threshold_dbm: float = Query(default=-25.5, description="Limiar de potência óptica Rx (dBm) para atenção"),
    drift_threshold_db: float = Query(default=-2.5, description="Limiar de deriva óptica negativa (dB) em relação à linha de base"),
    repo: ONUInventoryRepository = Depends(get_onu_repo),
    ctx: SecurityContext = Depends(get_security_context),
):
    """Radar de Degradação Óptica: lista ONUs com potência Rx crítica, deriva acentuada (drift) ou alarme LoS/LoFi."""
    ctx.enforce_scope("onus:read")
    if olt_id:
        ctx.enforce_olt(olt_id)

    items = repo.list_degraded_onus(
        olt_id=olt_id,
        threshold_dbm=threshold_dbm,
        drift_threshold_db=drift_threshold_db,
    )
    if ctx.allowed_olt_ids is not None:
        items = [i for i in items if i.olt_id in ctx.allowed_olt_ids]

    for item in items:
        item.links = {
            "onu": Link(href=f"/api/v1/onus/{item.serial}", method="GET", description="Ver inventário da ONU"),
            "optical_history": Link(
                href=f"/api/v1/onus/{item.serial}/optical-history",
                method="GET",
                description="Ver série temporal de potência óptica",
            ),
        }
    return items


@router.post("/pre-provision", response_model=ONUInventoryItem, status_code=status.HTTP_201_CREATED)
def pre_provision_onu(
    req: PreProvisionONURequest,
    response: Response,
    onu_repo: ONUInventoryRepository = Depends(get_onu_repo),
    preset_repo: SQLPresetRepository = Depends(get_preset_repo),
    topology_repo: SQLTopologyRepository = Depends(get_topology_repo),
    ctx: SecurityContext = Depends(get_security_context),
):
    """
    Pré-Provisionamento por Serial (Zero-Touch Field Activation - Fase 3).
    Agenda a ativação de uma ONU enviada a campo antes de ser conectada na fibra.
    Assim que o serial acender no autofind, o scanner aplica automaticamente VLAN, perfil e TR-101.
    """
    ctx.enforce_scope("onus:provision")
    clean_serial = sanitize_serial(req.serial)
    if req.olt_id:
        ctx.enforce_olt(req.olt_id)

    target_vlan = req.vlan
    target_profile = req.profile or "DEFAULT"
    if req.preset_id:
        preset = preset_repo.get_preset(req.preset_id)
        if not preset:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Preset '{req.preset_id}' não encontrado.")
        if target_vlan is None:
            target_vlan = preset.vlan
        if not req.profile and preset.line_profile:
            target_profile = preset.line_profile

    if target_vlan is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informe uma VLAN ou selecione um Preset de provisionamento válido.",
        )
    clean_vlan = sanitize_vlan(target_vlan)
    if req.olt_id:
        ctx.enforce_vlan(req.olt_id, clean_vlan)

    topo_data = {"zone_id": req.zone_id, "odb_id": req.odb_id, "odb_splitter_port": req.odb_splitter_port}
    if req.odb_id:
        topo_data = topology_repo.validate_and_assign_onu_topology(
            clean_serial,
            ONUTopologyAssignRequest(
                zone_id=req.zone_id,
                odb_id=req.odb_id,
                odb_splitter_port=req.odb_splitter_port,
            ),
        )

    existing = onu_repo.get_by_serial(clean_serial)
    item = existing or ONUInventoryItem(serial=clean_serial)
    item.subscriber_name = req.subscriber_name.strip()
    item.contract_id = req.contract_id.strip() if req.contract_id else None
    item.contract_status = "PRE_PROVISIONED"
    item.vlan = clean_vlan
    item.profile = sanitize_safe_string(target_profile, "profile")
    item.current_olt_id = req.olt_id
    item.current_port = sanitize_port(req.port) if req.port else None
    item.zone_id = topo_data.get("zone_id")
    item.odb_id = topo_data.get("odb_id")
    item.odb_splitter_port = topo_data.get("odb_splitter_port")
    item.description = req.description.strip() if req.description else "Aguardando conexão física em campo (Pré-Provisionada)"

    saved = onu_repo.upsert(item)
    response.headers["Location"] = f"/api/v1/onus/{saved.serial}"
    saved.links = {
        "self": Link(href=f"/api/v1/onus/{saved.serial}", method="GET", description="Consultar status da ONU"),
    }
    return saved


@router.get("/{serial}", response_model=ONUInventoryItem)

def get_onu_by_serial(
    serial: str,
    repo: ONUInventoryRepository = Depends(get_onu_repo),
    ctx: SecurityContext = Depends(get_security_context),
):
    """Consulta os dados de inventário, coordenadas e Circuit ID atual de uma ONU pelo serial imutável."""
    ctx.enforce_scope("onus:read")
    clean_serial = sanitize_serial(serial)
    item = repo.get_by_serial(clean_serial)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"ONU '{clean_serial}' não encontrada no inventário.")

    if item.current_olt_id and ctx.allowed_olt_ids is not None and item.current_olt_id not in ctx.allowed_olt_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"ONU '{clean_serial}' não encontrada no inventário.")

    if ctx.tenant_type == "NEUTRAL_OPERATOR" and ctx.allowed_vlans is not None:
        olt_vlans = ctx.allowed_vlans.get(item.current_olt_id or "", set())
        if not item.vlan or item.vlan not in olt_vlans:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"ONU '{clean_serial}' não encontrada no inventário.")

    links = {
        "self": Link(
            href=f"/api/v1/onus/{item.serial}",
            method="GET",
            description="Detalhes do equipamento no inventário",
        ),
        "history": Link(
            href=f"/api/v1/onus/{item.serial}/history",
            method="GET",
            description="Histórico de manobras e correções desta ONU",
        ),
    }
    if item.current_olt_id:
        links["optical_info"] = Link(
            href=f"/api/v1/olts/{item.current_olt_id}/onus/{item.serial}",
            method="GET",
            description="Leitura de potência óptica Rx/Tx em tempo real na OLT",
        )
        if item.current_port and item.current_onu_id is not None:
            links["reboot"] = Link(
                href=f"/api/v1/olts/{item.current_olt_id}/onus/{item.serial}/reboot?port={item.current_port}&onu_id={item.current_onu_id}",
                method="POST",
                description="Reiniciar remotamente via OMCI",
            )
            links["suspend"] = Link(
                href=f"/api/v1/olts/{item.current_olt_id}/onus/{item.serial}/suspend?port={item.current_port}&onu_id={item.current_onu_id}",
                method="POST",
                description="Bloquear administrativamente por inadimplência",
            )
    item.links = links
    return item


@router.get("/{serial}/history", response_model=List[ONUMigrationEvent])
def get_onu_history(
    serial: str,
    limit: int = Query(default=50, ge=1, le=200),
    repo: ONUInventoryRepository = Depends(get_onu_repo),
    ctx: SecurityContext = Depends(get_security_context),
):
    """Histórico de vida e movimentações de um equipamento específico através de portas e OLTs."""
    ctx.enforce_scope("onus:read")
    clean_serial = sanitize_serial(serial)
    events = repo.list_history(serial=clean_serial, limit=limit)
    for ev in events:
        ev.links = {
            "onu": Link(
                href=f"/api/v1/onus/{ev.serial}",
                method="GET",
                description="Consultar cadastro da ONU",
            )
        }
    return events


@router.patch("/{serial}", response_model=ONUInventoryItem)
def update_onu(
    serial: str,
    req: UpdateONUInventoryRequest,
    repo: ONUInventoryRepository = Depends(get_onu_repo),
    ctx: SecurityContext = Depends(get_security_context),
):
    """Atualiza dados cadastrais, circuito e VLAN de uma ONU no inventário."""
    if "*" not in ctx.scopes and "onus:write" not in ctx.scopes and "onus:provision" not in ctx.scopes:
        ctx.enforce_scope("onus:write")
    clean_serial = sanitize_serial(serial)
    item = repo.get_by_serial(clean_serial)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"ONU '{clean_serial}' não encontrada no inventário.")

    if item.current_olt_id and ctx.allowed_olt_ids is not None and item.current_olt_id not in ctx.allowed_olt_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado para a OLT desta ONU.")

    if req.subscriber_name is not None:
        item.subscriber_name = req.subscriber_name.strip() if req.subscriber_name else None
    if req.description is not None:
        item.description = req.description.strip() if req.description else None
    if req.circuit_id is not None:
        item.circuit_id = req.circuit_id.strip() if req.circuit_id else None
    if req.profile is not None:
        item.profile = sanitize_safe_string(req.profile, "profile") if req.profile else "DEFAULT"
    if req.vlan is not None:
        item.vlan = sanitize_vlan(req.vlan)
    if req.zone_id is not None:
        item.zone_id = req.zone_id
    if req.odb_id is not None:
        item.odb_id = req.odb_id
    if req.odb_splitter_port is not None:
        item.odb_splitter_port = req.odb_splitter_port

    updated_item = repo.upsert(item)
    updated_item.links = {
        "self": Link(
            href=f"/api/v1/onus/{updated_item.serial}",
            method="GET",
            description="Detalhes do equipamento no inventário",
        ),
        "history": Link(
            href=f"/api/v1/onus/{updated_item.serial}/history",
            method="GET",
            description="Histórico de manobras e correções desta ONU",
        ),
    }
    return updated_item


@router.get("/{serial}/optical-history", response_model=OpticalTelemetryHistoryResponse)
def get_onu_optical_history(
    serial: str,
    limit: int = Query(default=100, ge=1, le=500, description="Quantidade máxima de amostras da série temporal"),
    repo: ONUInventoryRepository = Depends(get_onu_repo),
    ctx: SecurityContext = Depends(get_security_context),
):
    """Consulta a série temporal de potência óptica (Rx/Tx/OLT Rx em dBm) e cálculo de deriva (drift_db) da ONU."""
    ctx.enforce_scope("onus:read")
    clean_serial = sanitize_serial(serial)
    hist = repo.get_optical_history(clean_serial, limit=limit)
    hist.links = {
        "onu": Link(href=f"/api/v1/onus/{clean_serial}", method="GET", description="Ver cadastro da ONU"),
    }
    return hist


@router.patch("/{serial}/topology", response_model=ONUInventoryItem)
def assign_onu_topology(
    serial: str,
    req: ONUTopologyAssignRequest,
    onu_repo: ONUInventoryRepository = Depends(get_onu_repo),
    topology_repo: SQLTopologyRepository = Depends(get_topology_repo),
    ctx: SecurityContext = Depends(get_security_context),
):
    """Vincula uma ONU a uma Zona FTTH, CTO/ODB e porta física do splitter com validação anti-colisão."""
    if "*" not in ctx.scopes and "onus:write" not in ctx.scopes and "onus:provision" not in ctx.scopes:
        ctx.enforce_scope("onus:write")
    clean_serial = sanitize_serial(serial)
    item = onu_repo.get_by_serial(clean_serial)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"ONU '{clean_serial}' não encontrada no inventário.")

    validated = topology_repo.validate_and_assign_onu_topology(clean_serial, req)
    item.zone_id = validated["zone_id"]
    item.odb_id = validated["odb_id"]
    item.odb_splitter_port = validated["odb_splitter_port"]
    if validated["latitude"] is not None:
        item.latitude = validated["latitude"]
    if validated["longitude"] is not None:
        item.longitude = validated["longitude"]

    saved = onu_repo.upsert(item)
    saved.links = {
        "self": Link(href=f"/api/v1/onus/{saved.serial}", method="GET", description="Ver cadastro da ONU"),
        "topology_map": Link(href="/api/v1/topology/health-map", method="GET", description="Mapa de saúde das CTOs"),
    }
    return saved

