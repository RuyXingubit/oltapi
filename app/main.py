from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.deps import get_scanner_service
from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.rate_limit import limiter
from app.db.init_db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Validação de segurança de credenciais em produção
    is_prod = getattr(settings, "ENVIRONMENT", "development").lower() in ["production", "prod"]
    if is_prod:
        if settings.JWT_SECRET == "oltapi_jwt_secret_key_change_me_in_production":
            raise RuntimeError(
                "[CRITICAL SECURITY] Bloqueio de inicialização: JWT_SECRET padrão detectado em produção. "
                "Defina uma chave criptográfica forte no .env."
            )
        if settings.API_KEY == "oltapi_secret_default_key_change_me":
            raise RuntimeError(
                "[CRITICAL SECURITY] Bloqueio de inicialização: API_KEY padrão detectada em produção. "
                "Defina uma chave forte no .env."
            )

    # Executa migrações do banco relacional (Alembic), migra dados legados e cifra senhas em repouso
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

# Registro do Rate Limiter SlowAPI
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Middleware de Cabeçalhos de Segurança HTTP (Defesas OWASP)
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response

# Configuração de CORS com controle de credenciais seguro
raw_cors = getattr(settings, "CORS_ORIGINS", "*")
cors_origins = [o.strip() for o in raw_cors.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins if cors_origins else ["*"],
    allow_credentials=True if cors_origins != ["*"] else False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registro dos roteadores de API
app.include_router(api_v1_router, prefix=settings.API_V1_STR)

@app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
def root():
    """Endpoint raiz REST JSON operacional."""
    return {
        "message": "OLTAPI Backend Operational",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "online",
    }


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
