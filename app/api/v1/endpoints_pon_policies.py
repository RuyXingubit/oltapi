import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_olt_repo, get_pon_policy_repo, require_api_key
from app.drivers.factory import DriverFactory
from app.models.hateoas import Link
from app.models.pon_policy import (
    AutoProvisionTaskCreate,
    AutoProvisionTaskItem,
    PonPolicyCreateOrUpdate,
    PonPolicyItem,
    ProvisioningSchemaResponse,
)
from app.storage.olt_repository import OLTRepository
from app.storage.sql.pon_policy_repository import SQLPonPolicyRepository

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/olts/{olt_id}",
    tags=["Políticas de PON & Auto-Provisionamento"],
    dependencies=[Depends(require_api_key)],
)


@router.get("/provisioning-schema", response_model=ProvisioningSchemaResponse)
def get_olt_provisioning_schema(
    olt_id: str,
    olt_repo: OLTRepository = Depends(get_olt_repo),
):
    """
    Retorna a especificação dinâmica de parâmetros de provisionamento do concentrador,
    incluindo portas detectadas, campos aceitos e listas reais de VLANs e perfis configurados.
    """
    olt = olt_repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    try:
        driver = DriverFactory.get_driver(olt)
        schema_dict = driver.get_provisioning_schema(olt)
        schema_dict["links"] = {
            "self": Link(href=f"/api/v1/olts/{olt_id}/provisioning-schema", method="GET", description="Esquema dinâmico de provisionamento"),
            "olt": Link(href=f"/api/v1/olts/{olt_id}", method="GET", description="Dados da OLT"),
            "policies": Link(href=f"/api/v1/olts/{olt_id}/pon-policies", method="GET", description="Políticas das portas PON"),
            "tasks": Link(href=f"/api/v1/olts/{olt_id}/tasks/auto-provision", method="GET", description="Tasks de auto-provisionamento"),
        }
        return ProvisioningSchemaResponse(**schema_dict)
    except Exception as e:
        logger.error(f"Erro ao obter esquema de provisionamento da OLT {olt.name}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao obter esquema da OLT: {str(e)}")


@router.get("/pon-policies", response_model=List[PonPolicyItem])
def list_pon_policies(
    olt_id: str,
    olt_repo: OLTRepository = Depends(get_olt_repo),
    policy_repo: SQLPonPolicyRepository = Depends(get_pon_policy_repo),
):
    """Lista todas as configurações padrão das portas PON da OLT."""
    olt = olt_repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    policies = policy_repo.list_policies_by_olt(olt_id)
    for p in policies:
        p.links = {
            "self": Link(href=f"/api/v1/olts/{olt_id}/pon-policies/{p.port}", method="GET", description="Política da porta PON"),
            "update": Link(href=f"/api/v1/olts/{olt_id}/pon-policies/{p.port}", method="PUT", description="Atualizar política"),
            "olt": Link(href=f"/api/v1/olts/{olt_id}", method="GET", description="Dados da OLT"),
        }
    return policies


@router.get("/pon-policies/{port:path}", response_model=PonPolicyItem)
def get_pon_policy(
    olt_id: str,
    port: str,
    olt_repo: OLTRepository = Depends(get_olt_repo),
    policy_repo: SQLPonPolicyRepository = Depends(get_pon_policy_repo),
):
    """Obtém a política padrão de uma porta PON específica."""
    olt = olt_repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    policy = policy_repo.get_policy(olt_id, port)
    if not policy:
        # Tenta buscar do schema para gerar um default virtual caso não esteja gravado
        driver = DriverFactory.get_driver(olt)
        schema = driver.get_provisioning_schema(olt)
        def_vlan = schema.get("available_vlans", [{}])[0].get("id", 100) if schema.get("available_vlans") else 100
        policy = policy_repo.upsert_policy(
            olt_id,
            port,
            PonPolicyCreateOrUpdate(
                port=port,
                default_vlan=def_vlan,
                default_mode="transparent",
            ),
        )

    policy.links = {
        "self": Link(href=f"/api/v1/olts/{olt_id}/pon-policies/{port}", method="GET", description="Política da porta PON"),
        "update": Link(href=f"/api/v1/olts/{olt_id}/pon-policies/{port}", method="PUT", description="Atualizar política"),
        "olt": Link(href=f"/api/v1/olts/{olt_id}", method="GET", description="Dados da OLT"),
    }
    return policy


