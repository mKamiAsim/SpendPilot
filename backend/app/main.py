from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.accounts.routes import router as cards_router
from app.agents.routes import defer_investigation_quietly
from app.agents.routes import router as agent_router
from app.administration.routes import router as admin_router
from app.analytics.routes import router as analytics_router
from app.api.deps import enforce_csrf
from app.api.records import router as records_router
from app.core.config import get_settings
from app.core.db import create_session_factory
from app.core.errors import ApiError
from app.identity.routes import router as auth_router
from app.ingestion.routes import defer_quietly
from app.ingestion.routes import router as imports_router
from app.ledger.routes import router as ledger_router

correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")
logger = logging.getLogger("spendpilot")


def _error_body(code: str, message: str, *, details: list | None = None) -> dict:
    body: dict = {
        "error": {
            "code": code,
            "message": message,
            "correlation_id": correlation_id.get(),
        }
    }
    if details:
        body["error"]["details"] = details
    return body


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    factory = create_session_factory(settings)
    app = FastAPI(title="SpendPilot", version="0.1.0")
    app.state.session_factory = factory

    if settings.allowed_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.allowed_origin_list,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Content-Type", "X-CSRF-Token", "X-Correlation-ID"],
        )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        incoming = request.headers.get("x-correlation-id")
        current = incoming if incoming and len(incoming) <= 80 else str(uuid.uuid4())
        token = correlation_id.set(current)
        request.state.correlation_id = current
        try:
            enforce_csrf(request, settings)
        except ApiError as exc:
            correlation_id.reset(token)
            response = JSONResponse(
                status_code=exc.status_code,
                content=_error_body(exc.code, exc.message),
            )
            response.headers["X-Correlation-ID"] = current
            return response
        async with factory() as session:
            request.state.db = session
            try:
                response = await call_next(request)
            except Exception:
                await session.rollback()
                logger.exception("request_failed", extra={"correlation_id": current})
                correlation_id.reset(token)
                failed = JSONResponse(
                    status_code=500,
                    content=_error_body("internal_error", "The request could not be completed."),
                )
                failed.headers["X-Correlation-ID"] = current
                return failed
            await session.commit()
            pending = getattr(request.state, "pending_imports", ())
            for document_id, owner_id in pending:
                defer_quietly(document_id, owner_id)
            pending_investigations = getattr(request.state, "pending_investigations", ())
            for investigation_id, owner_id in pending_investigations:
                defer_investigation_quietly(investigation_id, owner_id)
        response.headers["X-Correlation-ID"] = current
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        correlation_id.reset(token)
        return response

    @app.exception_handler(ApiError)
    async def api_error(_request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=_error_body(exc.code, exc.message))

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        details = []
        for item in exc.errors():
            details.append({"loc": [str(part) for part in item.get("loc", ())], "msg": item.get("msg", "")})
        return JSONResponse(
            status_code=422,
            content=_error_body("invalid_request", "Check the submitted fields.", details=details),
        )

    @app.get("/api/v1/health")
    async def health() -> dict:
        return {"status": "ok", "product": "SpendPilot"}

    @app.get("/api/v1/ready")
    async def ready(request: Request) -> dict:
        await request.state.db.execute(text("SELECT 1"))
        return {"status": "ready"}

    app.include_router(auth_router)
    app.include_router(records_router)
    app.include_router(admin_router)
    app.include_router(cards_router)
    app.include_router(imports_router)
    app.include_router(analytics_router)
    app.include_router(ledger_router)
    app.include_router(agent_router)
    return app


app = create_app()
