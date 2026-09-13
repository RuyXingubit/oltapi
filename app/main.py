from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.deps import get_scanner_service
from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.db.init_db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Executa migrações do banco relacional (Alembic) e migra dados legados
    init_db()
    scanner = get_scanner_service()
    if settings.SCANNER_ENABLED_ON_STARTUP:
        scanner.start()
    yield
    await scanner.stop()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="API REST padronizada para provisionamento multi-fabricante de OLTs, coleta de configurações, gestão de backups e diagnóstico óptico.",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
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

# Montagem dos arquivos estáticos da Interface Web de Bancada
static_dir = settings.BASE_DIR / "app" / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", include_in_schema=False)
def serve_ui():
    """Serve a Interface Web de Bancada & First-Run Setup Wizard."""
    index_file = settings.BASE_DIR / "app" / "static" / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "OLTAPI Backend Operational", "version": settings.VERSION}


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
