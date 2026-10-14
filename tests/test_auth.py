"""
Comprehensive test suite for Employee Authentication (Auth Module):
- OpenAPI route deduplication verification: EXACTLY TWO endpoints:
    1. POST /api/auth/login
    2. POST /api/auth/logout
- Credential validation (email, username / payCode, password)
- Active status verification (is_active = 1, deactivated accounts -> 403)
- Bulk Excel import default DOB password logic (DDMMYYYY, YYYY-MM-DD, DD-MM-YYYY, DD/MM/YYYY, DD.MM.YYYY)
- Custom password verification with bcrypt
- Signed JWT token generation and payload verification (id, username, email, role)
- Proper HTTP status codes (200, 400, 401, 403)
- Logout endpoint verification (POST /api/auth/logout)
"""
import sqlite3
from datetime import date, datetime
from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base
from app.core.security import get_password_hash, decode_access_token
from app.LMS.models.userModel import User
from app.auth.schemas.authSchema import LoginRequest, LogoutResponse
from app.auth.routes.authApi import login, logout
from app.auth.services import authService

# In-Memory SQLite Database for unit and integration testing
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def register_sqlite_functions(dbapi_conn, _):
    if isinstance(dbapi_conn, sqlite3.Connection):
        dbapi_conn.create_function("getdate", 0, lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def setup_database():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        # Clear any existing rows
        db.query(User).delete()

        # 1. Standard Super Admin User
        admin_user = User(
            payCode="ADMIN-001",
            empName="System Super Administrator",
            dob=date(1990, 1, 1),
            email="superadmin@ntfauto.com",
            passwordHash=get_password_hash("SuperAdmin@NTF"),
            role="SUPER_ADMIN",
            active=True
        )

        # 2. Bulk Excel Imported Employee (DOB: 15-August-1995, default password hashed as DDMMYYYY: '15081995')
        # This mirrors app.LMS.services.userService._dob_password
        bulk_employee = User(
            payCode="EMP-1001",
            empName="Ramesh Kumar",
            dob=date(1995, 8, 15),
            email="ramesh.kumar@ntfauto.com",
            passwordHash=get_password_hash("15081995"),
            role="OPERATOR",
            active=True
        )

        # 3. Deactivated Employee (active = False / is_active = 0)
        inactive_employee = User(
            payCode="EMP-9999",
            empName="Deactivated User",
            dob=date(1988, 5, 20),
            email="inactive@ntfauto.com",
            passwordHash=get_password_hash("20051988"),
            role="OPERATOR",
            active=False
        )

        # 4. Supervisor with Custom Password who also has DOB
        custom_pwd_employee = User(
            payCode="EMP-2002",
            empName="Sunita Sharma",
            dob=date(1992, 12, 10),
            email="sunita@ntfauto.com",
            passwordHash=get_password_hash("CustomP@ssw0rd!"),
            role="SUPERVISOR",
            active=True
        )

        db.add_all([admin_user, bulk_employee, inactive_employee, custom_pwd_employee])
        db.commit()
    finally:
        db.close()


def run_auth_tests():
    print("==================================================")
    print("    RUNNING COMPREHENSIVE AUTH TEST SUITE         ")
    print("==================================================")

    # 1. Verify OpenAPI Route Registration & Deduplication
    print("\n[1] Checking OpenAPI Route Deduplication...")
    openapi_schema = app.openapi()
    paths = openapi_schema["paths"]

    auth_paths = [p for p in paths.keys() if "auth" in p]
    print(f"  Discovered auth endpoints in OpenAPI schema: {auth_paths}")

    # Ensure only two clean endpoints exist: POST /api/auth/login and POST /api/auth/logout
    expected_auth_endpoints = ["/api/auth/login", "/api/auth/logout"]
    assert sorted(auth_paths) == sorted(expected_auth_endpoints), (
        f"Route deduplication error: Expected exactly {expected_auth_endpoints}, but found {auth_paths}"
    )

    for ep in expected_auth_endpoints:
        methods = list(paths[ep].keys())
        assert methods == ["post"], f"Endpoint {ep} should only have POST method, got {methods}"
        print(f"  [OK] Clean endpoint verified: POST {ep}")

    print("  [OK] No duplicate, redundant, or deprecated auth endpoints found!")

    # 2. Initialize in-memory DB
    setup_database()
    db = TestingSessionLocal()
    print("\n[2] Test in-memory database initialized with test users.")

    try:
        # 3. Test Missing Input Fields (400 Bad Request / 422 Validation Error)
        print("\n[3] Testing Missing Input Fields...")
        # Empty credentials
        try:
            authService.authenticate_employee(db, LoginRequest(email="", password=""))
            assert False, "Should have failed with 400"
        except HTTPException as e:
            assert e.status_code == 400
            assert "required" in e.detail.lower()
            print("  [OK] Empty request rejected with 400 Bad Request.")

        # Missing password
        try:
            authService.authenticate_employee(db, LoginRequest(email="superadmin@ntfauto.com", password=""))
            assert False, "Should have failed with 400"
        except HTTPException as e:
            assert e.status_code == 400
            print("  [OK] Missing password rejected with 400 Bad Request.")

        # Missing email
        try:
            authService.authenticate_employee(db, LoginRequest(email="", password="password123"))
            assert False, "Should have failed with 400"
        except HTTPException as e:
            assert e.status_code == 400
            print("  [OK] Missing email rejected with 400 Bad Request.")

        # 4. Test Invalid Credentials (401 Unauthorized)
        print("\n[4] Testing Invalid Credentials (401 Unauthorized)...")
        try:
            authService.authenticate_employee(db, LoginRequest(email="nonexistent@ntfauto.com", password="SomePassword"))
            assert False, "Should have failed with 401"
        except HTTPException as e:
            assert e.status_code == 401
            assert e.detail == "Invalid credentials"
            print("  [OK] Non-existent email rejected with 401 Unauthorized.")

        try:
            authService.authenticate_employee(db, LoginRequest(email="superadmin@ntfauto.com", password="WrongPassword@123"))
            assert False, "Should have failed with 401"
        except HTTPException as e:
            assert e.status_code == 401
            assert e.detail == "Invalid credentials"
            print("  [OK] Incorrect password rejected with 401 Unauthorized.")

        # 5. Test Deactivated Account (403 Forbidden)
        print("\n[5] Testing Deactivated Account (403 Forbidden)...")
        try:
            authService.authenticate_employee(db, LoginRequest(email="inactive@ntfauto.com", password="20051988"))
            assert False, "Should have failed with 403"
        except HTTPException as e:
            assert e.status_code == 403
            assert "deactivated" in e.detail.lower()
            print("  [OK] Deactivated account rejected with 403 Forbidden.")

        # 6. Test Successful Login with Email & Custom Password
        print("\n[6] Testing Successful Login with Email & Password...")
        resp = login(LoginRequest(email="superadmin@ntfauto.com", password="SuperAdmin@NTF"), db)
        assert resp.access_token is not None
        assert resp.token_type == "bearer"
        assert resp.user.email == "superadmin@ntfauto.com"
        assert resp.user.role == "SUPER_ADMIN"
        assert resp.user.payCode == "ADMIN-001"

        # Verify decoded JWT payload requirements: id, username, email, role
        payload = decode_access_token(resp.access_token)
        assert payload is not None
        assert payload["id"] == resp.user.id
        assert payload["email"] == "superadmin@ntfauto.com"
        assert payload["role"] == "SUPER_ADMIN"
        assert payload["username"] == "ADMIN-001"
        print(f"  [OK] Super Admin authenticated successfully! JWT claims verified: {payload}")

        # 7. Test Bulk Excel Imported Employee Default Password Logic (DOB Parsing & Matching)
        print("\n[7] Testing Bulk Excel Import DOB Default Password Matching...")
        # Employee DOB is 15-August-1995, passwordHash was generated as '15081995'

        # (A) Standard DDMMYYYY ('15081995')
        resp_dob1 = login(LoginRequest(email="ramesh.kumar@ntfauto.com", password="15081995"), db)
        assert resp_dob1.user.payCode == "EMP-1001"
        assert resp_dob1.user.role == "OPERATOR"
        print("  [OK] DOB matching format: DDMMYYYY ('15081995')")

        # (B) ISO format YYYY-MM-DD ('1995-08-15')
        resp_dob2 = login(LoginRequest(email="ramesh.kumar@ntfauto.com", password="1995-08-15"), db)
        assert resp_dob2.user.payCode == "EMP-1001"
        print("  [OK] DOB matching format: YYYY-MM-DD ('1995-08-15')")

        # (C) Indian/European format DD-MM-YYYY ('15-08-1995')
        resp_dob3 = login(LoginRequest(email="ramesh.kumar@ntfauto.com", password="15-08-1995"), db)
        assert resp_dob3.user.payCode == "EMP-1001"
        print("  [OK] DOB matching format: DD-MM-YYYY ('15-08-1995')")

        # (D) Slash format DD/MM/YYYY ('15/08/1995')
        resp_dob4 = login(LoginRequest(email="ramesh.kumar@ntfauto.com", password="15/08/1995"), db)
        assert resp_dob4.user.payCode == "EMP-1001"
        print("  [OK] DOB matching format: DD/MM/YYYY ('15/08/1995')")

        # (E) Dot format DD.MM.YYYY ('15.08.1995')
        resp_dob5 = login(LoginRequest(email="ramesh.kumar@ntfauto.com", password="15.08.1995"), db)
        assert resp_dob5.user.payCode == "EMP-1001"
        print("  [OK] DOB matching format: DD.MM.YYYY ('15.08.1995')")

        # (F) Verification that custom password user cannot login with old DOB
        try:
            authService.authenticate_employee(db, LoginRequest(email="sunita@ntfauto.com", password="1992-12-10"))
            assert False, "Should have rejected DOB for user with custom password"
        except HTTPException as e:
            assert e.status_code == 401
            print("  [OK] Security confirmed: Customized password user cannot use old DOB.")

        # Custom password user succeeds with custom password
        resp_custom = login(LoginRequest(email="sunita@ntfauto.com", password="CustomP@ssw0rd!"), db)
        assert resp_custom.user.payCode == "EMP-2002"
        assert resp_custom.user.role == "SUPERVISOR"
        print("  [OK] Custom password user successfully authenticated.")

        # 9. Test Logout Endpoint (POST /api/auth/logout)
        print("\n[9] Testing Logout Endpoint (POST /api/auth/logout)...")
        logout_resp = logout()
        assert isinstance(logout_resp, LogoutResponse)
        assert logout_resp.status == "success"
        assert logout_resp.message == "Successfully logged out"
        print(f"  [OK] Logout endpoint verified: status='{logout_resp.status}', message='{logout_resp.message}'")

        print("\n==================================================")
        print("      ALL AUTHENTICATION TESTS PASSED (100%)       ")
        print("==================================================")

    finally:
        db.close()


if __name__ == "__main__":
    run_auth_tests()
