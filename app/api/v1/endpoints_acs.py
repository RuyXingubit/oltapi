from typing import List
from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import (
    get_acs_repo,
    get_acs_service,
    get_security_context,
    require_api_key,
)
from app.core.rbac import SecurityContext
from app.core.security import sanitize_serial
from app.models.acs import (
    ACSConnectionTestResponse,
    ACSServerConfigCreate,
    ACSServerConfigItem,
    TR069ActionResponse,
    TR069DeviceSummary,
    TR069FirmwarePushRequest,
    TR069WanConfigRequest,
    TR069WiFiConfigRequest,
)
from app.models.hateoas import Link
from app.services.acs_service import ACSService
from app.storage.sql.acs_repository import SQLACSRepository

router = APIRouter(
    tags=["Gerência Remota TR-069 / CWMP & ACS (Fase 5)"],
    dependencies=[Depends(require_api_key)],
)


@router.get("/acs/servers", response_model=List[ACSServerConfigItem])
def list_acs_servers(
    repo: SQLACSRepository = Depends(get_acs_repo),
    ctx: SecurityContext = Depends(get_security_context),
):
    """Lista os servidores ACS TR-069 / CWMP (ex: GenieACS NBI) configurados na plataforma."""
    ctx.enforce_scope("olts:read")
    items = repo.list_servers()
    for item in items:
        item.links = {
            "test": Link(
                href=f"/api/v1/acs/servers/{item.id}/test",
                method="POST",
                description="Testar conectividade NBI com este servidor ACS",
            ),
            "delete": Link(
                href=f"/api/v1/acs/servers/{item.id}",
                method="DELETE",
                description="Remover servidor ACS",
            ),
        }
    return items


@router.post("/acs/servers", response_model=ACSServerConfigItem, status_code=status.HTTP_201_CREATED)
def create_acs_server(
    req: ACSServerConfigCreate,
    response: Response,
    repo: SQLACSRepository = Depends(get_acs_repo),
    ctx: SecurityContext = Depends(get_security_context),
):
    """Cadastra um servidor ACS TR-069 / CWMP com senha cifrada em repouso via Fernet AES."""
    ctx.enforce_scope("olts:admin")
    try:
        item = repo.create_server(req)
        response.headers["Location"] = f"/api/v1/acs/servers/{item.id}"
        item.links = {
            "test": Link(
                href=f"/api/v1/acs/servers/{item.id}/test",
                method="POST",
                description="Testar conectividade NBI",
            )
        }
        return item
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/acs/servers/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_acs_server(
    server_id: str,
    repo: SQLACSRepository = Depends(get_acs_repo),
    ctx: SecurityContext = Depends(get_security_context),
):
    """Remove um servidor ACS cadastrado."""
    ctx.enforce_scope("olts:admin")
    if not repo.delete_server(server_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Servidor ACS '{server_id}' não encontrado.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/acs/servers/{server_id}/test", response_model=ACSConnectionTestResponse)
def test_acs_server(
    server_id: str,
    service: ACSService = Depends(get_acs_service),
    ctx: SecurityContext = Depends(get_security_context),
):
    """Valida a conectividade HTTP/REST com a Northbound Interface (NBI) do servidor ACS TR-069."""
    ctx.enforce_scope("olts:read")
    try:
        return service.test_connection(server_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/onus/{serial}/tr069", response_model=TR069DeviceSummary)
def get_onu_tr069_summary(
    serial: str,
    service: ACSService = Depends(get_acs_service),
    ctx: SecurityContext = Depends(get_security_context),
):
    """Consulta o estado TR-069 / CWMP da ONU no ACS ativo (Wi-Fi SSID, WAN IP, PPPoE, versão de firmware e Last Inform)."""
    ctx.enforce_scope("onus:read")
    clean_serial = sanitize_serial(serial)
    summary = service.get_device_summary(clean_serial)
    summary.links = {
        "wifi": Link(
            href=f"/api/v1/onus/{clean_serial}/tr069/wifi",
            method="POST",
            description="Alterar SSID e senha Wi-Fi 2.4GHz/5GHz via TR-069",
        ),
        "wan": Link(
            href=f"/api/v1/onus/{clean_serial}/tr069/wan",
            method="POST",
            description="Reconfigurar WAN PPPoE/DHCP/Bridge via TR-069",
        ),
        "firmware": Link(
            href=f"/api/v1/onus/{clean_serial}/tr069/firmware",
            method="POST",
            description="Agendar upgrade de firmware OTA via TR-069",
        ),
    }
    return summary


@router.post("/onus/{serial}/tr069/wifi", response_model=TR069ActionResponse)
def configure_onu_tr069_wifi(
    serial: str,
    req: TR069WiFiConfigRequest,
    service: ACSService = Depends(get_acs_service),
    ctx: SecurityContext = Depends(get_security_context),
):
    """Envia task CWMP `setParameterValues` ao ACS para alterar SSID e senha Wi-Fi 2.4GHz e/ou 5GHz da ONU."""
    ctx.enforce_scope("onus:actions")
    clean_serial = sanitize_serial(serial)
    try:
        res = service.push_wifi_config(clean_serial, req)
        res.links = {
            "tr069": Link(href=f"/api/v1/onus/{clean_serial}/tr069", method="GET", description="Ver status TR-069"),
        }
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/onus/{serial}/tr069/wan", response_model=TR069ActionResponse)
def configure_onu_tr069_wan(
    serial: str,
    req: TR069WanConfigRequest,
    service: ACSService = Depends(get_acs_service),
    ctx: SecurityContext = Depends(get_security_context),
):
    """Envia task CWMP `setParameterValues` ao ACS para configurar credenciais PPPoE, DHCP, Bridge e VLAN WAN da ONU."""
    ctx.enforce_scope("onus:actions")
    clean_serial = sanitize_serial(serial)
    try:
        res = service.push_wan_config(clean_serial, req)
        res.links = {
            "tr069": Link(href=f"/api/v1/onus/{clean_serial}/tr069", method="GET", description="Ver status TR-069"),
        }
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/onus/{serial}/tr069/firmware", response_model=TR069ActionResponse)
def push_onu_tr069_firmware(
    serial: str,
    req: TR069FirmwarePushRequest,
    service: ACSService = Depends(get_acs_service),
    ctx: SecurityContext = Depends(get_security_context),
):
    """Envia task CWMP `download` ao ACS para atualização remota de firmware (OTA) da ONU."""
    ctx.enforce_scope("onus:actions")
    clean_serial = sanitize_serial(serial)
    try:
        res = service.push_firmware_upgrade(clean_serial, req)
        res.links = {
            "tr069": Link(href=f"/api/v1/onus/{clean_serial}/tr069", method="GET", description="Ver status TR-069"),
        }
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
