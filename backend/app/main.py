from contextlib import asynccontextmanager
import asyncio
import logging
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config.logging import configure_logging, get_logger, reset_request_id, set_request_id
from app.config.settings import get_settings
from app.database.session import init_db
from app.database.session import session_scope
from app.routers.health import router as health_router
from app.routers.auth import router as auth_router
from app.routers.mailboxes import router as mailbox_router
from app.routers.tags import router as tag_router
from app.routers.emails import router as email_router
from app.routers.settings import router as settings_router
from app.routers.dashboard import router as dashboard_router
from app.services.admin_service import ensure_bootstrap_admin
from app.routers.outbound import router as outbound_router
from app.workers.outbound_worker import OutboundWorker
from app.database.session import SessionLocal

settings = get_settings()
configure_logging(settings.log_dir)
app_logger = get_logger()
access_logger = get_logger("access")


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        init_db()
        db = session_scope()
        try:
            ensure_bootstrap_admin(db, settings)
        finally:
            db.close()
        app_logger.info("Service started environment=%s", settings.environment)
    except Exception:
        app_logger.critical("Service startup failed", exc_info=True)
        raise
    worker = OutboundWorker(SessionLocal, settings) if settings.outbound_worker_enabled else None
    if worker:
        worker.start()
    try:
        yield
    finally:
        if worker:
            await asyncio.to_thread(worker.stop)
        app_logger.info("Service stopped")


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)


class ImportBodyLimitMiddleware:
    """Bound multipart bytes before Starlette can spool an uploaded file."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("path") != "/api/mailboxes/import-usernames":
            return await self.app(scope, receive, send)
        chunks = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > 1024 * 1024 + 64 * 1024:
                app_logger.error("Username upload rejected code=file_too_large")
                response = JSONResponse(status_code=413, content={"detail": {
                    "code": "file_too_large", "message": "文件不能超过 1 MiB"
                }})
                return await response(scope, receive, send)
            chunks.append(message.get("body", b""))
            if not message.get("more_body", False):
                break
        body = b"".join(chunks)
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        return await self.app(scope, bounded_receive, send)


app.add_middleware(ImportBodyLimitMiddleware)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(mailbox_router)
app.include_router(tag_router)
app.include_router(email_router)
app.include_router(settings_router)
app.include_router(dashboard_router)
app.include_router(outbound_router)


@app.middleware("http")
async def access_log_middleware(request: Request, call_next):
    request_id = uuid4().hex
    context_token = set_request_id(request_id)
    started = perf_counter()
    response = None
    try:
        response = await call_next(request)
    except Exception as exc:
        access_logger.error(
            "request_failed method=%s path=%s client=%s type=%s",
            request.method,
            request.url.path,
            request.client.host if request.client else "-",
            type(exc).__name__,
        )
        raise
    finally:
        duration_ms = (perf_counter() - started) * 1000
        if response is not None:
            access_logger.info(
                "request method=%s path=%s status=%s duration_ms=%.2f client=%s",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
                request.client.host if request.client else "-",
            )
        reset_request_id(context_token)
    if response is None:
        raise RuntimeError("request completed without a response")
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    level = logging.ERROR if exc.status_code >= 500 else logging.WARNING
    app_logger.log(
        level,
        "HTTP exception method=%s path=%s status=%s",
        request.method,
        request.url.path,
        exc.status_code,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    app_logger.warning(
        "Request validation failed method=%s path=%s error_count=%s",
        request.method,
        request.url.path,
        len(exc.errors()),
    )
    return JSONResponse(status_code=422, content={"detail": "请求参数无效"})


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception):
    # Exception strings and SQLAlchemy tracebacks can include request secrets.
    app_logger.error("Unhandled application error type=%s", type(exc).__name__)
    return JSONResponse(status_code=500, content={"detail": "服务器内部错误，请稍后重试"})
