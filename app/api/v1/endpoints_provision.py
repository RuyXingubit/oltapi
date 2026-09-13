from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import get_olt_repo, get_security_context, require_api_key
from app.core.rbac import SecurityContext
from app.core.security import sanitize_port, sanitize_safe_string
from app.drivers.factory import DriverFactory
from app.models.hateoas import Link
from app.models.onu import UnauthorizedONU
from app.models.provision import ONUActionResponse, ProvisionRequest, ProvisionResponse
from app.storage.olt_repository import OLTRepository

router = APIRouter(prefix="/olts", tags=["Provisionamento & Descoberta"], dependencies=[Depends(require_api_key)])


@router.get("/{olt_id}/unauthorized", response_model=List[UnauthorizedONU])
def list_unauthorized_onus(
    olt_id: str,
    serial: Optional[str] = Query(default=None, description="Filtrar por serial específico da ONU"),
    repo: OLTRepository = Depends(get_olt_repo),
    ctx: SecurityContext = Depends(get_security_context),
):
    """Lista as ONUs conectadas fisicamente que aguardam autorização (autofind / unconfigured)."""
    ctx.enforce_scope("onus:discover")
    ctx.enforce_olt(olt_id)

    olt = repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    try:
        driver = DriverFactory.get_driver(olt)
        onus = driver.list_unauthorized_onus(olt)
        if serial:
            clean_serial = serial.strip().upper()
            onus = [o for o in onus if o.serial.upper() == clean_serial]

        for onu in onus:
            onu.links = {
                "provision": Link(
                    href=f"/api/v1/olts/{olt_id}/onus",
                    method="POST",
                    description="Provisionar e autorizar esta ONU",
                )
            }
        return onus
    except ConnectionError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao listar ONUs descobertas: {str(e)}")


@router.post("/{olt_id}/onus", response_model=ProvisionResponse, status_code=status.HTTP_201_CREATED)
def provision_onu(
    olt_id: str,
    req: ProvisionRequest,
    response: Response,
    repo: OLTRepository = Depends(get_olt_repo),
    ctx: SecurityContext = Depends(get_security_context),
):
    """Provisiona e autoriza uma ONU na porta informada aplicando VLAN, perfil e descrição."""
    ctx.enforce_scope("onus:provision")
    ctx.enforce_olt(olt_id)
    if req.vlan:
        ctx.enforce_vlan(olt_id, req.vlan)

    olt = repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    try:
        driver = DriverFactory.get_driver(olt)
        result = driver.provision_onu(olt, req)
        
        # Cabeçalho Location e links de diagnóstico pós-provisionamento
        response.headers["Location"] = f"/api/v1/olts/{olt_id}/onus/{result.serial}"
        result.links = {
            "details": Link(
                href=f"/api/v1/olts/{olt_id}/onus/{result.serial}",
                method="GET",
                description="Consultar níveis de sinal óptico e detalhes da ONU",
            ),
            "port_onus": Link(
                href=f"/api/v1/olts/{olt_id}/ports/{result.port}/onus",
                method="GET",
                description="Listar todas as ONUs da porta PON",
            ),
        }
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao provisionar ONU: {str(e)}")


@router.delete("/{olt_id}/onus/{serial_or_id}", response_model=ONUActionResponse)
def deprovision_onu(
    olt_id: str,
    serial_or_id: str,
    port: Optional[str] = Query(default=None, description="Porta PON da ONU (opcional)"),
    onu_id: Optional[int] = Query(default=None, description="Índice numérico da ONU (opcional)"),
    repo: OLTRepository = Depends(get_olt_repo),
    ctx: SecurityContext = Depends(get_security_context),
):
    """Desprovisiona uma ONU e libera a porta PON e recursos alocados na OLT."""
    ctx.enforce_scope("onus:deprovision")
    ctx.enforce_olt(olt_id)

    olt = repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    try:
        clean_id = sanitize_safe_string(serial_or_id, "identificador da onu")
        clean_port = sanitize_port(port) if port else None
        driver = DriverFactory.get_driver(olt)
        result = driver.deprovision_onu(olt, clean_id, port=clean_port, onu_id=onu_id)
        result.links = {
            "unauthorized_onus": Link(
                href=f"/api/v1/olts/{olt_id}/unauthorized",
                method="GET",
                description="Verificar ONUs não autorizadas para reprovisionamento",
            ),
            "port_onus": Link(
                href=f"/api/v1/olts/{olt_id}/ports/{result.port}/onus" if result.port else f"/api/v1/olts/{olt_id}/unauthorized",
                method="GET",
                description="Listar ONUs ativas na porta",
            ),
            "olt": Link(
                href=f"/api/v1/olts/{olt_id}",
                method="GET",
                description="Consultar dados da OLT",
            ),
        }
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao desprovisionar ONU: {str(e)}")


