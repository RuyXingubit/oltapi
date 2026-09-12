from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_scanner_service, require_api_key
from app.models.scanner import (
    ScannerIntervalUpdateRequest,
    ScannerRunResult,
    ScannerStatus,
)
from app.services.autofind_scanner import AutofindScannerService

router = APIRouter(
    prefix="/scanner",
    tags=["Autofind Scanner"],
    dependencies=[Depends(require_api_key)],
)


@router.get(
    "/status",
    response_model=ScannerStatus,
    summary="Consultar status do Autofind Scanner",
    description="Retorna o estado operacional do worker (ativo/inativo), intervalo atual e métricas acumuladas.",
)
async def get_scanner_status(
    scanner: AutofindScannerService = Depends(get_scanner_service),
) -> ScannerStatus:
    return scanner.get_status()


@router.post(
    "/start",
    response_model=ScannerStatus,
    summary="Iniciar o worker do Autofind Scanner",
    description="Inicia o loop assíncrono periódico em background caso esteja parado.",
)
async def start_scanner(
    scanner: AutofindScannerService = Depends(get_scanner_service),
) -> ScannerStatus:
    scanner.start()
    return scanner.get_status()


@router.post(
    "/stop",
    response_model=ScannerStatus,
    summary="Parar o worker do Autofind Scanner",
    description="Interrompe graciosamente o loop de varredura periódica.",
)
async def stop_scanner(
    scanner: AutofindScannerService = Depends(get_scanner_service),
) -> ScannerStatus:
    await scanner.stop()
    return scanner.get_status()


@router.post(
    "/run-now",
    response_model=ScannerRunResult,
    summary="Forçar varredura de autofind sob demanda",
    description="Executa imediatamente um ciclo de varredura completo em todas as OLTs cadastradas.",
)
async def run_scanner_now(
    scanner: AutofindScannerService = Depends(get_scanner_service),
) -> ScannerRunResult:
    try:
        result = await scanner.run_scan_cycle()
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha ao executar ciclo de varredura sob demanda: {str(e)}",
        )


@router.patch(
    "/interval",
    response_model=ScannerStatus,
    summary="Atualizar intervalo de varredura periódica",
    description="Modifica o tempo entre ciclos de varredura (mínimo defensivo: 10 segundos).",
)
async def update_scanner_interval(
    req: ScannerIntervalUpdateRequest,
    scanner: AutofindScannerService = Depends(get_scanner_service),
) -> ScannerStatus:
    scanner.set_interval(req.interval_seconds)
    return scanner.get_status()
