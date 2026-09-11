import asyncio
import time
from typing import Optional
from app.models.hateoas import Link
from app.models.olt import ConnectionTestResult


async def test_olt_connectivity(
    olt_id: str,
    host: str,
    port: int,
    timeout_sec: float = 1.5,
) -> ConnectionTestResult:
    """
    Testa a conectividade básica (handshake TCP) com a OLT com timeout agressivo
    para não reter requisições HTTP da API. Retorna diagnóstico e links de fluxo HATEOAS.
    """
    start_time = time.perf_counter()
    reachable = False
    latency_ms: Optional[float] = None
    message = ""

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout_sec,
        )
        elapsed = time.perf_counter() - start_time
        latency_ms = round(elapsed * 1000, 2)
        reachable = True
        message = f"Porta {port} acessível em {host}. Latência de handshake: {latency_ms}ms."

        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

    except asyncio.TimeoutError:
        message = f"Timeout ({int(timeout_sec * 1000)}ms) ao conectar em {host}:{port}. Verifique firewall ou rota."
    except ConnectionRefusedError:
        message = f"Conexão recusada em {host}:{port}. O serviço (SSH/Telnet) pode estar desligado na OLT."
    except OSError as e:
        message = f"Erro de rede ao alcançar {host}:{port}: {str(e)}."
    except Exception as e:
        message = f"Falha inesperada de conectividade com {host}:{port}: {str(e)}."

    # Geração dos hiperlinks contextuais com base no resultado da conectividade
    if reachable:
        links = {
            "self": Link(href=f"/api/v1/olts/{olt_id}", method="GET", description="Ver detalhes da OLT"),
            "config": Link(href=f"/api/v1/olts/{olt_id}/config", method="GET", description="Ver running-config e interfaces"),
            "unauthorized_onus": Link(href=f"/api/v1/olts/{olt_id}/onus/unauthorized", method="GET", description="Consultar ONUs pendentes"),
            "backups": Link(href=f"/api/v1/olts/{olt_id}/backups", method="GET", description="Listar backups"),
            "trigger_backup": Link(href=f"/api/v1/olts/{olt_id}/backups", method="POST", description="Disparar backup imediato"),
        }
    else:
        links = {
            "self": Link(href=f"/api/v1/olts/{olt_id}", method="GET", description="Ver detalhes da OLT"),
            "test_connection": Link(href=f"/api/v1/olts/{olt_id}/test-connection", method="POST", description="Retestar conexão TCP"),
            "edit_olt": Link(href=f"/api/v1/olts/{olt_id}", method="PUT", description="Atualizar IP, porta ou credenciais"),
        }

    return ConnectionTestResult(
        olt_id=olt_id,
        host=host,
        port=port,
        reachable=reachable,
        latency_ms=latency_ms,
        message=message,
        links=links,
    )
