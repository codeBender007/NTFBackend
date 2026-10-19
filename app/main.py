import time
import logging
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.LMS.router import router as lms_router, rbac_router
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
# Main LMS router includes hierarchy (plants, depts, machines, users) and RBAC routes
app.include_router(
    lms_router,
    prefix="/api/v1/lms"
)

# Backward-compatibility alias for legacy un-versioned /api/lms routes (hidden from Swagger to prevent duplication)
app.include_router(
    rbac_router,
    prefix="/api/lms",
    include_in_schema=False
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

    bearer_scheme_def = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "Enter your raw JWT token or 'Bearer <token>'. Authorizing here injects the token into all requests."
    }

    # Define single unified BearerAuth HTTP security scheme
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": bearer_scheme_def,
    }

    # Ensure all path operations with security requirements use single BearerAuth
    paths = openapi_schema.get("paths", {})
    for path, path_item in paths.items():
        for method, operation in path_item.items():
            if method.lower() in {"get", "post", "put", "patch", "delete"} and isinstance(operation, dict):
                op_sec = operation.get("security")
                if op_sec is not None:
                    # Clean out any old HTTPBearer references and ensure only BearerAuth is used
                    cleaned_sec = [s for s in op_sec if "HTTPBearer" not in s]
                    if not any("BearerAuth" in s for s in cleaned_sec):
                        cleaned_sec.append({"BearerAuth": []})
                    operation["security"] = cleaned_sec

    # Apply global security requirement to ensure single lock icon and dialog field
    openapi_schema["security"] = [{"BearerAuth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema


# Override default openapi generator
app.openapi = custom_openapi