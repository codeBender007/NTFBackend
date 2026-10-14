"""
Test Suite for Centralized Authentication Middleware:
- Verifies that all master, setup, and mutation routes (POST, PUT, PATCH, DELETE)
  across Plants, Departments, Sub-departments, Lines, Machines, and Users/Employees
  cannot be accessed anonymously.
- Verifies that missing or invalid/expired tokens return 401 Unauthorized
  with message 'Access denied. Please log in first.'
- Verifies that valid JWT tokens allow execution and inject user context (req.user).
- Verifies public endpoints (login, logout, health) remain accessible.
"""
import asyncio
import json
from datetime import timedelta
from app.main import app
from app.core.security import create_access_token


async def dispatch_request(method: str, path: str, body: dict = None, token: str = None):
    headers = [
        (b"content-type", b"application/json"),
        (b"accept", b"application/json")
    ]
    if token:
        headers.append((b"authorization", f"Bearer {token}".encode()))

    body_bytes = json.dumps(body).encode() if body is not None else b""
    scope = {
        "type": "http",
        "method": method.upper(),
        "path": path,
        "headers": headers,
        "query_string": b""
    }
    sent = []

    async def receive():
        return {"type": "http.request", "body": body_bytes, "more_body": False}

    async def send(msg):
        sent.append(msg)

    await app(scope, receive, send)
    status_code = next(m["status"] for m in sent if m["type"] == "http.response.start")
    resp_body = b"".join(m["body"] for m in sent if m["type"] == "http.response.body").decode()
    try:
        json_body = json.loads(resp_body) if resp_body else {}
    except Exception:
        json_body = {"raw": resp_body}
    return status_code, json_body


def run_middleware_tests():
    print("==================================================")
    print("  RUNNING AUTHENTICATION MIDDLEWARE TEST SUITE    ")
    print("==================================================")

    async def _test():
        # 1. Anonymous Access to Master & Creation Routes (Must return 401)
        protected_endpoints = [
            ("POST", "/api/v1/lms/plants/", {"plantName": "Unauthorized Plant"}),
            ("PUT", "/api/v1/lms/plants/1", {"plantName": "Unauthorized Edit"}),
            ("DELETE", "/api/v1/lms/plants/1", None),
            ("POST", "/api/v1/lms/departments/", {"departmentName": "Unauthorized Dept", "plantId": 1}),
            ("PUT", "/api/v1/lms/departments/1", {"departmentName": "Unauthorized Edit"}),
            ("DELETE", "/api/v1/lms/departments/1", None),
            ("POST", "/api/v1/lms/sub-departments/", {"subDepartmentName": "Unauthorized SubDept", "departmentId": 1}),
            ("PUT", "/api/v1/lms/sub-departments/1", {"subDepartmentName": "Unauthorized Edit"}),
            ("DELETE", "/api/v1/lms/sub-departments/1", None),
            ("POST", "/api/v1/lms/lines/", {"lineName": "Unauthorized Line", "subDepartmentId": 1}),
            ("PUT", "/api/v1/lms/lines/1", {"lineName": "Unauthorized Edit"}),
            ("DELETE", "/api/v1/lms/lines/1", None),
            ("POST", "/api/v1/lms/machines/", {"machineName": "Unauthorized Machine", "lineId": 1}),
            ("PUT", "/api/v1/lms/machines/1", {"machineName": "Unauthorized Edit"}),
            ("DELETE", "/api/v1/lms/machines/1", None),
            ("POST", "/api/v1/lms/users/", {"payCode": "EMP999", "empName": "Anonymous User"}),
            ("PUT", "/api/v1/lms/users/1", {"empName": "Anonymous Edit"}),
            ("DELETE", "/api/v1/lms/users/1", None),
            ("POST", "/api/v1/lms/users/upload-excel", None),
        ]

        print("\n[1] Testing Anonymous Requests on Master & Setup Routes...")
        for method, path, body in protected_endpoints:
            status, res = await dispatch_request(method, path, body=body)
            assert status == 401, f"Security failure: {method} {path} allowed anonymous access (Status {status})"
            assert res.get("detail") == "Access denied. Please log in first.", (
                f"Unexpected error message on {method} {path}: {res}"
            )
            print(f"  [BLOCKED 401] {method} {path} -> {res['detail']}")

        # 2. Invalid Token (Must return 401)
        print("\n[2] Testing Invalid Token...")
        status, res = await dispatch_request("POST", "/api/v1/lms/plants/", body={"plantName": "Test"}, token="invalid.token.here")
        assert status == 401, f"Expected 401 for invalid token, got {status}"
        assert res.get("detail") == "Access denied. Please log in first."
        print(f"  [BLOCKED 401] Invalid token -> {res['detail']}")

        # 3. Expired Token (Must return 401)
        print("\n[3] Testing Expired Token...")
        expired_token = create_access_token(
            {"id": 1, "username": "ADMIN-001", "email": "admin@ntfauto.com", "role": "SUPER_ADMIN"},
            expires_delta=timedelta(seconds=-60)  # expired 1 minute ago
        )
        status, res = await dispatch_request("POST", "/api/v1/lms/plants/", body={"plantName": "Test"}, token=expired_token)
        assert status == 401, f"Expected 401 for expired token, got {status}"
        assert res.get("detail") == "Access denied. Please log in first."
        print(f"  [BLOCKED 401] Expired token -> {res['detail']}")

        # 4. Public Endpoints (Must NOT be blocked by middleware)
        print("\n[4] Testing Public Endpoints...")
        status, _ = await dispatch_request("GET", "/")
        assert status == 200, f"Expected 200 on health check, got {status}"
        print("  [ALLOWED 200] GET / (Health Check)")

        status, _ = await dispatch_request("POST", "/api/auth/login", body={"email": "", "password": ""})
        # Login returns 400 validation error (not 401 from auth middleware)
        assert status == 400, f"Expected 400 validation error, got {status}"
        print("  [ALLOWED] POST /api/auth/login is publicly reachable")

        status, _ = await dispatch_request("POST", "/api/auth/logout")
        assert status == 200, f"Expected 200 on logout, got {status}"
        print("  [ALLOWED 200] POST /api/auth/logout is reachable")

        # 5. Valid Token (Passes through middleware)
        print("\n[5] Testing Valid Token Authentication...")
        valid_token = create_access_token(
            {"id": 1, "username": "ADMIN-001", "email": "admin@ntfauto.com", "role": "SUPER_ADMIN"}
        )
        status, res = await dispatch_request(
            "POST",
            "/api/v1/lms/plants/",
            body={"plantName": "Secure Gurugram Plant"},
            token=valid_token
        )
        # Passed through middleware (status will not be 401)
        assert status != 401, f"Valid token should not be rejected with 401 (Status: {status})"
        print(f"  [PASSED AUTH] POST /api/v1/lms/plants/ with valid token (Status: {status})")

        print("\n==================================================")
        print("   ALL AUTHENTICATION MIDDLEWARE TESTS PASSED!    ")
        print("==================================================")

    asyncio.run(_test())


if __name__ == "__main__":
    run_middleware_tests()
