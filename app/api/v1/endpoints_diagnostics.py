from typing import List
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_olt_repo, require_api_key
from app.core.security import sanitize_port, sanitize_safe_string
from app.drivers.factory import DriverFactory
from app.models.hateoas import Link
from app.models.onu import ONUDetails, ONUSummary
from app.storage.olt_repository import OLTRepository

router = APIRouter(prefix="/olts", tags=["Diagnóstico de Portas & ONUs"], dependencies=[Depends(require_api_key)])


@router.get("/{olt_id}/ports/{port:path}/onus", response_model=List[ONUSummary])
def list_port_onus(olt_id: str, port: str, repo: OLTRepository = Depends(get_olt_repo)):
    """Lista as ONUs cadastradas/ativas em uma porta PON específica (ex: '1/1' ou '0/1/1')."""
    olt = repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    try:
        clean_port = sanitize_port(port)
        driver = DriverFactory.get_driver(olt)
        onus = driver.get_port_onus(olt, clean_port)
        for onu in onus:
            onu.links = {
                "details": Link(
                    href=f"/api/v1/olts/{olt_id}/onus/{onu.serial}",
                    method="GET",
                    description="Consultar níveis de potência óptica e detalhes",
                ),
                "reboot": Link(
                    href=f"/api/v1/olts/{olt_id}/onus/{onu.serial}/reboot?port={clean_port}&onu_id={onu.onu_id}",
                    method="POST",
                    description="Reiniciar remotamente esta ONU",
                ),
                "suspend": Link(
                    href=f"/api/v1/olts/{olt_id}/onus/{onu.serial}/suspend?port={clean_port}&onu_id={onu.onu_id}",
                    method="POST",
                    description="Bloquear administrativamente por inadimplência",
                ),
            }
        return onus
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao consultar porta: {str(e)}")


@router.get("/{olt_id}/onus/{serial_or_id}", response_model=ONUDetails)
def get_onu_details(olt_id: str, serial_or_id: str, repo: OLTRepository = Depends(get_olt_repo)):
    """Consulta detalhes operacionais e níveis de potência óptica (Rx/Tx em dBm) de uma ONU."""
    olt = repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    try:
        clean_id = sanitize_safe_string(serial_or_id, "identificador da onu")
        driver = DriverFactory.get_driver(olt)
        details = driver.get_onu_details(olt, clean_id)
        details.links = {
            "reboot": Link(
                href=f"/api/v1/olts/{olt_id}/onus/{clean_id}/reboot?port={details.port}&onu_id={details.onu_id}",
                method="POST",
                description="Reiniciar remotamente esta ONU",
            ),
            "suspend": Link(
                href=f"/api/v1/olts/{olt_id}/onus/{clean_id}/suspend?port={details.port}&onu_id={details.onu_id}",
                method="POST",
                description="Suspender administrativamente o serviço da ONU",
            ),
            "resume": Link(
                href=f"/api/v1/olts/{olt_id}/onus/{clean_id}/resume?port={details.port}&onu_id={details.onu_id}",
                method="POST",
                description="Reativar serviço da ONU",
            ),
            "deprovision": Link(
                href=f"/api/v1/olts/{olt_id}/onus/{clean_id}?port={details.port}&onu_id={details.onu_id}",
                method="DELETE",
                description="Desprovisionar e liberar porta",
            ),
            "port_onus": Link(
                href=f"/api/v1/olts/{olt_id}/ports/{details.port}/onus",
                method="GET",
                description="Listar ONUs da mesma porta",
            ),
        }
        return details
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao diagnosticar ONU: {str(e)}")
