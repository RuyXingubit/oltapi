"""
Suíte Obrigatória de Conformidade de Drivers de OLT (BaseDriverComplianceTest).
Garante que todos os fabricantes registrados atendam integralmente ao contrato polimórfico,
possuam assinaturas canônicas, executem o padrão de backup FTP + fallback de terminal
e não inventem portas, dados ou valores fictícios.
"""

import inspect
from abc import ABC, abstractmethod
from typing import Type
from unittest.mock import MagicMock, patch
import pytest

from app.drivers.base import BaseOLTDriver
from app.drivers.fiberhome.fiberhome_tl1 import FiberhomeTL1Driver
from app.drivers.registry import DriverRegistry
from app.drivers.vsol.vsol_v1600 import VSOLV1600Driver
from app.models.bootstrap import BootstrapRequest
from app.models.olt import OLTInDB, OLTProtocol, OLTVendor
from app.models.provision import ONUActionResponse, ProvisionRequest, ProvisionResponse


class BaseDriverComplianceTest(ABC):
    """
    Classe base de conformidade para todos os drivers de OLT.
    Cada novo driver DEVE herdar desta classe e passar em 100% dos testes contratuais.
    """

    @property
    @abstractmethod
    def driver_class(self) -> Type[BaseOLTDriver]:
        """Classe do driver a ser testada."""
        pass

    @property
    @abstractmethod
    def vendor(self) -> OLTVendor:
        """Fabricante associado ao driver."""
        pass

    @pytest.fixture
    def driver_instance(self) -> BaseOLTDriver:
        try:
            return self.driver_class(model_name="TEST-MODEL")
        except TypeError:
            return self.driver_class()

    @pytest.fixture
    def sample_olt(self) -> OLTInDB:
        return OLTInDB(
            id="0191e4a0-0000-7000-8000-000000000001",
            name="OLT-COMPLIANCE-TEST",
            vendor=self.vendor,
            model="TEST-MODEL",
            host="192.168.10.1",
            port=22,
            protocol=OLTProtocol.SSH,
            username="admin",
            password="secret_password",
        )

    # 1. Contrato de Herança e Registro
    def test_driver_inherits_from_base_olt_driver(self):
        assert issubclass(self.driver_class, BaseOLTDriver), (
            f"O driver {self.driver_class.__name__} deve herdar obrigatoriamente de BaseOLTDriver."
        )

    def test_driver_is_registered_in_registry(self):
        registered_cls = DriverRegistry.get_driver_class(vendor=self.vendor, model="TEST-MODEL")
        assert registered_cls == self.driver_class, (
            f"O driver {self.driver_class.__name__} deve estar registrado no DriverRegistry para o vendor {self.vendor}."
        )

    # 2. Existência de Todos os Métodos Canônicos
    def test_all_canonical_methods_exist_and_callable(self, driver_instance):
        required_methods = [
            "get_running_config",
            "backup_config",
            "list_unauthorized_onus",
            "get_port_onus",
            "get_onu_details",
            "provision_onu",
            "deprovision_onu",
            "reboot_onu",
            "suspend_onu",
            "resume_onu",
            "generate_bootstrap_commands",
            "apply_bootstrap",
            "list_vlans",
            "create_vlan",
            "list_profiles",
            "list_all_authorized_onus",
            "save_running_config",
            "get_chassis_interfaces",
            "get_chassis_uptime",
            "extract_snmp_community",
            "configure_snmp",
            "inspect_management_arch",
            "execute_wizard_commissioning",
        ]
        for method_name in required_methods:
            assert hasattr(driver_instance, method_name), (
                f"Método contratual obrigatório ausente no driver {self.driver_class.__name__}: {method_name}"
            )
            assert callable(getattr(driver_instance, method_name)), (
                f"Atributo {method_name} no driver {self.driver_class.__name__} deve ser um método executável."
            )

    # 3. Assinatura de Métodos Críticos
    def test_backup_config_signature(self, driver_instance):
        sig = inspect.signature(driver_instance.backup_config)
        params = list(sig.parameters.keys())
        assert "olt" in params, f"Parâmetro 'olt' obrigatório em backup_config de {self.driver_class.__name__}."
        assert "ftp_servers" in params, f"Parâmetro 'ftp_servers' obrigatório em backup_config de {self.driver_class.__name__}."

    def test_onu_lifecycle_signatures(self, driver_instance):
        lifecycle_methods = ["deprovision_onu", "reboot_onu", "suspend_onu", "resume_onu"]
        for m_name in lifecycle_methods:
            sig = inspect.signature(getattr(driver_instance, m_name))
            params = list(sig.parameters.keys())
            assert "olt" in params, f"Parâmetro 'olt' ausente em {m_name}."
            assert "serial_or_id" in params, f"Parâmetro 'serial_or_id' ausente em {m_name}."

    # 4. Padrão de Backup: Fallback Automático para Terminal quando FTP ausente
    def test_backup_config_fallback_to_terminal_when_no_ftp(self, driver_instance, sample_olt):
        with patch.object(driver_instance, "get_running_config", return_value="! Running config de teste") as mock_rc:
            result = driver_instance.backup_config(sample_olt, ftp_servers=None)
            assert "! Running config de teste" in result
            mock_rc.assert_called_once_with(sample_olt)

    def test_backup_config_fallback_to_terminal_when_empty_ftp_list(self, driver_instance, sample_olt):
        with patch.object(driver_instance, "get_running_config", return_value="! Running config de teste") as mock_rc:
            result = driver_instance.backup_config(sample_olt, ftp_servers=[])
            assert "! Running config de teste" in result
            mock_rc.assert_called_once_with(sample_olt)

    # 5. Contrato de Interfaces do Chassi (Sem dados inventados)
    def test_get_chassis_interfaces_returns_list(self, driver_instance, sample_olt):
        with patch.object(driver_instance, "list_all_authorized_onus", return_value=[]):
            ports = driver_instance.get_chassis_interfaces(sample_olt)
            assert isinstance(ports, list), f"get_chassis_interfaces deve retornar list em {self.driver_class.__name__}."

    # 6. Contrato de Inspeção de Gerência (Zero hasattr)
    def test_inspect_management_arch_structure(self, driver_instance, sample_olt):
        arch = driver_instance.inspect_management_arch(sample_olt, "running-config content", "192.168.10.1")
        assert isinstance(arch, dict), f"inspect_management_arch deve retornar dict em {self.driver_class.__name__}."
        required_keys = ["existing_svis", "existing_vlans", "total_onus", "access_scenario", "prompt_message"]
        for k in required_keys:
            assert k in arch, f"Chave '{k}' obrigatória no resultado de inspect_management_arch de {self.driver_class.__name__}."

    # 7. Contrato de Comissionamento Wizard
    def test_execute_wizard_commissioning_returns_list(self, driver_instance, sample_olt):
        from app.models.olt import OLTWizardOnboardRequest
        req = OLTWizardOnboardRequest(
            name="TEST-OLT",
            vendor=self.vendor,
            model="TEST-MODEL",
            host="192.168.10.1",
            username="admin",
            password="secret_password",
            inband_vlan=100,
            ip_network="192.168.100.10/24",
            gateway="192.168.100.1",
            uplink_interface="ge 0/1",
        )
        with patch.object(driver_instance, "_execute_cli_commands", return_value="OK") if hasattr(driver_instance, "_execute_cli_commands") else patch("builtins.print"):
            res = driver_instance.execute_wizard_commissioning(sample_olt, req)
            assert isinstance(res, list), f"execute_wizard_commissioning deve retornar list de comandos em {self.driver_class.__name__}."

    # 8. Contrato SNMP
    def test_extract_snmp_community_contract(self, driver_instance):
        res = driver_instance.extract_snmp_community("! Config sem snmp")
        assert isinstance(res, tuple) and len(res) == 2, (
            f"extract_snmp_community deve retornar tupla (community, is_cipher) em {self.driver_class.__name__}."
        )


