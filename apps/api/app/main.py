from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.core.config import get_settings
from fastapi.exceptions import RequestValidationError

from app.core.errors import (
    AppError,
    app_error_handler,
    internal_error_handler,
    validation_error_handler,
)
from app.core.logging_config import configure_logging
from app.core.request_context import RequestIdMiddleware
from app.infrastructure.database.session import SessionLocal
from app.modules.identity.application.bootstrap import ensure_default_tenant
from app.modules.identity.interface.api import router as identity_router
from app.modules.park_property.interface.api import router as park_router
from app.modules.party.interface.api import router as party_router
from app.modules.lease.interface.api import router as lease_router
from app.modules.billing.interface.api import router as billing_router
from app.modules.collection.interface.api import router as collection_router
from app.modules.workbench.interface.api import router as workbench_router
from app.modules.investment.interface.api import router as investment_router
from app.modules.facility_ops.interface.api import router as facility_ops_router
from app.modules.platform_integrations.interface.api import router as integrations_router
from app.modules.workflow.interface.api import router as workflow_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Ensure step1 tables exist when using create_all fallback
    settings = get_settings()
    if settings.app_env in {"local", "test"}:  # normalized lowercase by Settings
        from app.infrastructure.database.session import create_all_tables

        create_all_tables()
        db = SessionLocal()
        try:
            ensure_default_tenant(db)
        finally:
            db.close()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.debug)
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="KWZY AI Smart Park API — Identity+Park+Unit+Party+Lease+Billing+Collection+Workbench+Investment",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, internal_error_handler)

    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIdMiddleware)

    prefix = settings.api_v1_prefix
    app.include_router(identity_router, prefix=prefix)
    app.include_router(park_router, prefix=prefix)
    app.include_router(party_router, prefix=prefix)
    app.include_router(lease_router, prefix=prefix)
    app.include_router(billing_router, prefix=prefix)
    app.include_router(collection_router, prefix=prefix)
    app.include_router(workbench_router, prefix=prefix)
    app.include_router(investment_router, prefix=prefix)
    app.include_router(facility_ops_router, prefix=prefix)
    app.include_router(integrations_router, prefix=prefix)
    app.include_router(workflow_router, prefix=prefix)

    @app.get("/health")
    def health() -> dict:
        return {"status": "up", "version": __version__, "env": settings.app_env}

    return app


app = create_app()
