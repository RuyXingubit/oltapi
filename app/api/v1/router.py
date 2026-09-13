from fastapi import APIRouter
from app.api.v1.endpoints_olts import router as olts_router
from app.api.v1.endpoints_backups import router as backups_router
from app.api.v1.endpoints_diagnostics import router as diagnostics_router
from app.api.v1.endpoints_provision import router as provision_router
from app.api.v1.endpoints_bootstrap import router as bootstrap_router
from app.api.v1.endpoints_onu_inventory import router as onu_inventory_router
from app.api.v1.endpoints_webhooks import router as webhooks_router
from app.api.v1.endpoints_scanner import router as scanner_router
from app.api.v1.endpoints_vlans import router as vlans_router
from app.api.v1.endpoints_ftp import router as ftp_router
from app.api.v1.endpoints_auth import router as auth_router
from app.api.v1.endpoints_tenants import router as tenants_router
from app.api.v1.endpoints_users import router as users_router
from app.api.v1.endpoints_api_keys import router as api_keys_router
from app.api.v1.endpoints_setup import router as setup_router

api_v1_router = APIRouter()
api_v1_router.include_router(setup_router, prefix="/setup", tags=["Setup Inicial"])
api_v1_router.include_router(auth_router)
api_v1_router.include_router(tenants_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(api_keys_router)
api_v1_router.include_router(olts_router)
api_v1_router.include_router(backups_router)
api_v1_router.include_router(diagnostics_router)
api_v1_router.include_router(provision_router)
api_v1_router.include_router(bootstrap_router)
api_v1_router.include_router(onu_inventory_router)
api_v1_router.include_router(webhooks_router)
api_v1_router.include_router(scanner_router)
api_v1_router.include_router(vlans_router)
api_v1_router.include_router(ftp_router)


