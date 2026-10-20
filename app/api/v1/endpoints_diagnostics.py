from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_olt_repo, get_onu_repo, get_security_context, require_api_key
from app.core.rbac import SecurityContext
from app.core.security import sanitize_interface_port, sanitize_safe_string
from app.drivers.factory import DriverFactory
from app.models.hateoas import Link
from app.models.onu import ONUDetails, ONUMacEntry, ONUSummary
from app.models.optical_telemetry import (
    OpticalCollectionSummaryResponse,
    OpticalTelemetrySample,
)
from app.storage.olt_repository import OLTRepository
from app.storage.onu_repository import ONUInventoryRepository

router = APIRouter(prefix="/olts", tags=["Diagnóstico de Portas & ONUs"], dependencies=[Depends(require_api_key)])


@router.get("/{olt_id}/ports/{port:path}/onus", response_model=List[ONUSummary])
def list_port_onus(
    olt_id: str,
    port: str,
    repo: OLTRepository = Depends(get_olt_repo),
    ctx: SecurityContext = Depends(get_security_context),
):
    """Lista as ONUs cadastradas/ativas em uma porta PON específica (ex: '1/1' ou '0/1/1')."""
    ctx.enforce_scope("diagnostics:read")
    ctx.enforce_olt(olt_id)

    olt = repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    try:
        clean_port = sanitize_interface_port(port)
        driver = DriverFactory.get_driver(olt)
        onus = driver.get_port_onus(olt, clean_port)
        for onu in onus:
            onu.links = {
                "details": Link(
                    href=f"/api/v1/olts/{olt_id}/onus/{onu.serial}",
                    method="GET",
                    description="Consultar níveis de potência óptica e detalhes",
                ),
                "macs": Link(
                    href=f"/api/v1/olts/{olt_id}/onus/{onu.serial}/macs?port={clean_port}&onu_id={onu.onu_id}",
                    method="GET",
                    description="Consultar tabela de endereços MAC aprendidos na ONU",
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
def get_onu_details(
    olt_id: str,
    serial_or_id: str,
    repo: OLTRepository = Depends(get_olt_repo),
    onu_repo: ONUInventoryRepository = Depends(get_onu_repo),
    ctx: SecurityContext = Depends(get_security_context),
):
    """Consulta detalhes operacionais, causa da última queda e níveis de potência óptica (Rx/Tx em dBm) de uma ONU."""
    ctx.enforce_scope("diagnostics:read")
    ctx.enforce_olt(olt_id)

    olt = repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    try:
        clean_id = sanitize_safe_string(serial_or_id, "identificador da onu")
        driver = DriverFactory.get_driver(olt)
        details = driver.get_onu_details(olt, clean_id)

        # Persiste amostra na série temporal óptica (Fase 2)
        try:
            if hasattr(onu_repo, "record_optical_sample"):
                onu_repo.record_optical_sample(
                    OpticalTelemetrySample(
                        serial=details.serial or clean_id,
                        olt_id=olt_id,
                        port=details.port,
                        onu_id=details.onu_id,
                        rx_power_dbm=details.rx_power_dbm,
                        tx_power_dbm=details.tx_power_dbm,
                        olt_rx_power_dbm=details.olt_rx_power_dbm,
                        status=details.status or "online",
                        last_down_cause=details.last_down_cause,
                    ),
                    last_down_time=details.last_down_time,
                )
        except Exception:
            pass

        details.links = {
            "optical_history": Link(
                href=f"/api/v1/onus/{details.serial or clean_id}/optical-history",
                method="GET",
                description="Consultar série temporal óptica e deriva de sinal (dBm)",
            ),
            "macs": Link(
                href=f"/api/v1/olts/{olt_id}/onus/{clean_id}/macs?port={details.port}&onu_id={details.onu_id}",
                method="GET",
                description="Consultar tabela FDB/MAC aprendida nas portas da ONU",
            ),
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


@router.get("/{olt_id}/onus/{serial_or_id}/macs", response_model=List[ONUMacEntry])
def get_onu_mac_table(
    olt_id: str,
    serial_or_id: str,
    port: Optional[str] = Query(default=None, description="Porta PON opcional da ONU (ex: '0/1' ou 'gpon1/1')"),
    onu_id: Optional[int] = Query(default=None, description="ID numérico opcional da ONU na porta PON"),
    repo: OLTRepository = Depends(get_olt_repo),
    ctx: SecurityContext = Depends(get_security_context),
):
    """Consulta a tabela de endereços MAC (FDB) aprendidos nas portas Ethernet/VEIP da ONU."""
    ctx.enforce_scope("diagnostics:read")
    ctx.enforce_olt(olt_id)

    olt = repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    try:
        clean_id = sanitize_safe_string(serial_or_id, "identificador da onu")
        clean_port = sanitize_interface_port(port) if port else None
        driver = DriverFactory.get_driver(olt)
        return driver.get_onu_mac_table(olt, clean_id, port=clean_port, onu_id=onu_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao consultar tabela MAC da ONU: {str(e)}",
        )


@router.post("/{olt_id}/telemetry/collect-optical", response_model=OpticalCollectionSummaryResponse)
def collect_olt_optical_telemetry(
    olt_id: str,
    port: Optional[str] = Query(default=None, description="Filtrar coleta por porta PON específica"),
    max_onus: int = Query(default=64, ge=1, le=256, description="Máximo de ONUs coletadas no lote"),
    repo: OLTRepository = Depends(get_olt_repo),
    onu_repo: ONUInventoryRepository = Depends(get_onu_repo),
    ctx: SecurityContext = Depends(get_security_context),
):
    """Executa coleta ativa de potência óptica (dBm) e causa de queda para as ONUs da OLT, alimentando a série temporal."""
    ctx.enforce_scope("diagnostics:read")
    ctx.enforce_olt(olt_id)

    olt = repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    driver = DriverFactory.get_driver(olt)
    target_onus = onu_repo.list_all(olt_id=olt_id, port=port)[:max_onus]
    collected = 0
    degraded = 0

    for item in target_onus:
        try:
            details = driver.get_onu_details(olt, item.serial)
            onu_repo.record_optical_sample(
                OpticalTelemetrySample(
                    serial=item.serial,
                    olt_id=olt_id,
                    port=details.port or item.current_port,
                    onu_id=details.onu_id if details.onu_id is not None else item.current_onu_id,
                    rx_power_dbm=details.rx_power_dbm,
                    tx_power_dbm=details.tx_power_dbm,
                    olt_rx_power_dbm=details.olt_rx_power_dbm,
                    status=details.status or "online",
                    last_down_cause=details.last_down_cause,
                ),
                last_down_time=details.last_down_time,
            )
            collected += 1
            if details.rx_power_dbm is not None and details.rx_power_dbm <= -25.5:
                degraded += 1
        except Exception:
            continue

    return OpticalCollectionSummaryResponse(
        olt_id=olt_id,
        olt_name=olt.name,
        collected_count=collected,
        degraded_count=degraded,
        links={
            "degraded_onus": Link(
                href=f"/api/v1/onus/degraded?olt_id={olt_id}",
                method="GET",
                description="Consultar radar de ONUs com sinal óptico degradado",
            )
        },
    )


