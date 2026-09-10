from fastapi import APIRouter
from app.api.v1.endpoints_olts import router as olts_router
from app.api.v1.endpoints_diagnostics import router as diagnostics_router
from app.api.v1.endpoints_provision import router as provision_router

api_v1_router = APIRouter()
api_v1_router.include_router(olts_router)
api_v1_router.include_router(diagnostics_router)
api_v1_router.include_router(provision_router)
