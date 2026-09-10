import pytest
from app.drivers.factory import DriverFactory
from app.drivers.intelbras.intelbras_8820 import Intelbras8820Driver
from app.models.olt import OLTInDB, OLTVendor, OLTProtocol


def test_parse_unauthorized_onus_format_standard():
    mock_cli_output = """
Onu uncfg list:
-------------------------------------------------------------
OnuIndex               Sn                     State
-------------------------------------------------------------
gpon-onu_1/1:1         INCL12345678           discovering
gpon-onu_1/2:3         INCL87654321           discovering
-------------------------------------------------------------
    """
    driver = Intelbras8820Driver()
    onus = driver.parse_unauthorized_onus(mock_cli_output)

    assert len(onus) == 2
    assert onus[0].port == "1/1"
    assert onus[0].serial == "INCL12345678"
    assert onus[1].port == "1/2"
    assert onus[1].serial == "INCL87654321"


def test_parse_unauthorized_onus_format_table():
    mock_cli_output = """
Port   SN             Model
1/3    HWTC55443322   110B
1/4    INCL99001122   auto
    """
    driver = Intelbras8820Driver()
    onus = driver.parse_unauthorized_onus(mock_cli_output)

    assert len(onus) == 2
    assert onus[0].port == "1/3"
    assert onus[0].serial == "HWTC55443322"
    assert onus[0].model == "110B"


def test_parse_port_onus():
    mock_cli_output = """
-------------------------------------------------------------
OnuIndex               AdminState  OperState    RxPower(dBm)
-------------------------------------------------------------
gpon-onu_1/1:1         enable      online       -19.45  INCL11112222
gpon-onu_1/1:2         enable      offline      --      INCL33334444
-------------------------------------------------------------
    """
    driver = Intelbras8820Driver()
    onus = driver.parse_port_onus(mock_cli_output, "1/1")

    assert len(onus) == 2
    assert onus[0].port == "1/1"
    assert onus[0].onu_id == 1
    assert onus[0].status == "online"
    assert onus[0].serial == "INCL11112222"

    assert onus[1].onu_id == 2
    assert onus[1].status == "offline"


def test_parse_optical_info():
    mock_cli_output = """
Optical Power Information:
  Rx optical power: -19.45 dBm
  Tx optical power: 2.10 dBm
  Temperature: 45.2 C
    """
    driver = Intelbras8820Driver()
    rx, tx = driver.parse_optical_info(mock_cli_output)

    assert rx == -19.45
    assert tx == 2.10


def test_driver_factory_resolution():
    olt_8820 = OLTInDB(
        name="OLT-8820",
        vendor=OLTVendor.INTELBRAS,
        model="8820 G",
        host="10.0.0.1",
        port=22,
        protocol=OLTProtocol.SSH,
        username="u",
        password="p",
    )
    driver = DriverFactory.get_driver(olt_8820)
    assert isinstance(driver, Intelbras8820Driver)

    olt_huawei = OLTInDB(
        name="OLT-HUAWEI",
        vendor=OLTVendor.HUAWEI,
        model="MA5800-X7",
        host="10.0.0.2",
        port=22,
        protocol=OLTProtocol.SSH,
        username="u",
        password="p",
    )
    with pytest.raises(NotImplementedError):
        DriverFactory.get_driver(olt_huawei)
