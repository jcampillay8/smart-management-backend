import logging
import logging.config
import redis.asyncio as aioredis
import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
# 🛑 COMENTADO: Causa ImportError en Python 3.12 con uv
# from fastapi_limiter.fastapi_limiter import FastAPILimiter 
from fastapi_pagination import add_pagination
from sqladmin import Admin
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from src.config import LOGGING_CONFIG, settings
from src.database import engine, redis_pool
from src.routers import routers
from src.models import User 
from src.registration.router import account_router

# ==============================
# 🌐 Middleware for HTTPS redirect (Railway & proxies)
# ==============================
class ForceHTTPSRedirectMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # SI ESTAMOS EN DESARROLLO, NO REDIRIGIR A HTTPS
        if settings.ENVIRONMENT == "development":
            return await call_next(request)

        x_forwarded_proto = request.headers.get("x-forwarded-proto")
        if x_forwarded_proto == "https" and request.url.scheme == "http":
            request.scope["scheme"] = "https"
            request._url = request.url.replace(scheme="https")

        return await call_next(request)

# ==============================
# 🪵 Logging & Sentry
# ==============================
if settings.SENTRY_DSN and settings.ENVIRONMENT != "test":
    logging.config.dictConfig(LOGGING_CONFIG)
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        enable_tracing=True,
    )

logger = logging.getLogger(__name__)

# ==============================
# 🚀 FastAPI App Init
# ==============================
app = FastAPI(
    title="EasyManagement",
    description="Sistema de gestión de inventario, recetas y ventas",
    version="1.0.0"
)

# ==============================
# 🛡️ Trusted Hosts & Middlewares
# ==============================
if settings.ENVIRONMENT == "production":
    trusted_hosts = ["localhost", "127.0.0.1", "*"] # Modificar con tu dominio real luego
else:
    # Agregamos 0.0.0.0 y host.docker.internal por seguridad en Docker
    trusted_hosts = ["localhost", "127.0.0.1", "10.0.2.2", "0.0.0.0", "*.ngrok-free.app"]

app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts)
app.add_middleware(ForceHTTPSRedirectMiddleware)
app.add_middleware(
    SessionMiddleware, 
    secret_key=settings.SECRET_KEY,
    session_cookie="easy_mgmt_session"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================
# 🧭 Routers & Config
# ==============================
for router in routers:
    app.include_router(router)

add_pagination(app)

# ==============================
# ⏯️ Startup & Shutdown
# ==============================
@app.on_event("startup")
async def startup():
    logger.info(f"🚀 EasyManagement API arrancando en modo: {settings.ENVIRONMENT}")
    # Mantenemos la conexión a Redis para otras funciones (como caché)
    # pero saltamos la inicialización del Limiter por ahora.
    try:
        redis = aioredis.Redis(connection_pool=redis_pool)
        await redis.ping()
        logger.info("✅ Conexión a Redis exitosa")
        # await FastAPILimiter.init(redis) # 🛑 Saltamos esto temporalmente
    except Exception as e:
        logger.error(f"❌ Error conectando a Redis: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Cerrando aplicación...")