@router.post("/{olt_id}/onus/{serial_or_id}/reboot", response_model=ONUActionResponse)
def reboot_onu(
    olt_id: str,
    serial_or_id: str,
    port: Optional[str] = Query(default=None, description="Porta PON da ONU (opcional)"),
    onu_id: Optional[int] = Query(default=None, description="Índice numérico da ONU (opcional)"),
    repo: OLTRepository = Depends(get_olt_repo),
    ctx: SecurityContext = Depends(get_security_context),
):
    """Reinicia remotamente a ONU do cliente através de comando de gerenciamento OMCI da OLT."""
    ctx.enforce_scope("onus:actions")
    ctx.enforce_olt(olt_id)

    olt = repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    try:
        clean_id = sanitize_safe_string(serial_or_id, "identificador da onu")
        clean_port = sanitize_port(port) if port else None
        driver = DriverFactory.get_driver(olt)
        result = driver.reboot_onu(olt, clean_id, port=clean_port, onu_id=onu_id)
        result.links = {
            "details": Link(
                href=f"/api/v1/olts/{olt_id}/onus/{result.serial}",
                method="GET",
                description="Verificar status e potências ópticas da ONU pós-reinicialização",
            ),
            "olt": Link(
                href=f"/api/v1/olts/{olt_id}",
                method="GET",
                description="Consultar status da OLT",
            ),
        }
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao reiniciar ONU: {str(e)}")


@router.post("/{olt_id}/onus/{serial_or_id}/suspend", response_model=ONUActionResponse)
def suspend_onu(
    olt_id: str,
    serial_or_id: str,
    port: Optional[str] = Query(default=None, description="Porta PON da ONU (opcional)"),
    onu_id: Optional[int] = Query(default=None, description="Índice numérico da ONU (opcional)"),
    repo: OLTRepository = Depends(get_olt_repo),
    ctx: SecurityContext = Depends(get_security_context),
):
    """Suspende administrativamente a ONU (bloqueio por inadimplência/financeiro) desativando o tráfego GPON sem perder o cadastro."""
    ctx.enforce_scope("onus:actions")
    ctx.enforce_olt(olt_id)

    olt = repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    try:
        clean_id = sanitize_safe_string(serial_or_id, "identificador da onu")
        clean_port = sanitize_port(port) if port else None
        driver = DriverFactory.get_driver(olt)
        result = driver.suspend_onu(olt, clean_id, port=clean_port, onu_id=onu_id)
        result.links = {
            "resume": Link(
                href=f"/api/v1/olts/{olt_id}/onus/{result.serial}/resume" + (f"?port={result.port}&onu_id={result.onu_id}" if result.port else ""),
                method="POST",
                description="Reativar / desbloquear serviço da ONU",
            ),
            "details": Link(
                href=f"/api/v1/olts/{olt_id}/onus/{result.serial}",
                method="GET",
                description="Verificar status da ONU",
            ),
            "deprovision": Link(
                href=f"/api/v1/olts/{olt_id}/onus/{result.serial}" + (f"?port={result.port}&onu_id={result.onu_id}" if result.port else ""),
                method="DELETE",
                description="Desprovisionar e liberar porta se cancelado",
            ),
        }
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao suspender ONU: {str(e)}")


@router.post("/{olt_id}/onus/{serial_or_id}/resume", response_model=ONUActionResponse)
def resume_onu(
    olt_id: str,
    serial_or_id: str,
    port: Optional[str] = Query(default=None, description="Porta PON da ONU (opcional)"),
    onu_id: Optional[int] = Query(default=None, description="Índice numérico da ONU (opcional)"),
    repo: OLTRepository = Depends(get_olt_repo),
    ctx: SecurityContext = Depends(get_security_context),
):
    """Reativa a ONU suspensa (desbloqueio após confirmação de pagamento), restabelecendo o tráfego GPON."""
    ctx.enforce_scope("onus:actions")
    ctx.enforce_olt(olt_id)

    olt = repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    try:
        clean_id = sanitize_safe_string(serial_or_id, "identificador da onu")
        clean_port = sanitize_port(port) if port else None
        driver = DriverFactory.get_driver(olt)
        result = driver.resume_onu(olt, clean_id, port=clean_port, onu_id=onu_id)
        result.links = {
            "details": Link(
                href=f"/api/v1/olts/{olt_id}/onus/{result.serial}",
                method="GET",
                description="Verificar sinal óptico da ONU reativada",
            ),
            "suspend": Link(
                href=f"/api/v1/olts/{olt_id}/onus/{result.serial}/suspend" + (f"?port={result.port}&onu_id={result.onu_id}" if result.port else ""),
                method="POST",
                description="Suspender administrativamente a ONU",
            ),
            "reboot": Link(
                href=f"/api/v1/olts/{olt_id}/onus/{result.serial}/reboot" + (f"?port={result.port}&onu_id={result.onu_id}" if result.port else ""),
                method="POST",
                description="Reiniciar remotamente a ONU",
            ),
        }
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao reativar ONU: {str(e)}")

