from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.LMS.router import router as lms_router
from app.dashboard.router import router as dashboard_router
from app.CMS.router import router as cms_router

app = FastAPI(
    title="NTF Automobile LMS/CMS Portal",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

import time
import logging
from fastapi.exceptions import RequestValidationError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("ntf_backend")

# CORS configuration frontend (React/Vite/Next) & Swagger UI ke liye
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# HTTP Request & Response Logging Middleware
@app.middleware("http")
async def log_requests_middleware(request: Request, call_next):
    start_time = time.time()
    method = request.method
    path = request.url.path
    query = request.url.query
    query_str = f"?{query}" if query else ""
    client_ip = request.client.host if request.client else "unknown"

    logger.info(f"Incoming: {method} {path}{query_str} [client={client_ip}]")
    try:
        response = await call_next(request)
        duration = (time.time() - start_time) * 1000
        logger.info(f"Completed: {method} {path} -> Status {response.status_code} ({duration:.2f}ms)")
        return response
    except Exception as exc:
        duration = (time.time() - start_time) * 1000
        logger.error(f"Failed: {method} {path} -> {type(exc).__name__}: {str(exc)} ({duration:.2f}ms)", exc_info=True)
        raise exc

# Global error handler for database integrity constraints
@app.exception_handler(IntegrityError)
def integrity_exception_handler(request: Request, exc: IntegrityError):
    logger.warning(f"IntegrityError on {request.method} {request.url.path}: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": "Database integrity constraint violation. Please verify that related parent entities exist and child constraints are satisfied.",
            "error": str(exc.orig) if hasattr(exc, "orig") else str(exc)
        }
    )

@app.exception_handler(SQLAlchemyError)
def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    logger.error(f"SQLAlchemyError on {request.method} {request.url.path}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "A database error occurred.", "error": str(exc)}
    )

@app.exception_handler(RequestValidationError)
def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning(f"Validation error on {request.method} {request.url.path}: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Request parameter validation failed.",
            "errors": exc.errors()
        }
    )

@app.exception_handler(Exception)
def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled Server Error on {request.method} {request.url.path}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal server error occurred.",
            "error": str(exc),
            "type": type(exc).__name__
        }
    )

# Base health route
@app.get("/", tags=["Health"])
def healthCheck():
    return {"status": "online", "message": "NTF Backend API is running successfully"}

app.include_router(
    lms_router,
    prefix="/api/v1/lms"
)

app.include_router(
    dashboard_router,
    prefix="/api/v1/dashboard",
    tags=["Dashboard"]
)

app.include_router(
    cms_router,
    prefix="/api/v1/cms",
    tags=["CMS"]
)