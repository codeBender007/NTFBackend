import time
import logging
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.LMS.router import router as lms_router
from app.dashboard.router import router as dashboard_router
from app.CMS.router import router as cms_router
from app.auth.router import router as auth_router
from app.core.middleware import AuthenticationMiddleware

# Initialize FastAPI Application
app = FastAPI(
    title="NTF Automobile LMS/CMS Portal",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure Application Logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("ntf_backend")

# 1. Centralized Authentication Middleware (Master & Setup routes protection)
app.add_middleware(AuthenticationMiddleware)

# 2. CORS Middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# 3. HTTP Request & Response Logging Middleware
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


# 4. Global Error Handlers
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


# 5. Base Health Check Route
@app.get("/", tags=["Health"])
def healthCheck():
    return {"status": "online", "message": "NTF Backend API is running successfully"}


# 6. Domain Router Mountings
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

# Authentication Endpoints: POST /api/auth/login and POST /api/auth/logout
app.include_router(
    auth_router,
    prefix="/api/auth",
    tags=["Auth"]
)


# 7. Global Swagger / OpenAPI Specification with BearerAuth Scheme & Lock Button
def custom_openapi():
    """
    Custom OpenAPI schema generator to enable Swagger UI's global 'Authorize' (lock icon) button
    and inject Bearer JWT authorization into OpenAPI 3.1 specifications.
    """
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description="NTF Automobile LMS/CMS Portal API Documentation with Bearer JWT Authentication",
        routes=app.routes,
    )

    if "components" not in openapi_schema:
        openapi_schema["components"] = {}

    # Define BearerAuth HTTP security scheme
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Enter your raw JWT token without the 'Bearer ' prefix. Swagger UI automatically prepends 'Bearer '."
        }
    }

    # Apply global security requirement to ensure lock icons appear across Swagger UI
    openapi_schema["security"] = [{"BearerAuth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema


# Override default openapi generator
app.openapi = custom_openapi