# =============================================================================
# Implementações Concretas da Suíte para Fabricantes Homologados
# =============================================================================

class TestFiberhomeCompliance(BaseDriverComplianceTest):
    @property
    def driver_class(self) -> Type[BaseOLTDriver]:
        return FiberhomeTL1Driver

    @property
    def vendor(self) -> OLTVendor:
        return OLTVendor.FIBERHOME

    def test_fiberhome_declares_primary_ftp_upload(self, driver_instance):
        assert driver_instance.handles_primary_ftp_upload is True, (
            "FiberhomeTL1Driver deve declarar handles_primary_ftp_upload = True."
        )


class TestVSOLCompliance(BaseDriverComplianceTest):
    @property
    def driver_class(self) -> Type[BaseOLTDriver]:
        return VSOLV1600Driver

    @property
    def vendor(self) -> OLTVendor:
        return OLTVendor.VSOL

    def test_vsol_backup_ftp_command_execution(self, driver_instance, sample_olt):
        mock_ftp = MagicMock()
        mock_ftp.host = "10.0.0.50"
        mock_ftp.port = 21
        mock_ftp.username = "backup_user"
        mock_ftp.password = "backup_pass"
        mock_ftp.base_path = "/backups"

        with patch.object(driver_instance, "_execute_cli_commands", return_value="Upload success") as mock_cli, \
             patch("app.services.ftp_service.FTPService.download_file", return_value="! VSOL Backup Content") as mock_dl:
            content = driver_instance.backup_config(sample_olt, ftp_servers=[mock_ftp])
            assert content == "! VSOL Backup Content"
            commands_sent = mock_cli.call_args[0][1]
            assert any("copy running-config ftp" in cmd for cmd in commands_sent)
            mock_dl.assert_called_once()
