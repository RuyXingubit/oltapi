import json
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx

from app.models.acs import (
    ACSConnectionTestResponse,
    TR069ActionResponse,
    TR069DeviceSummary,
    TR069FirmwarePushRequest,
    TR069WanConfigRequest,
    TR069WiFiConfigRequest,
)
from app.storage.sql.acs_repository import SQLACSRepository

logger = logging.getLogger(__name__)


class ACSService:
    """
    Serviço de integração com servidores ACS TR-069 / CWMP (padrão GenieACS NBI REST) - Fase 5.
    Suporta consulta de árvore de parâmetros TR-098/TR-181, reconfiguração de Wi-Fi 2.4G/5G,
    provisionamento WAN (PPPoE/DHCP/Bridge) e agendamento de atualização de firmware OTA.
    """

    def __init__(self, acs_repo: SQLACSRepository, timeout_seconds: float = 5.0):
        self.acs_repo = acs_repo
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def _extract_param_value(tree: Dict[str, Any], paths: List[str]) -> Optional[Any]:
        """Navega defensivamente pelos nós TR-098 / TR-181 do GenieACS buscando `_value`."""
        for path in paths:
            node: Any = tree
            for part in path.split("."):
                if isinstance(node, dict) and part in node:
                    node = node[part]
                else:
                    node = None
                    break
            if isinstance(node, dict) and "_value" in node:
                return node["_value"]
            if isinstance(node, (str, int, float, bool)):
                return node
        return None

    def test_connection(self, server_id: str) -> ACSConnectionTestResponse:
        cred = self.acs_repo.get_server_with_credentials(server_id)
        if not cred:
            raise ValueError(f"Servidor ACS '{server_id}' não encontrado.")
        server, password = cred
        auth = (server.username, password or "") if server.username else None

        try:
            with httpx.Client(timeout=self.timeout_seconds, auth=auth) as client:
                resp = client.get(f"{server.nbi_url}/devices/?projection=_id")
                reachable = resp.status_code < 500
                return ACSConnectionTestResponse(
                    server_id=server.id,
                    server_name=server.name,
                    nbi_url=server.nbi_url,
                    reachable=reachable,
                    status_code=resp.status_code,
                    message="Conectividade NBI TR-069 validada com sucesso."
                    if reachable
                    else f"Servidor respondeu com HTTP {resp.status_code}.",
                )
        except Exception as e:
            return ACSConnectionTestResponse(
                server_id=server.id,
                server_name=server.name,
                nbi_url=server.nbi_url,
                reachable=False,
                status_code=None,
                message=f"Sem resposta da NBI em '{server.nbi_url}': {str(e)}",
            )

    def get_device_summary(self, serial: str) -> TR069DeviceSummary:
        clean_serial = serial.strip().upper()
        cred = self.acs_repo.get_server_with_credentials()
        if not cred:
            return TR069DeviceSummary(
                serial=clean_serial,
                registered_in_acs=False,
                message="Nenhum servidor ACS TR-069 ativo configurado na plataforma.",
            )

        server, password = cred
        auth = (server.username, password or "") if server.username else None
        query_json = json.dumps({"_deviceId._SerialNumber": clean_serial})

        try:
            with httpx.Client(timeout=self.timeout_seconds, auth=auth) as client:
                resp = client.get(f"{server.nbi_url}/devices/?query={quote(query_json)}")
                if resp.status_code != 200:
                    return TR069DeviceSummary(
                        serial=clean_serial,
                        registered_in_acs=False,
                        acs_server_name=server.name,
                        message=f"ACS retornou HTTP {resp.status_code}.",
                    )
                devices = resp.json()
                if not devices:
                    return TR069DeviceSummary(
                        serial=clean_serial,
                        registered_in_acs=False,
                        acs_server_name=server.name,
                        message="ONU ainda não realizou Inform CWMP no servidor ACS.",
                    )

                dev = devices[0]
                device_id = dev.get("_id")
                last_inform = dev.get("_lastInform")

                sw_ver = self._extract_param_value(
                    dev,
                    [
                        "InternetGatewayDevice.DeviceInfo.SoftwareVersion",
                        "Device.DeviceInfo.SoftwareVersion",
                    ],
                )
                hw_ver = self._extract_param_value(
                    dev,
                    [
                        "InternetGatewayDevice.DeviceInfo.HardwareVersion",
                        "Device.DeviceInfo.HardwareVersion",
                    ],
                )
                wan_ip = self._extract_param_value(
                    dev,
                    [
                        "InternetGatewayDevice.WANDevice.1.WANConnectionDevice.1.WANPPPConnection.1.ExternalIPAddress",
                        "InternetGatewayDevice.WANDevice.1.WANConnectionDevice.1.WANIPConnection.1.ExternalIPAddress",
                        "Device.IP.Interface.1.IPv4Address.1.IPAddress",
                    ],
                )
                pppoe_user = self._extract_param_value(
                    dev,
                    [
                        "InternetGatewayDevice.WANDevice.1.WANConnectionDevice.1.WANPPPConnection.1.Username",
                        "Device.PPP.Interface.1.Username",
                    ],
                )
                ssid_24 = self._extract_param_value(
                    dev,
                    [
                        "InternetGatewayDevice.LANDevice.1.WLANConfiguration.1.SSID",
                        "Device.WiFi.SSID.1.SSID",
                    ],
                )
                ssid_5 = self._extract_param_value(
                    dev,
                    [
                        "InternetGatewayDevice.LANDevice.1.WLANConfiguration.5.SSID",
                        "Device.WiFi.SSID.2.SSID",
                    ],
                )

                return TR069DeviceSummary(
                    serial=clean_serial,
                    acs_device_id=device_id,
                    registered_in_acs=True,
                    acs_server_name=server.name,
                    last_inform=str(last_inform) if last_inform else None,
                    software_version=str(sw_ver) if sw_ver else None,
                    hardware_version=str(hw_ver) if hw_ver else None,
                    wan_mode="pppoe" if pppoe_user else ("dhcp" if wan_ip else None),
                    wan_ip=str(wan_ip) if wan_ip else None,
                    pppoe_username=str(pppoe_user) if pppoe_user else None,
                    ssid_24g=str(ssid_24) if ssid_24 else None,
                    ssid_5g=str(ssid_5) if ssid_5 else None,
                    message="Parâmetros TR-069 sincronizados do ACS.",
                )
        except Exception as e:
            logger.debug(f"Falha ao consultar ACS NBI para {clean_serial}: {e}")
            return TR069DeviceSummary(
                serial=clean_serial,
                registered_in_acs=False,
                acs_server_name=server.name,
                message=f"Servidor ACS '{server.name}' indisponível no momento: {str(e)}",
            )

    def _enqueue_acs_task(self, serial: str, task_payload: Dict[str, Any], action_label: str) -> TR069ActionResponse:
        clean_serial = serial.strip().upper()
        cred = self.acs_repo.get_server_with_credentials()
        if not cred:
            raise ValueError("Nenhum servidor ACS TR-069 ativo está configurado.")

        server, password = cred
        auth = (server.username, password or "") if server.username else None
        summary = self.get_device_summary(clean_serial)
        device_id = summary.acs_device_id or clean_serial

        try:
            with httpx.Client(timeout=self.timeout_seconds, auth=auth) as client:
                url = f"{server.nbi_url}/devices/{quote(device_id, safe='')}/tasks?connection_request"
                resp = client.post(url, json=task_payload)
                if resp.status_code in (200, 202):
                    return TR069ActionResponse(
                        serial=clean_serial,
                        acs_device_id=device_id,
                        task_queued=True,
                        action=action_label,
                        message=f"Task CWMP '{action_label}' aplicada/enfileirada no ACS '{server.name}'.",
                    )
                return TR069ActionResponse(
                    serial=clean_serial,
                    acs_device_id=device_id,
                    task_queued=False,
                    action=action_label,
                    message=f"ACS '{server.name}' respondeu HTTP {resp.status_code} ao enfileirar task.",
                )
        except Exception as e:
            return TR069ActionResponse(
                serial=clean_serial,
                acs_device_id=device_id,
                task_queued=False,
                action=action_label,
                message=f"Não foi possível contatar o ACS '{server.name}': {str(e)}",
            )

    def push_wifi_config(self, serial: str, req: TR069WiFiConfigRequest) -> TR069ActionResponse:
        parameter_values = []
        if req.ssid_24g:
            parameter_values.append(
                ["InternetGatewayDevice.LANDevice.1.WLANConfiguration.1.SSID", req.ssid_24g, "xsd:string"]
            )
        if req.password_24g:
            parameter_values.append(
                [
                    "InternetGatewayDevice.LANDevice.1.WLANConfiguration.1.PreSharedKey.1.KeyPassphrase",
                    req.password_24g,
                    "xsd:string",
                ]
            )
        if req.ssid_5g:
            parameter_values.append(
                ["InternetGatewayDevice.LANDevice.1.WLANConfiguration.5.SSID", req.ssid_5g, "xsd:string"]
            )
        if req.password_5g:
            parameter_values.append(
                [
                    "InternetGatewayDevice.LANDevice.1.WLANConfiguration.5.PreSharedKey.1.KeyPassphrase",
                    req.password_5g,
                    "xsd:string",
                ]
            )

        if not parameter_values:
            raise ValueError("Informe ao menos um parâmetro Wi-Fi (SSID ou senha 2.4GHz/5GHz) para alterar.")

        task = {"name": "setParameterValues", "parameterValues": parameter_values}
        return self._enqueue_acs_task(serial, task, "wifi_reconfig")

    def push_wan_config(self, serial: str, req: TR069WanConfigRequest) -> TR069ActionResponse:
        mode = req.mode.strip().lower()
        if mode not in ("pppoe", "dhcp", "bridge", "static"):
            raise ValueError("Modo WAN inválido. Use: pppoe, dhcp, bridge ou static.")

        parameter_values = []
        if mode == "pppoe":
            if not req.pppoe_username:
                raise ValueError("pppoe_username é obrigatório quando mode='pppoe'.")
            parameter_values.append(
                [
                    "InternetGatewayDevice.WANDevice.1.WANConnectionDevice.1.WANPPPConnection.1.Username",
                    req.pppoe_username,
                    "xsd:string",
                ]
            )
            if req.pppoe_password:
                parameter_values.append(
                    [
                        "InternetGatewayDevice.WANDevice.1.WANConnectionDevice.1.WANPPPConnection.1.Password",
                        req.pppoe_password,
                        "xsd:string",
                    ]
                )
        if req.vlan_id is not None:
            parameter_values.append(
                [
                    "InternetGatewayDevice.WANDevice.1.WANConnectionDevice.1.X_CT-COM_WANGponLinkConfig.VLANIDMark",
                    req.vlan_id,
                    "xsd:unsignedInt",
                ]
            )

        task = {"name": "setParameterValues", "parameterValues": parameter_values}
        return self._enqueue_acs_task(serial, task, f"wan_{mode}")

    def push_firmware_upgrade(self, serial: str, req: TR069FirmwarePushRequest) -> TR069ActionResponse:
        task = {
            "name": "download",
            "fileType": req.file_type,
            "fileName": req.firmware_filename.strip(),
        }
        return self._enqueue_acs_task(serial, task, "firmware_upgrade")
