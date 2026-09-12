import os
import socket
from unittest.mock import MagicMock, patch
import pytest

from app.drivers.fiberhome.fiberhome_tl1 import FiberhomeTL1Driver
from app.drivers.fiberhome.telnet_client import TelnetClient
from app.models.ftp import FTPServerCreate
from app.models.olt import OLTCreateRequest, OLTInDB, OLTProtocol, OLTVendor
from app.services.ftp_service import FTPService

# Configurações com leitura de variáveis de ambiente e fallbacks genéricos de teste (RFC 5737 / RFC 2606)
TEST_FTP_HOST = os.getenv("TEST_FTP_HOST", "198.51.100.10")
TEST_FTP_USER = os.getenv("TEST_FTP_USER", "mock_ftp_user")
TEST_FTP_PASS = os.getenv("TEST_FTP_PASS", "mock_ftp_secret_pass_123")
TEST_OLT_HOST = os.getenv("TEST_OLT_HOST", "192.0.2.100")
TEST_OLT_USER = os.getenv("TEST_OLT_USER", "mock_tecnico")
TEST_OLT_PASS = os.getenv("TEST_OLT_PASS", "mock_olt_admin_pass_456")


def test_telnet_client_negotiation_and_read():
    """Testa tratamento defensivo de opções IAC Telnet e leitura até o prompt."""
    client = TelnetClient(host="127.0.0.1", port=23, timeout=2)
    mock_sock = MagicMock()

    # Simula resposta contendo IAC DO ECHO (0xFF, 0xFD, 0x01) seguido de "Login: "
    iac_bytes = bytes([0xFF, 0xFD, 0x01]) + b"Login: "
    mock_sock.recv.side_effect = [iac_bytes, b""]

    with patch("socket.socket", return_value=mock_sock):
        client.connect()
        output = client.read_until([b"Login:"])
        assert b"Login:" in output
        # Valida que respondeu IAC WONT ECHO (0xFF, 0xFC, 0x01)
        mock_sock.sendall.assert_any_call(bytes([0xFF, 0xFC, 0x01]))

        client.write(f"{TEST_OLT_USER}\r\n")
        mock_sock.sendall.assert_any_call(f"{TEST_OLT_USER}\r\n".encode("ascii"))

        client.close()
        mock_sock.close.assert_called_once()


def test_ftp_service_download_upload_delete():
    """Testa operações FTP de download, upload e limpeza com ftplib mockado."""
    mock_ftp_instance = MagicMock()
    mock_ftp_instance.getwelcome.return_value = "220 Ready"
    mock_ftp_instance.pwd.return_value = "/"

    # Mock retrbinary para preencher buffer
    def fake_retrbinary(cmd, callback):
        callback(b"Current running configuration content...")

    mock_ftp_instance.retrbinary.side_effect = fake_retrbinary

    with patch("ftplib.FTP", return_value=mock_ftp_instance):
        content = FTPService.download_file(
            host=TEST_FTP_HOST,
            port=21,
            username=TEST_FTP_USER,
            password=TEST_FTP_PASS,
            remote_filename="backup.cfg",
        )
        assert content == "Current running configuration content..."
        mock_ftp_instance.connect.assert_called_with(TEST_FTP_HOST, 21)
        mock_ftp_instance.login.assert_called_with(TEST_FTP_USER, TEST_FTP_PASS)

        # Test upload
        uploaded = FTPService.upload_file(
            host=TEST_FTP_HOST,
            port=21,
            username=TEST_FTP_USER,
            password=TEST_FTP_PASS,
            remote_filename="remote.cfg",
            content="test content",
        )
        assert uploaded is True
        mock_ftp_instance.storbinary.assert_called()

        # Test delete
        deleted = FTPService.delete_file(
            host=TEST_FTP_HOST,
            port=21,
            username=TEST_FTP_USER,
            password=TEST_FTP_PASS,
            remote_filename="remote.cfg",
        )
        assert deleted is True
        mock_ftp_instance.delete.assert_called_with("remote.cfg")


def test_fiberhome_backup_via_ftp_flow():
    """Valida que o driver Fiberhome executa o fluxo Telnet + upload ftp showrun quando há FTP."""
    driver = FiberhomeTL1Driver()
    olt = OLTInDB(
        id="01a096e7-f961-7b12-945d-276a073908f6",
        name="OLT VTX",
        vendor=OLTVendor.FIBERHOME,
        model="an5516",
        host=TEST_OLT_HOST,
        port=23,
        protocol=OLTProtocol.TELNET,
        username=TEST_OLT_USER,
        password=TEST_OLT_PASS,
    )

    mock_ftp = MagicMock()
    mock_ftp.host = TEST_FTP_HOST
    mock_ftp.port = 21
    mock_ftp.username = TEST_FTP_USER
    mock_ftp.password = TEST_FTP_PASS
    mock_ftp.base_path = "/"

    mock_telnet = MagicMock()
    # Simula as respostas do diálogo Telnet
    mock_telnet.read_until.side_effect = [
        b"Login: ",
        b"Password: ",
        b"OLTVTX> ",
        b"Password: ",
        b"OLTVTX# ",
        b"Finished. You've successfully upload config file.",
    ]

    with patch("app.drivers.fiberhome.fiberhome_tl1.TelnetClient", return_value=mock_telnet):
        with patch("app.drivers.fiberhome.fiberhome_tl1.FTPService.download_file", return_value="! OLT VTX Running Config"):
            with patch("app.drivers.fiberhome.fiberhome_tl1.FTPService.delete_file", return_value=True):
                content = driver.backup_config(olt, ftp_servers=[mock_ftp])
                assert content == "! OLT VTX Running Config"

                # Verifica se enviou o comando de upload
                mock_telnet.write.assert_any_call(f"{TEST_OLT_USER}\r\n")
                mock_telnet.write.assert_any_call(f"{TEST_OLT_PASS}\r\n")
                mock_telnet.write.assert_any_call("enable\r\n")
                # Verifica se chamou upload ftp showrun
                upload_cmds = [
                    call_arg[0][0]
                    for call_arg in mock_telnet.write.call_args_list
                    if "upload ftp showrun" in str(call_arg[0][0])
                ]
                assert len(upload_cmds) == 1
                assert TEST_FTP_HOST in upload_cmds[0]
                assert TEST_FTP_USER in upload_cmds[0]


def test_fiberhome_backup_without_ftp_falls_back_to_tl1():
    """Valida que na ausência de FTP, o driver faz fallback transparente para get_running_config."""
    driver = FiberhomeTL1Driver()
    olt = OLTInDB(
        id="01a096e7-f961-7b12-945d-276a073908f6",
        name="OLT VTX",
        vendor=OLTVendor.FIBERHOME,
        model="an5516",
        host=TEST_OLT_HOST,
        port=3337,
        protocol=OLTProtocol.TELNET,
        username=TEST_OLT_USER,
        password=TEST_OLT_PASS,
    )

    with patch.object(driver, "get_running_config", return_value="! TL1 Config"):
        content = driver.backup_config(olt, ftp_servers=[])
        assert content == "! TL1 Config"
