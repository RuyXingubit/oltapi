import logging
import time
from typing import Any, Dict, Optional, Union

from app.core.circuit_id import generate_circuit_id
from app.drivers.factory import DriverFactory
from app.storage.olt_repository import OLTRepository
from app.storage.onu_repository import ONUInventoryRepository
from app.storage.sql.olt_repository import SQLOLTRepository
from app.storage.sql.onu_repository import SQLONUInventoryRepository

logger = logging.getLogger(__name__)


class ONUEnrichmentService:
    """
    Serviço assíncrono para enriquecimento gradual de telemetria e VLANs de ONUs em 2º plano.
    Executa consultas individuais de 'service-info' com cadência controlada para preservar
    a CPU da controladora da OLT em ambientes com centenas ou milhares de clientes.
    """

    def __init__(
        self,
        olt_repo: Union[SQLOLTRepository, OLTRepository],
        onu_repo: Union[SQLONUInventoryRepository, ONUInventoryRepository],
    ):
        self.olt_repo = olt_repo
        self.onu_repo = onu_repo

    def enrich_olt_onus(
        self,
        olt_id: str,
        force: bool = False,
        delay_seconds: float = 0.08,
        max_onus: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Percorre as ONUs da OLT que estejam sem VLAN definida (ou todas se force=True),
        descobrindo a VLAN real de serviço configurada no chassi.
        """
        olt = self.olt_repo.get_by_id(olt_id)
        if not olt:
            raise ValueError(f"OLT '{olt_id}' não encontrada.")

        driver = DriverFactory.get_driver(olt)
        all_onus = self.onu_repo.list_all(olt_id=olt_id)

        target_onus = [o for o in all_onus if force or o.vlan is None]
        if max_onus:
            target_onus = target_onus[:max_onus]

        total_target = len(target_onus)
        if total_target == 0:
            logger.info(f"[Enrichment] Nenhuma ONU pendente de VLAN na OLT {olt.name}.")
            return {
                "olt_id": olt_id,
                "olt_name": olt.name,
                "total_scanned": 0,
                "vlans_discovered": 0,
                "duration_seconds": 0.0,
                "status": "completed",
            }

        logger.info(f"[Enrichment] Iniciando varredura gradual de VLANs para {total_target} ONUs na OLT {olt.name}...")
        start_time = time.perf_counter()
        discovered_count = 0

        # Para Fiberhome Telnet CLI: abre uma única sessão Telnet contínua
        if getattr(driver, "is_telnet_cli", None) and driver.is_telnet_cli(olt):
            try:
                client = driver._open_telnet_session(olt)
            except Exception as e:
                logger.warning(f"[Enrichment] Falha ao abrir sessão Telnet na OLT {olt.name}: {e}")
                return {
                    "olt_id": olt_id,
                    "olt_name": olt.name,
                    "total_scanned": total_target,
                    "vlans_discovered": 0,
                    "duration_seconds": round(time.perf_counter() - start_time, 2),
                    "status": "failed",
                    "error": str(e),
                }

            try:
                client.write("cd onu\r\n")
                time.sleep(0.2)
                client.read_until([b"#"])

                for item in target_onus:
                    if not item.current_port or item.current_onu_id is None:
                        continue

                    parts = item.current_port.split("/")
                    if len(parts) != 2:
                        continue
                    slot, pon = parts[0], parts[1]

                    try:
                        srv_out = driver._exec_telnet_cmd(
                            client,
                            f"show onu service-info slot {slot} pon {pon} onu {item.current_onu_id}",
                        )
                        real_vlan = driver.parse_telnet_service_vlan(srv_out)
                        if real_vlan:
                            item.vlan = real_vlan
                            item.circuit_id = generate_circuit_id(
                                olt.name, item.current_port, item.current_onu_id, real_vlan
                            )
                            self.onu_repo.upsert(item)
                            discovered_count += 1
                        elif force and item.vlan is not None:
                            item.vlan = None
                            item.circuit_id = generate_circuit_id(
                                olt.name, item.current_port, item.current_onu_id, None
                            )
                            self.onu_repo.upsert(item)
                    except Exception as err:
                        logger.debug(f"[Enrichment] Falha ao consultar ONU {item.serial}: {err}")

                    time.sleep(delay_seconds)
            finally:
                try:
                    client.write("exit\r\n")
                    client.close()
                except Exception:
                    pass
        else:
            # Fallback genérico para outros drivers que implementam get_onu_details
            for item in target_onus:
                try:
                    details = driver.get_onu_details(olt, item.serial)
                    if details.vlan:
                        item.vlan = details.vlan
                        item.circuit_id = generate_circuit_id(
                            olt.name, item.current_port, item.current_onu_id, details.vlan
                        )
                        self.onu_repo.upsert(item)
                        discovered_count += 1
                except Exception as err:
                    logger.debug(f"[Enrichment] Falha ao consultar ONU {item.serial}: {err}")
                time.sleep(delay_seconds)

        duration = round(time.perf_counter() - start_time, 2)
        logger.info(
            f"[Enrichment] Concluído para OLT {olt.name}: {discovered_count}/{total_target} VLANs descobertas em {duration}s."
        )

        return {
            "olt_id": olt_id,
            "olt_name": olt.name,
            "total_scanned": total_target,
            "vlans_discovered": discovered_count,
            "duration_seconds": duration,
            "status": "completed",
        }
