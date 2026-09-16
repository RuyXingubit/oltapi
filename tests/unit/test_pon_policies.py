import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.models.onu import UnauthorizedONU
from app.models.provision import ProvisionResponse
from app.models.pon_policy import (
    AutoProvisionTaskCreate,
    PonPolicyCreateOrUpdate,
)
from app.services.autofind_scanner import AutofindScannerService


def test_provisioning_schema_endpoint(client: TestClient, auth_headers, sample_olt_8820):
    resp = client.get(
        f"/api/v1/olts/{sample_olt_8820.id}/provisioning-schema",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["olt_id"] == sample_olt_8820.id
    assert data["vendor"] == "VSOL"
    assert "ports" in data
    assert len(data["ports"]) > 0
    assert "fields" in data
    field_keys = [f["key"] for f in data["fields"]]
    assert "vlan" in field_keys
    assert "mode" in field_keys


def test_pon_policy_crud(client: TestClient, auth_headers, sample_olt_8820):
    # 1. Atualizar política para porta 0/1
    update_payload = {
        "port": "0/1",
        "default_vlan": 621,
        "default_mode": "transparent",
        "default_line_profile": "line_internet",
        "default_srv_profile": "srv_bridge",
        "vendor_parameters": {"custom_tag": "rural"},
        "auto_authorize_enabled": False,
    }
    resp = client.put(
        f"/api/v1/olts/{sample_olt_8820.id}/pon-policies/0/1",
        json=update_payload,
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["port"] == "0/1"
    assert data["default_vlan"] == 621
    assert data["default_line_profile"] == "line_internet"

    # 2. Consultar política da porta 0/1
    resp = client.get(
        f"/api/v1/olts/{sample_olt_8820.id}/pon-policies/0/1",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["default_vlan"] == 621

    # 3. Listar políticas da OLT
    resp = client.get(
        f"/api/v1/olts/{sample_olt_8820.id}/pon-policies",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    items = resp.json()
    assert any(p["port"] == "0/1" and p["default_vlan"] == 621 for p in items)

    # 4. Remover política
    resp = client.delete(
        f"/api/v1/olts/{sample_olt_8820.id}/pon-policies/0/1",
        headers=auth_headers,
    )
    assert resp.status_code == 204


def test_auto_provision_task_lifecycle(client: TestClient, auth_headers, sample_olt_8820):
    # 1. Iniciar task temporizada de cutover
    task_payload = {
        "pon_port": "0/2",
        "target_vlan": 300,
        "duration_minutes": 60,
        "default_mode": "transparent",
        "default_line_profile": "line_internet",
        "created_by": "Operador_NOC",
    }
    resp = client.post(
        f"/api/v1/olts/{sample_olt_8820.id}/tasks/auto-provision",
        json=task_payload,
        headers=auth_headers,
    )
    assert resp.status_code == 201
    task = resp.json()
    assert task["olt_id"] == sample_olt_8820.id
    assert task["pon_port"] == "0/2"
    assert task["target_vlan"] == 300
    assert task["status"] == "RUNNING"
    assert task["remaining_seconds"] > 3000
    task_id = task["id"]

    # 2. Listar tasks
    resp = client.get(
        f"/api/v1/olts/{sample_olt_8820.id}/tasks/auto-provision",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    tasks = resp.json()
    assert any(t["id"] == task_id for t in tasks)

    # 3. Cancelar task (Kill switch)
    resp = client.post(
        f"/api/v1/olts/{sample_olt_8820.id}/tasks/auto-provision/{task_id}/cancel",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_autofind_scanner_with_active_cutover_task(setup_test_env, sample_olt_8820):
    olt_repo = setup_test_env["repo"]
    policy_repo = setup_test_env["pon_policy_repo"]
    onu_repo = setup_test_env["onu_repo"]

    # Cria task ativa para a porta 0/3
    task = policy_repo.create_task(
        sample_olt_8820.id,
        AutoProvisionTaskCreate(
            pon_port="0/3",
            target_vlan=621,
            duration_minutes=30,
            default_line_profile="line_internet",
        ),
        default_vlan=621,
    )

    unauth_onu = UnauthorizedONU(
        port="0/3",
        serial="HWTC99887766",
        model="EG8041",
    )

    # Mock do driver
    mock_driver = MagicMock()
    mock_driver.list_unauthorized_onus.return_value = [unauth_onu]
    mock_driver.provision_onu.return_value = ProvisionResponse(
        success=True,
        port="0/3",
        onu_id=5,
        serial="HWTC99887766",
        message="Provisioned",
    )

    scanner = AutofindScannerService(
        olt_repo=olt_repo,
        onu_repo=onu_repo,
        reconciliation_service=MagicMock(),
        policy_repo=policy_repo,
    )

    with patch("app.drivers.factory.DriverFactory.get_driver", return_value=mock_driver):
        result = await scanner.run_scan_cycle()

    # Verifica se a ONU foi auto-provisionada
    assert result.reconciled_onus_count >= 1
    mock_driver.provision_onu.assert_called_once()
    call_args = mock_driver.provision_onu.call_args[0]
    prov_req = call_args[1]
    assert prov_req.vlan == 621
    assert prov_req.serial == "HWTC99887766"

    # Confirma que o contador da task incrementou
    updated_task = policy_repo.get_task(task.id)
    assert updated_task.provisioned_count == 1
