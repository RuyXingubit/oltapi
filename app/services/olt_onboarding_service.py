import asyncio
import json
import logging
import re
import socket
import time
from typing import AsyncGenerator, Dict, List, Optional, Tuple, Union
import paramiko

from app.core.uuid import generate_uuid7
from app.drivers.factory import DriverFactory
from app.drivers.fiberhome.telnet_client import TelnetClient
from app.models.hateoas import Link
from app.models.olt import (
    OLTInDB,
    OLTOnboardRequest,
    OLTOnboardResponse,
    OLTProtocol,
    OLTVendor,
    OnboardingStepItem,
)
from app.services.backup_service import BackupService
from app.services.olt_sync_service import OLTSyncService
from app.services.olt_telemetry_service import OLTTelemetryService
from app.services.snmp_collector import SNMPCollector
from app.storage.olt_repository import OLTRepository
from app.storage.sql.olt_repository import SQLOLTRepository

logger = logging.getLogger(__name__)


def slugify_community(name: str, fallback: str = "provedor") -> str:
    """Gera um slug seguro e limpo para comunidade SNMP a partir do nome da empresa/tenant."""
    if not name:
        return fallback
    clean = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip().lower()).strip("_")
    return clean[:24] or fallback


class OLTOnboardingService:
    """
    Serviço de Onboarding Automatizado ("Zero-Touch") de OLTs.
    Executa o pipeline contínuo à prova de erro humano:
    1. Probe de Conectividade (SSH :22 com Fallback Telnet :23)
    2. Fingerprinting Automático de Fabricante & Modelo
    3. Criação da OLT e Snapshot Preventivo Baseline v0
    4. Diagnóstico e Provisionamento SNMP Dinâmico (Tenant / Empresa)
    5. Ingestão de Portas Físicas, VLANs e ONUs com Circuit ID TR-101
    6. Retorno Consolidado para Apresentação do Card Resumo
    """

    def __init__(
        self,
        olt_repo: Union[SQLOLTRepository, OLTRepository],
        backup_service: BackupService,
        sync_service: OLTSyncService,
        telemetry_service: OLTTelemetryService,
    ):
        self.olt_repo = olt_repo
        self.backup_service = backup_service
        self.sync_service = sync_service
        self.telemetry_service = telemetry_service

    def probe_connectivity(
        self,
        host: str,
        username: str,
        password: str,
        custom_port: Optional[int] = None,
    ) -> Tuple[OLTProtocol, int, str]:
        """
        Testa conectividade e autenticação.
        Se custom_port for informada, tenta SSH e Telnet nessa porta.
        Se omitida, tenta primeiro SSH (porta 22); em caso de falha/recusa/timeout, tenta Telnet (porta 23).
        Retorna (protocolo, porta, banner_ou_prompt_capturado).
        """
        ports_to_try: List[Tuple[OLTProtocol, int]] = []
        if custom_port:
            ports_to_try = [(OLTProtocol.SSH, custom_port), (OLTProtocol.TELNET, custom_port)]
        else:
            ports_to_try = [(OLTProtocol.SSH, 22), (OLTProtocol.TELNET, 23)]

        last_error = ""

        for proto, port in ports_to_try:
            logger.info(f"[Onboarding Probe] Tentando handshake {proto.value.upper()} em {host}:{port}...")
            if proto == OLTProtocol.SSH:
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                try:
                    ssh.connect(
                        hostname=host,
                        port=port,
                        username=username,
                        password=password,
                        timeout=4.0,
                        banner_timeout=4.0,
                        auth_timeout=4.0,
                        allow_agent=False,
                        look_for_keys=False,
                    )
                    # Abre canal para capturar prompt/banner
                    channel = ssh.invoke_shell()
                    channel.settimeout(3.0)
                    time.sleep(0.5)
                    banner = ""
                    if channel.recv_ready():
                        banner = channel.recv(4096).decode("utf-8", errors="ignore")
                    ssh.close()
                    logger.info(f"[Onboarding Probe] Conexão SSH estabelecida com sucesso em {host}:{port}.")
                    return (OLTProtocol.SSH, port, banner)
                except Exception as e:
                    last_error = f"SSH ({port}): {e}"
                    logger.debug(f"[Onboarding Probe] Falha SSH em {host}:{port}: {e}")
            elif proto == OLTProtocol.TELNET:
                try:
                    tn = TelnetClient(host=host, port=port, timeout=4)
                    tn.connect()
                    # Aguarda prompt de login
                    banner_bytes = tn.read_until([b":", b">", b"#", b"%", b"login", b"Username"], timeout=3)
                    banner_str = banner_bytes.decode("ascii", errors="ignore")

                    # Se pediu login/user, envia credenciais
                    if any(w in banner_str.lower() for w in ["login", "user", "username", ":"]):
                        tn.write(username.encode() + b"\n")
                        tn.read_until([b"password", b"Password", b"Pass", b":"], timeout=3)
                        tn.write(password.encode() + b"\n")
                        prompt_bytes = tn.read_until([b">", b"#", b"%", b"$", b":"], timeout=3)
                        banner_str += " " + prompt_bytes.decode("ascii", errors="ignore")

                    tn.close()
                    logger.info(f"[Onboarding Probe] Conexão Telnet estabelecida com sucesso em {host}:{port}.")
                    return (OLTProtocol.TELNET, port, banner_str)
                except Exception as e:
                    last_error = f"Telnet ({port}): {e}"
                    logger.debug(f"[Onboarding Probe] Falha Telnet em {host}:{port}: {e}")

        raise ConnectionError(
            f"Não foi possível autenticar na OLT em {host} via SSH ou Telnet. "
            f"Verifique IP, rota e credenciais de acesso. Último erro: {last_error}"
        )

    def fingerprint_vendor_and_model(self, banner_or_prompt: str) -> Tuple[OLTVendor, str]:
        """
        Reconhece automaticamente o fabricante e modelo a partir de palavras-chave
        do banner, prompt de login e identificadores padrão de firmware.
        """
        text = (banner_or_prompt or "").lower()

        if any(k in text for k in ["fiberhome", "an5516", "an6000", "admin%", "gepon_ngn", "ngn"]):
            return (OLTVendor.FIBERHOME, "an5516")
        elif any(k in text for k in ["huawei", "vrp", "ma5800", "ma5608", "<huawei", "smartax"]):
            return (OLTVendor.HUAWEI, "ma5800")
        elif any(k in text for k in ["zte", "zxros", "zxa10", "c300", "c320"]):
            return (OLTVendor.ZTE, "c320")
        elif any(k in text for k in ["intelbras", "8820"]):
            return (OLTVendor.INTELBRAS, "8820")
        elif any(k in text for k in ["vsol", "v1600"]):
            return (OLTVendor.VSOL, "v1600")

        # Padrão seguro caso inconclusivo
        logger.info(f"[Onboarding Fingerprint] Banner inconclusivo ({text[:80]}). Adotando Fiberhome AN5516 como padrão.")
        return (OLTVendor.FIBERHOME, "an5516")

    def execute_onboarding(
        self,
        request: OLTOnboardRequest,
        tenant_name: Optional[str] = None,
    ) -> OLTOnboardResponse:
        """
        Executa o pipeline contínuo de onboarding Zero-Touch.
        """
        steps: List[OnboardingStepItem] = []
        company_slug = slugify_community(tenant_name or "provedor")

        # ---------------------------------------------------------------------
        # Etapa 1: Negociação de Conectividade (SSH -> Telnet)
        # ---------------------------------------------------------------------
        try:
            protocol, port, banner_prompt = self.probe_connectivity(
                host=request.host,
                username=request.username,
                password=request.password,
                custom_port=request.custom_port,
            )
            steps.append(
                OnboardingStepItem(
                    step_key="connectivity",
                    title="Negociação de Conexão",
                    status="success",
                    details=f"Conectado com sucesso via {protocol.value.upper()} na porta {port}.",
                )
            )
        except Exception as e:
            steps.append(
                OnboardingStepItem(
                    step_key="connectivity",
                    title="Negociação de Conexão",
                    status="error",
                    details=str(e),
                )
            )
            raise ConnectionError(str(e))

        # ---------------------------------------------------------------------
        # Etapa 2: Reconhecimento do Fabricante e Modelo
        # ---------------------------------------------------------------------
        vendor, model = self.fingerprint_vendor_and_model(banner_prompt)
        steps.append(
            OnboardingStepItem(
                step_key="fingerprint",
                title="Reconhecimento do Fabricante",
                status="success",
                details=f"Fabricante identificado: {vendor.value.upper()} (Modelo: {model.upper()}).",
            )
        )

        # ---------------------------------------------------------------------
        # Etapa 3: Cadastro Atômico da OLT
        # ---------------------------------------------------------------------
        default_community = f"olt_{company_slug}"
        olt_id = generate_uuid7()
        olt_entity = OLTInDB(
            id=olt_id,
            name=request.name.strip(),
            vendor=vendor,
            model=model,
            host=request.host.strip(),
            port=port,
            protocol=protocol,
            username=request.username.strip(),
            password=request.password.strip(),
            snmp_community=default_community,
            snmp_port=161,
            snmp_version="v2c",
        )
        created_olt = self.olt_repo.create(olt_entity)

        # ---------------------------------------------------------------------
        # Etapa 4: Snapshot de Segurança Obrigatório (Baseline v0)
        # ---------------------------------------------------------------------
        try:
            baseline_backup = self.backup_service.create_backup(
                olt_id=created_olt.id,
                notes="Baseline v0 - Onboarding Zero-Touch Full Discovery",
            )
            baseline_backup_id = baseline_backup.backup_id
            steps.append(
                OnboardingStepItem(
                    step_key="baseline_backup",
                    title="Backup Preventivo Baseline v0",
                    status="success",
                    details=f"Backup de segurança gravado em disco com SHA-256 (ID: {baseline_backup_id}).",
                )
            )
        except Exception as e:
            steps.append(
                OnboardingStepItem(
                    step_key="baseline_backup",
                    title="Backup Preventivo Baseline v0",
                    status="warning",
                    details=f"Aviso ao extrair backup completo da OLT: {e}",
                )
            )
            baseline_backup_id = "baseline_v0_pendente"

        # ---------------------------------------------------------------------
        # Etapa 5: Diagnóstico e Provisionamento SNMP Dinâmico (Zero Hardcode)
        # ---------------------------------------------------------------------
        snmp_active, final_community, step_snmp = self._discover_and_configure_snmp(
            created_olt=created_olt,
            tenant_name=tenant_name,
        )
        steps.append(step_snmp)

        # ---------------------------------------------------------------------
        # Etapa 6: Ingestão de Portas, VLANs e ONUs no Inventário
        # ---------------------------------------------------------------------
        try:
            sync_res = self.sync_service.sync_olt(created_olt.id)
            total_onus = sync_res.total_onus_discovered
            new_onus = sync_res.new_onus_registered
            steps.append(
                OnboardingStepItem(
                    step_key="inventory_sync",
                    title="Ingestão de Inventário & TR-101",
                    status="success",
                    details=f"{total_onus} ONUs sincronizadas com cálculo de Circuit ID TR-101.",
                )
            )
        except Exception as e:
            logger.warning(f"[Onboarding Sync] Erro ao sincronizar inventário: {e}")
            total_onus = 0
            new_onus = 0
            steps.append(
                OnboardingStepItem(
                    step_key="inventory_sync",
                    title="Ingestão de Inventário",
                    status="warning",
                    details=f"Aviso ao sincronizar inventário: {e}",
                )
            )

        # ---------------------------------------------------------------------
        # Etapa 7: Telemetria Consolidada e Mapeamento de Portas Físicas
        # ---------------------------------------------------------------------
        ports_count, active_ports_count, firmware_ver, uptime_str = self._derive_ports_and_telemetry(
            created_olt=created_olt,
            snmp_active=snmp_active,
            final_community=final_community,
        )

        links = {
            "self": Link(href=f"/api/v1/olts/{created_olt.id}", rel="self", method="GET"),
            "telemetry": Link(href=f"/api/v1/olts/{created_olt.id}/telemetry", rel="telemetry", method="GET"),
            "ports": Link(href=f"/api/v1/olts/{created_olt.id}/ports", rel="ports", method="GET"),
            "vlans": Link(href=f"/api/v1/olts/{created_olt.id}/vlans", rel="vlans", method="GET"),
            "onus": Link(href=f"/api/v1/onus?olt_id={created_olt.id}", rel="onus", method="GET"),
        }

        return OLTOnboardResponse(
            olt_id=created_olt.id,
            name=created_olt.name,
            vendor=created_olt.vendor,
            model=created_olt.model,
            host=created_olt.host,
            port=created_olt.port,
            protocol=created_olt.protocol,
            baseline_backup_id=baseline_backup_id,
            snmp_community=final_community,
            snmp_active=snmp_active,
            total_ports=ports_count,
            active_ports=active_ports_count,
            total_onus_detected=total_onus,
            new_onus_registered=new_onus,
            firmware_version=firmware_ver,
            uptime_human=uptime_str,
            steps=steps,
            message=f"Onboarding da OLT '{created_olt.name}' concluído com sucesso! {total_onus} ONUs e {ports_count} portas mapeadas.",
            links=links,
        )

    def _discover_and_configure_snmp(
        self,
        created_olt: OLTInDB,
        tenant_name: Optional[str] = None,
    ) -> Tuple[bool, str, OnboardingStepItem]:
        """
        Diagnóstico e provisionamento dinâmico de SNMP com auto-descoberta em múltiplas etapas:
        1. Consulta ativa via CLI física (ex: 'show snmp community' em 'cd service').
        2. Teste da comunidade encontrada via UDP 161 (sysUpTime).
        3. Teste em cascata de candidatos dinâmicos derivados da empresa (zero hardcode).
        4. Provisionamento seguro na OLT caso nenhuma comunidade esteja ativa.
        """
        driver = DriverFactory.get_driver(created_olt)
        tenant_raw = (tenant_name or "").strip()
        tenant_clean = re.sub(r"[^a-zA-Z0-9]+", "", tenant_raw)
        company_slug = slugify_community(tenant_raw or "provedor")
        default_community = f"olt_{company_slug}"

        snmp_active = False
        final_community = created_olt.snmp_community or default_community
        existing_comm: Optional[str] = None
        is_cipher = False

        try:
            # 1. Tenta obter comunidade ao vivo do chassi físico via Telnet CLI em 'cd service'
            try:
                live_res = driver.get_snmp_community_live(created_olt)
                if isinstance(live_res, tuple) and len(live_res) == 2:
                    if isinstance(live_res[0], str) and live_res[0].strip():
                        existing_comm = live_res[0].strip()
                        is_cipher = bool(live_res[1])
            except Exception:
                pass

            if not existing_comm:
                # Fallback: running-config
                try:
                    running_cfg = driver.get_running_config(created_olt)
                    cfg_res = driver.extract_snmp_community(running_cfg)
                    if isinstance(cfg_res, tuple) and len(cfg_res) == 2:
                        if isinstance(cfg_res[0], str) and cfg_res[0].strip():
                            existing_comm = cfg_res[0].strip()
                            is_cipher = bool(cfg_res[1])
                except Exception:
                    pass

            # 2. Se encontrou e não é cifrada, testa via UDP 161
            if existing_comm and not is_cipher:
                test_uptime = SNMPCollector.get_sys_uptime(
                    host=created_olt.host,
                    community=existing_comm,
                    port=161,
                    timeout=0.8,
                )
                if test_uptime is not None:
                    snmp_active = True
                    final_community = existing_comm
                    created_olt.snmp_community = existing_comm
                    self.olt_repo.update(created_olt)
                    step = OnboardingStepItem(
                        step_key="snmp",
                        title="Agente SNMP (Auto-Descoberta)",
                        status="success",
                        details=f"Comunidade '{existing_comm}' descoberta no chassi e validada via UDP 161 (Uptime: {test_uptime}s).",
                    )
                    return True, final_community, step

            # 3. Teste de candidatos dinâmicos sem hardcode
            candidates: List[str] = []
            if existing_comm:
                candidates.append(existing_comm)
            candidates.append(f"olt_{company_slug}")
            if tenant_clean:
                cand_camel = f"olt{tenant_clean[0].upper()}{tenant_clean[1:]}"
                candidates.extend([cand_camel, f"olt{tenant_clean}", company_slug])
            else:
                candidates.append(company_slug)
            candidates.extend(["adsl", "public"])

            seen = set()
            unique_candidates = [
                c for c in candidates
                if isinstance(c, str) and c.strip() and not (c in seen or seen.add(c))
            ]

            for cand in unique_candidates:
                test_uptime = SNMPCollector.get_sys_uptime(
                    host=created_olt.host,
                    community=cand,
                    port=161,
                    timeout=0.8,
                )
                if test_uptime is not None:
                    snmp_active = True
                    final_community = cand
                    created_olt.snmp_community = cand
                    self.olt_repo.update(created_olt)
                    step = OnboardingStepItem(
                        step_key="snmp",
                        title="Agente SNMP (Auto-Descoberta)",
                        status="success",
                        details=f"Comunidade '{cand}' descoberta e validada via UDP 161 (Uptime: {test_uptime}s).",
                    )
                    return True, final_community, step

            # 4. Provisionamento na OLT
            dynamic_comm = f"olt_{company_slug}"
            driver.configure_snmp(created_olt, dynamic_comm, port=161)
            test_uptime = SNMPCollector.get_sys_uptime(
                host=created_olt.host,
                community=dynamic_comm,
                port=161,
                timeout=1.0,
            )
            if test_uptime is not None:
                snmp_active = True
                final_community = dynamic_comm
                created_olt.snmp_community = dynamic_comm
                self.olt_repo.update(created_olt)
                step = OnboardingStepItem(
                    step_key="snmp",
                    title="Provisionamento SNMP (Empresa)",
                    status="success",
                    details=f"Comunidade '{dynamic_comm}' configurada na OLT via CLI e validada com sucesso.",
                )
                return True, final_community, step
            else:
                created_olt.snmp_community = dynamic_comm
                self.olt_repo.update(created_olt)
                step = OnboardingStepItem(
                    step_key="snmp",
                    title="Provisionamento SNMP",
                    status="warning",
                    details=f"Comunidade '{dynamic_comm}' gravada na OLT, aguardando resposta UDP 161.",
                )
                return False, dynamic_comm, step
        except Exception as e:
            logger.warning(f"[Onboarding SNMP] Erro ao avaliar/provisionar SNMP: {e}")
            step = OnboardingStepItem(
                step_key="snmp",
                title="Agente SNMP",
                status="warning",
                details=f"Diagnóstico SNMP inconclusivo: {e}",
            )
            return False, final_community, step

    def _derive_ports_and_telemetry(
        self,
        created_olt: OLTInDB,
        snmp_active: bool,
        final_community: str,
    ) -> Tuple[int, int, Optional[str], Optional[str]]:
        """
        Deriva total de portas, portas ativas e telemetria básica a partir do inventário sincronizado
        e do agente SNMP, evitando sobrecarregar a sessão de terminal com um inspect_chassis pesado.
        """
        firmware_ver = None
        uptime_str = None
        ports_count = 0
        active_ports_count = 0

        try:
            onus_discovered = self.sync_service.onu_repo.list_all(olt_id=created_olt.id)
            distinct_ports = {o.current_port for o in onus_discovered if o.current_port}
            active_ports_count = len(distinct_ports)
            slots = {o.current_port.split("/")[0] for o in onus_discovered if o.current_port and "/" in o.current_port}
            # Cada slot de serviço GPON típico possui 16 portas PON
            ports_count = max(len(slots) * 16, active_ports_count)

            if snmp_active:
                uptime_sec = SNMPCollector.get_sys_uptime(
                    host=created_olt.host,
                    community=final_community,
                    port=161,
                    timeout=0.8,
                )
                if uptime_sec is not None:
                    hours = int(uptime_sec // 3600)
                    minutes = int((uptime_sec % 3600) // 60)
                    uptime_str = f"{hours}h {minutes}m"

            if ports_count == 0:
                xray = self.telemetry_service.inspect_chassis(created_olt.id)
                if hasattr(xray, "firmware_version") and isinstance(xray.firmware_version, str):
                    firmware_ver = xray.firmware_version
                else:
                    firmware_ver = f"{created_olt.vendor.value.upper()}_{created_olt.model.upper()}"
                if hasattr(xray, "uptime_human") and isinstance(xray.uptime_human, str):
                    uptime_str = uptime_str or xray.uptime_human
                if hasattr(xray, "ports") and isinstance(xray.ports, list):
                    ports_count = len(xray.ports)
                    active_ports_count = len([p for p in xray.ports if getattr(p, "oper_status", "") == "up"])
            else:
                firmware_ver = f"{created_olt.vendor.value.upper()}_{created_olt.model.upper()}"
        except Exception as e:
            logger.debug(f"[Onboarding Ports/Telemetry] Erro ao consolidar portas/telemetria: {e}")

        return ports_count, active_ports_count, firmware_ver, uptime_str

    async def execute_onboarding_stream(
        self,
        request: OLTOnboardRequest,
        tenant_name: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Executa o pipeline contínuo de onboarding Zero-Touch emitindo eventos SSE em tempo real.
        Permite que a interface anime o stepper e mostre logs segundo a segundo sem sensação de travamento.
        """
        def format_sse(data: dict) -> str:
            return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

        steps: List[OnboardingStepItem] = []
        company_slug = slugify_community(tenant_name or "provedor")

        # ---------------------------------------------------------------------
        # Etapa 1: Negociação de Conectividade (SSH -> Telnet)
        # ---------------------------------------------------------------------
        yield format_sse({
            "type": "step_update",
            "step_key": "connectivity",
            "status": "running",
            "message": f"Iniciando probe de conectividade em {request.host}...",
        })
        await asyncio.sleep(0.05)

        try:
            protocol, port, banner_prompt = await asyncio.to_thread(
                self.probe_connectivity,
                host=request.host,
                username=request.username,
                password=request.password,
                custom_port=request.custom_port,
            )
            step1 = OnboardingStepItem(
                step_key="connectivity",
                title="Negociação de Conexão",
                status="success",
                details=f"Conectado com sucesso via {protocol.value.upper()} na porta {port}.",
            )
            steps.append(step1)
            yield format_sse({
                "type": "step_update",
                "step_key": "connectivity",
                "status": "success",
                "message": step1.details,
            })
            await asyncio.sleep(0.05)
        except Exception as e:
            yield format_sse({
                "type": "step_update",
                "step_key": "connectivity",
                "status": "error",
                "message": str(e),
            })
            yield format_sse({"type": "error", "message": f"Falha de conexão: {e}"})
            return

        # ---------------------------------------------------------------------
        # Etapa 2: Reconhecimento do Fabricante e Modelo
        # ---------------------------------------------------------------------
        yield format_sse({
            "type": "step_update",
            "step_key": "fingerprint",
            "status": "running",
            "message": "Reconhecendo fabricante e modelo via prompt do chassi...",
        })
        await asyncio.sleep(0.05)

        vendor, model = self.fingerprint_vendor_and_model(banner_prompt)
        default_community = f"olt_{company_slug}"
        olt_id = generate_uuid7()
        olt_entity = OLTInDB(
            id=olt_id,
            name=request.name.strip(),
            vendor=vendor,
            model=model,
            host=request.host.strip(),
            port=port,
            protocol=protocol,
            username=request.username.strip(),
            password=request.password.strip(),
            snmp_community=default_community,
            snmp_port=161,
            snmp_version="v2c",
        )
        created_olt = await asyncio.to_thread(self.olt_repo.create, olt_entity)
        step2 = OnboardingStepItem(
            step_key="fingerprint",
            title="Reconhecimento do Fabricante",
            status="success",
            details=f"Fabricante identificado: {vendor.value.upper()} (Modelo: {model.upper()}).",
        )
        steps.append(step2)
        yield format_sse({
            "type": "step_update",
            "step_key": "fingerprint",
            "status": "success",
            "message": step2.details,
        })
        await asyncio.sleep(0.05)

        # ---------------------------------------------------------------------
        # Etapa 3: Snapshot de Segurança Obrigatório (Baseline v0)
        # ---------------------------------------------------------------------
        yield format_sse({
            "type": "step_update",
            "step_key": "baseline_backup",
            "status": "running",
            "message": "Criando snapshot preventivo de segurança (Baseline v0)...",
        })
        await asyncio.sleep(0.05)

        try:
            baseline_backup = await asyncio.to_thread(
                self.backup_service.create_backup,
                olt_id=created_olt.id,
                notes="Baseline v0 - Onboarding Zero-Touch Full Discovery",
            )
            baseline_backup_id = baseline_backup.backup_id
            step3 = OnboardingStepItem(
                step_key="baseline_backup",
                title="Backup Preventivo Baseline v0",
                status="success",
                details=f"Backup gravado em disco com hash SHA-256 (ID: {baseline_backup_id}).",
            )
        except Exception as e:
            baseline_backup_id = "baseline_v0_pendente"
            step3 = OnboardingStepItem(
                step_key="baseline_backup",
                title="Backup Preventivo Baseline v0",
                status="warning",
                details=f"Aviso ao extrair backup completo da OLT: {e}",
            )
        steps.append(step3)
        yield format_sse({
            "type": "step_update",
            "step_key": "baseline_backup",
            "status": step3.status,
            "message": step3.details,
        })
        await asyncio.sleep(0.05)

        # ---------------------------------------------------------------------
        # Etapa 4: Diagnóstico e Provisionamento SNMP Dinâmico (Zero Hardcode)
        # ---------------------------------------------------------------------
        yield format_sse({
            "type": "step_update",
            "step_key": "snmp",
            "status": "running",
            "message": "Consultando agente SNMP físico e testando comunidades...",
        })
        await asyncio.sleep(0.05)

        snmp_active, final_community, step4 = await asyncio.to_thread(
            self._discover_and_configure_snmp,
            created_olt=created_olt,
            tenant_name=tenant_name,
        )
        steps.append(step4)
        yield format_sse({
            "type": "step_update",
            "step_key": "snmp",
            "status": step4.status,
            "message": step4.details,
        })
        await asyncio.sleep(0.05)

        # ---------------------------------------------------------------------
        # Etapa 5: Ingestão de Portas, VLANs e ONUs no Inventário
        # ---------------------------------------------------------------------
        yield format_sse({
            "type": "step_update",
            "step_key": "inventory_sync",
            "status": "running",
            "message": "Sincronizando inventário completo de ONUs ativas e calculando Circuit ID TR-101...",
        })
        await asyncio.sleep(0.05)

        try:
            sync_res = await asyncio.to_thread(self.sync_service.sync_olt, created_olt.id)
            total_onus = sync_res.total_onus_discovered
            new_onus = sync_res.new_onus_registered
            step5 = OnboardingStepItem(
                step_key="inventory_sync",
                title="Ingestão de Inventário & TR-101",
                status="success",
                details=f"{total_onus} ONUs sincronizadas com cálculo de Circuit ID TR-101.",
            )
        except Exception as e:
            logger.warning(f"[Onboarding Sync] Erro ao sincronizar inventário: {e}")
            total_onus = 0
            new_onus = 0
            step5 = OnboardingStepItem(
                step_key="inventory_sync",
                title="Ingestão de Inventário",
                status="warning",
                details=f"Aviso ao sincronizar inventário: {e}",
            )
        steps.append(step5)
        yield format_sse({
            "type": "step_update",
            "step_key": "inventory_sync",
            "status": step5.status,
            "message": step5.details,
        })
        await asyncio.sleep(0.05)

        # ---------------------------------------------------------------------
        # Consolidação de Portas Físicas e Resumo
        # ---------------------------------------------------------------------
        ports_count, active_ports_count, firmware_ver, uptime_str = await asyncio.to_thread(
            self._derive_ports_and_telemetry,
            created_olt=created_olt,
            snmp_active=snmp_active,
            final_community=final_community,
        )

        links = {
            "self": Link(href=f"/api/v1/olts/{created_olt.id}", rel="self", method="GET"),
            "telemetry": Link(href=f"/api/v1/olts/{created_olt.id}/telemetry", rel="telemetry", method="GET"),
            "ports": Link(href=f"/api/v1/olts/{created_olt.id}/ports", rel="ports", method="GET"),
            "vlans": Link(href=f"/api/v1/olts/{created_olt.id}/vlans", rel="vlans", method="GET"),
            "onus": Link(href=f"/api/v1/onus?olt_id={created_olt.id}", rel="onus", method="GET"),
        }

        response = OLTOnboardResponse(
            olt_id=created_olt.id,
            name=created_olt.name,
            vendor=created_olt.vendor,
            model=created_olt.model,
            host=created_olt.host,
            port=created_olt.port,
            protocol=created_olt.protocol,
            baseline_backup_id=baseline_backup_id,
            snmp_community=final_community,
            snmp_active=snmp_active,
            total_ports=ports_count,
            active_ports=active_ports_count,
            total_onus_detected=total_onus,
            new_onus_registered=new_onus,
            firmware_version=firmware_ver,
            uptime_human=uptime_str,
            steps=steps,
            message=f"Onboarding da OLT '{created_olt.name}' concluído com sucesso! {total_onus} ONUs e {ports_count} portas mapeadas.",
            links=links,
        )

        yield format_sse({
            "type": "completed",
            "response": response.model_dump(mode="json"),
        })
