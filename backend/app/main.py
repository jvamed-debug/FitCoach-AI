from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import time

from app.config import settings
from app.services.scheduler import start_scheduler, stop_scheduler

# ── Sentry (initialise before app creation) ───────────────────────────────────
if settings.sentry_dsn:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
        traces_sample_rate=settings.sentry_traces_sample_rate,
        environment=settings.app_env,
        send_default_pii=False,
    )
    logger.info("Sentry initialised (env=%s, traces=%.0f%%)", settings.app_env, settings.sentry_traces_sample_rate * 100)

logging.basicConfig(
    level=logging.DEBUG if settings.app_env == "development" else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="FitCoach AI API",
    description="API de coaching esportivo com IA para ciclismo e musculação",
    version="1.0.0",
    docs_url="/docs" if settings.app_env == "development" else None,
    redoc_url="/redoc" if settings.app_env == "development" else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = (time.monotonic() - start) * 1000
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Request-Duration-Ms"] = f"{duration_ms:.1f}"
    return response


# ── Routers (imported lazily so missing stubs don't block startup) ──────────
try:
    from app.routers import auth as auth_router
    app.include_router(auth_router.router, prefix="/api/auth", tags=["auth"])
except ImportError:
    logger.warning("auth router not yet available")

try:
    from app.routers import athletes as athletes_router
    app.include_router(athletes_router.router, prefix="/api/athletes", tags=["athletes"])
except ImportError:
    logger.warning("athletes router not yet available")

try:
    from app.routers import admin_athletes as admin_athletes_router
    app.include_router(admin_athletes_router.router, prefix="/api/admin/athletes", tags=["admin"])
except ImportError:
    logger.warning("admin_athletes router not yet available")

try:
    from app.routers import workouts as workouts_router
    app.include_router(workouts_router.router, prefix="/api/workouts", tags=["workouts"])
except ImportError:
    logger.warning("workouts router not yet available")

try:
    from app.routers import strength as strength_router
    app.include_router(strength_router.router, prefix="/api/strength", tags=["strength"])
except ImportError:
    logger.warning("strength router not yet available")

try:
    from app.routers import metrics as metrics_router
    app.include_router(metrics_router.router, prefix="/api/metrics", tags=["metrics"])
except ImportError:
    logger.warning("metrics router not yet available")

try:
    from app.routers import recommendations as rec_router
    app.include_router(rec_router.router, prefix="/api/recommendations", tags=["recommendations"])
except ImportError:
    logger.warning("recommendations router not yet available")

try:
    from app.routers import webhooks as webhooks_router
    app.include_router(webhooks_router.router, prefix="/api/webhooks", tags=["webhooks"])
except ImportError:
    logger.warning("webhooks router not yet available")

try:
    from app.routers import lgpd as lgpd_router
    app.include_router(lgpd_router.router, prefix="/api/lgpd", tags=["lgpd"])
except ImportError:
    logger.warning("lgpd router not yet available")

try:
    from app.routers import oauth as oauth_router
    app.include_router(oauth_router.router, prefix="/api/auth/oauth", tags=["oauth"])
except ImportError:
    logger.warning("oauth router not yet available")

try:
    from app.routers import admin_alerts as admin_alerts_router
    app.include_router(admin_alerts_router.router, prefix="/api/admin/alerts", tags=["admin-alerts"])
except ImportError:
    logger.warning("admin_alerts router not yet available")

try:
    from app.routers import push_notifications as push_router
    app.include_router(push_router.router, prefix="/api/push", tags=["push"])
except ImportError:
    logger.warning("push_notifications router not yet available")

try:
    from app.routers import reports as reports_router
    app.include_router(reports_router.athlete_router, prefix="/api/reports", tags=["reports"])
    app.include_router(reports_router.admin_router, prefix="/api/admin", tags=["admin-reports"])
except ImportError:
    logger.warning("reports router not yet available")

try:
    from app.routers import billing as billing_router
    app.include_router(billing_router.router, prefix="/api/billing", tags=["billing"])
except ImportError:
    logger.warning("billing router not yet available")


@app.get("/health", tags=["infra"])
async def health_check():
    return {"status": "ok", "env": settings.app_env, "version": "1.0.0"}


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(status_code=404, content={"detail": "Rota não encontrada"})


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "Erro interno do servidor"})