@router.put("/pon-policies/{port:path}", response_model=PonPolicyItem)
def update_pon_policy(
    olt_id: str,
    port: str,
    req: PonPolicyCreateOrUpdate,
    olt_repo: OLTRepository = Depends(get_olt_repo),
    policy_repo: SQLPonPolicyRepository = Depends(get_pon_policy_repo),
):
    """Cria ou atualiza a política padrão de uma porta PON específica."""
    olt = olt_repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    policy = policy_repo.upsert_policy(olt_id, port, req)
    policy.links = {
        "self": Link(href=f"/api/v1/olts/{olt_id}/pon-policies/{port}", method="GET", description="Política da porta PON"),
        "olt": Link(href=f"/api/v1/olts/{olt_id}", method="GET", description="Dados da OLT"),
    }
    return policy


@router.delete("/pon-policies/{port:path}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pon_policy(
    olt_id: str,
    port: str,
    olt_repo: OLTRepository = Depends(get_olt_repo),
    policy_repo: SQLPonPolicyRepository = Depends(get_pon_policy_repo),
):
    """Remove a política customizada de uma porta PON."""
    olt = olt_repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    deleted = policy_repo.delete_policy(olt_id, port)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Política da porta '{port}' não encontrada.")


@router.post("/tasks/auto-provision", response_model=AutoProvisionTaskItem, status_code=status.HTTP_201_CREATED)
def create_auto_provision_task(
    olt_id: str,
    req: AutoProvisionTaskCreate,
    olt_repo: OLTRepository = Depends(get_olt_repo),
    policy_repo: SQLPonPolicyRepository = Depends(get_pon_policy_repo),
):
    """
    Cria e inicializa uma janela temporizada de auto-provisionamento (Cutover Zero-Touch).
    Enquanto ativa, o worker do OLTAPI autoriza automaticamente as ONUs que surgirem naquela porta PON.
    """
    olt = olt_repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    # Se não foi informada a VLAN alvo, busca da política padrão da porta ou do schema
    target_vlan = req.target_vlan
    if not target_vlan:
        port_pol = policy_repo.get_policy(olt_id, req.pon_port)
        if port_pol:
            target_vlan = port_pol.default_vlan
        else:
            driver = DriverFactory.get_driver(olt)
            schema = driver.get_provisioning_schema(olt)
            target_vlan = schema.get("available_vlans", [{}])[0].get("id", 100) if schema.get("available_vlans") else 100

    task = policy_repo.create_task(olt_id, req, default_vlan=target_vlan)
    task.links = {
        "self": Link(href=f"/api/v1/olts/{olt_id}/tasks/auto-provision", method="GET", description="Listar tasks"),
        "cancel": Link(href=f"/api/v1/olts/{olt_id}/tasks/auto-provision/{task.id}/cancel", method="POST", description="Cancelar task"),
        "olt": Link(href=f"/api/v1/olts/{olt_id}", method="GET", description="Dados da OLT"),
    }
    return task


@router.get("/tasks/auto-provision", response_model=List[AutoProvisionTaskItem])
def list_auto_provision_tasks(
    olt_id: str,
    limit: int = 20,
    olt_repo: OLTRepository = Depends(get_olt_repo),
    policy_repo: SQLPonPolicyRepository = Depends(get_pon_policy_repo),
):
    """Lista as janelas de auto-provisionamento (ativas e finalizadas) da OLT."""
    olt = olt_repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    tasks = policy_repo.list_tasks(olt_id, limit=limit)
    for t in tasks:
        t.links = {
            "self": Link(href=f"/api/v1/olts/{olt_id}/tasks/auto-provision", method="GET", description="Listar tasks"),
            "cancel": Link(href=f"/api/v1/olts/{olt_id}/tasks/auto-provision/{t.id}/cancel", method="POST", description="Cancelar task"),
            "olt": Link(href=f"/api/v1/olts/{olt_id}", method="GET", description="Dados da OLT"),
        }
    return tasks


@router.post("/tasks/auto-provision/{task_id}/cancel", response_model=AutoProvisionTaskItem)
def cancel_auto_provision_task(
    olt_id: str,
    task_id: str,
    olt_repo: OLTRepository = Depends(get_olt_repo),
    policy_repo: SQLPonPolicyRepository = Depends(get_pon_policy_repo),
):
    """Interrompe imediatamente uma janela de auto-provisionamento ativa (Kill Switch)."""
    olt = olt_repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    task = policy_repo.cancel_task(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task '{task_id}' não encontrada.")

    task.links = {
        "self": Link(href=f"/api/v1/olts/{olt_id}/tasks/auto-provision", method="GET", description="Listar tasks"),
        "olt": Link(href=f"/api/v1/olts/{olt_id}", method="GET", description="Dados da OLT"),
    }
    return task
