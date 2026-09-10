from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_v1_router
from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="API REST padronizada para provisionamento multi-fabricante de OLTs, coleta de configurações, gestão de backups e diagnóstico óptico.",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
)

# Configuração de CORS para permitir integração segura com frontends e ERPs web
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registro dos roteadores de API
app.include_router(api_v1_router, prefix=settings.API_V1_STR)


@app.get("/health", tags=["Healthcheck"])
def healthcheck():
    """Endpoint público de verificação de integridade da API."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
    }


@app.exception_handler(ValueError)
def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc), "code": "VALIDATION_ERROR"},
    )
