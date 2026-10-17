"""
Centralized Authentication Middleware for NTF Backend.
Enforces JWT authentication on all administrative, master, setup, and mutation routes.
Attaches authenticated user context to request.scope['user'] and request.state.user.
"""
import logging
from typing import Set
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.security import decode_access_token

logger = logging.getLogger("ntf_backend.auth_middleware")

# Public exact routes that do not require authentication
PUBLIC_EXACT_PATHS: Set[str] = {
    "/",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/auth/login",
    "/api/auth/logout",
}

# Public path prefixes (documentation, static assets, etc.)
PUBLIC_PATH_PREFIXES = (
    "/docs",
    "/redoc",
    "/openapi.json",
)

# HTTP mutation methods requiring authentication across all master & setup resources
PROTECTED_METHODS: Set[str] = {"POST", "PUT", "PATCH", "DELETE"}


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    Centralized Authentication Middleware (authenticateToken / verifyJWT).
    - Checks for a valid JWT Bearer token in the Authorization header.
    - Rejects unauthorized mutation requests (POST, PUT, PATCH, DELETE) with 401.
    - Injects decoded token payload into request.scope['user'] and request.state.user.
    """

    async def dispatch(self, request: Request, call_next):
        # 1. Allow CORS preflight requests
        if request.method.upper() == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        method = request.method.upper()

        # 2. Extract Authorization header (Bearer <token>)
        auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
        token = None
        if auth_header:
            clean_header = auth_header.strip()
            while clean_header.lower().startswith("bearer "):
                clean_header = clean_header[7:].strip()
            token = clean_header.strip('"').strip("'").strip()

        decoded_token = None
        if token:
            decoded_token = decode_access_token(token)

        # 3. User Context Injection: Attach to request object for downstream controllers
        if decoded_token:
            request.scope["user"] = decoded_token
            request.state.user = decoded_token

        # 4. Check if route is public
        if path in PUBLIC_EXACT_PATHS or any(path.startswith(prefix) for prefix in PUBLIC_PATH_PREFIXES):
            return await call_next(request)

        # 5. Protect Master & Setup Routes (POST, PUT, PATCH, DELETE across all resources)
        # Includes Plants, Departments, Sub-departments, Lines, Machines, Users/Employees, etc.
        if method in PROTECTED_METHODS:
            if not token or not decoded_token:
                client_ip = request.client.host if request.client else "unknown"
                logger.warning(
                    f"Unauthorized access blocked: {method} {path} [client={client_ip}] - Missing or invalid token"
                )
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Access denied. Please log in first."},
                    headers={"WWW-Authenticate": "Bearer"}
                )

        return await call_next(request)
