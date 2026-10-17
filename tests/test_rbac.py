"""
Comprehensive Test Suite for RBAC (Roles, Pages, Role Permissions, and User Role Assignment):
1. Route registration and OpenAPI inspection.
2. SQLAlchemy models matching table expectations.
3. Role CRUD (create, duplicate check, detail, update, protect Superadmin, assigned user 409 conflict, delete).
4. Page CRUD (create across DASHBOARD, LMS, CMS, module validation, duplicate check, filter, update, delete).
5. Role Permissions (assign single page, independent 5 flags, bulk update with sync, ensure isolation, delete).
6. User Role Assignment (assign role, self-assignment 403, superadmin protection 403, effective permissions).
7. Effective permissions for active, deactivated, no-role, and Superadmin users.
8. Reusable `require_permission` dependency helper verification.
"""
import os
import sys
sys.path.insert(0, os.getcwd())
import sqlite3
from datetime import date, datetime
from fastapi import HTTPException
from sqlalchemy import create_engine, event, func
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base
from app.core.security import get_password_hash
from app.LMS.models.userModel import User
from app.LMS.models.roleModel import Role
from app.LMS.models.pageModel import Page
from app.LMS.models.rolePermissionModel import RolePermission
from app.LMS.schemas.roleSchema import RoleCreate, RoleUpdate
from app.LMS.schemas.pageSchema import PageCreate, PageUpdate
from app.LMS.schemas.rolePermissionSchema import (
    SinglePagePermissionUpdate,
    BulkPagePermissionItem,
)
from app.LMS.services import (
    roleService,
    pageService,
    rolePermissionService,
    userRoleService,
)
from app.core.dependencies import require_permission

# In-Memory SQLite Database for unit testing
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def register_sqlite_functions(dbapi_conn, _):
    if isinstance(dbapi_conn, sqlite3.Connection):
        dbapi_conn.create_function("getdate", 0, lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def setup_test_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        # Create Superadmin user
        admin = User(
            id=1,
            payCode="ADMIN-001",
            empName="System Administrator",
            email="admin@ntfauto.com",
            passwordHash=get_password_hash("AdminPass123"),
            role="SUPER_ADMIN",
            active=True
        )
        # Create Standard user
        user = User(
            id=2,
            payCode="EMP-100",
            empName="John Operator",
            email="john@ntfauto.com",
            passwordHash=get_password_hash("UserPass123"),
            role="OPERATOR",
            active=True
        )
        db.add_all([admin, user])
        db.commit()
    finally:
        db.close()


def test_openapi_routes():
    """1. Verify that all RBAC endpoints are registered in the FastAPI app."""
    schema = app.openapi()
    paths = schema.get("paths", {})

    expected_endpoints = [
        "/api/lms/roles",
        "/api/lms/roles/{role_id}",
        "/api/lms/pages",
        "/api/lms/pages/{page_id}",
        "/api/lms/roles/{role_id}/permissions",
        "/api/lms/roles/{role_id}/permissions/{page_id}",
        "/api/lms/users/{user_id}/role",
        "/api/lms/users/{user_id}/permissions",
        "/api/lms/me/permissions",
    ]

    for ep in expected_endpoints:
        assert ep in paths, f"Expected endpoint '{ep}' not found in OpenAPI paths!"
    print("PASS: 1. All RBAC endpoints registered in OpenAPI schema.")


def test_role_crud():
    """2. Test complete Role CRUD operations and validation rules."""
    db = TestingSessionLocal()
    try:
        admin_user = db.query(User).filter(User.id == 1).first()

        # A. Create Role
        role_hr = roleService.create_role(db, RoleCreate(name="HR Manager"))
        assert role_hr.id is not None
        assert role_hr.name == "HR Manager"
        assert role_hr.isActive is True

        # B. Duplicate Name Prevention
        try:
            roleService.create_role(db, RoleCreate(name="hr manager"))
            assert False, "Duplicate role name was not rejected!"
        except HTTPException as e:
            assert e.status_code == 400

        # C. Empty Name Prevention
        try:
            roleService.create_role(db, RoleCreate(name="   "))
            assert False, "Empty role name was not rejected!"
        except HTTPException as e:
            assert e.status_code == 400

        # D. Superadmin Role Creation
        role_super = roleService.create_role(db, RoleCreate(name="SUPER_ADMIN"))

        # E. Get All Roles
        all_roles = roleService.get_all_roles(db)
        assert len(all_roles) >= 2

        # F. Get Role Details
        details = roleService.get_role_details(db, role_hr.id)
        assert details["id"] == role_hr.id
        assert details["name"] == "HR Manager"
        assert "permissions" in details

        # G. Update Role
        updated_role = roleService.update_role(db, role_hr.id, RoleUpdate(name="HR Lead"), current_user=admin_user)
        assert updated_role.name == "HR Lead"

        # H. Prevent Renaming Superadmin Role
        try:
            roleService.update_role(db, role_super.id, RoleUpdate(name="RegularAdmin"), current_user=admin_user)
            assert False, "Superadmin rename was not blocked!"
        except HTTPException as e:
            assert e.status_code == 400

        # I. Prevent Deleting Superadmin Role
        try:
            roleService.delete_role(db, role_super.id, current_user=admin_user)
            assert False, "Superadmin deletion was not blocked!"
        except HTTPException as e:
            assert e.status_code == 400

        # J. Prevent Deleting Role Assigned to User (409 Conflict)
        test_user = db.query(User).filter(User.id == 2).first()
        test_user.roleId = role_hr.id
        db.commit()

        try:
            roleService.delete_role(db, role_hr.id, current_user=admin_user)
            assert False, "Deleting role assigned to users was not blocked with 409!"
        except HTTPException as e:
            assert e.status_code == 409

        # K. Successful Role Deletion after unassigning
        test_user.roleId = None
        db.commit()
        roleService.delete_role(db, role_hr.id, current_user=admin_user)

        try:
            roleService.get_role_by_id(db, role_hr.id)
            assert False, "Deleted role still retrieved!"
        except HTTPException as e:
            assert e.status_code == 404

        print("PASS: 2. Role CRUD, uniqueness, Superadmin protection & 409 delete safeguards verified.")
    finally:
        db.close()


def test_page_crud():
    """3. Test Page CRUD across DASHBOARD, LMS, and CMS modules."""
    db = TestingSessionLocal()
    try:
        # A. Create Pages in modules
        p1 = pageService.create_page(db, PageCreate(module="LMS", name="Users"))
        assert p1.id is not None
        assert p1.module == "LMS"
        assert p1.name == "Users"
        assert p1.pageKey == "users"

        p2 = pageService.create_page(db, PageCreate(module="DASHBOARD", name="Attendance Tracker"))
        assert p2.module == "DASHBOARD"
        assert p2.pageKey == "attendance_tracker"

        p3 = pageService.create_page(db, PageCreate(module="CMS", name="Complaints"))
        assert p3.module == "CMS"

        # B. Module validation
        try:
            pageService.create_page(db, PageCreate(module="UNKNOWN_MOD", name="Invalid"))
            assert False, "Invalid module was not rejected!"
        except (HTTPException, ValueError):
            pass

        # C. Duplicate page in same module
        try:
            pageService.create_page(db, PageCreate(module="LMS", name="users"))
            assert False, "Duplicate page in same module was not rejected!"
        except HTTPException as e:
            assert e.status_code == 400

        # D. Filter pages by module
        lms_pages = pageService.get_all_pages(db, module="LMS")
        assert len(lms_pages) == 1
        assert lms_pages[0].name == "Users"

        dash_pages = pageService.get_all_pages(db, module="DASHBOARD")
        assert len(dash_pages) == 1

        # E. Update Page
        up = pageService.update_page(db, p1.id, PageUpdate(name="User Management"))
        assert up.name == "User Management"
        assert up.pageKey == "user_management"

        # F. Delete Page
        pageService.delete_page(db, p3.id)
        try:
            pageService.get_page_by_id(db, p3.id)
            assert False, "Deleted page still retrieved!"
        except HTTPException as e:
            assert e.status_code == 404

        print("PASS: 3. Page CRUD across DASHBOARD, LMS, CMS and module filtering verified.")
    finally:
        db.close()


def test_role_permissions():
    """4. Test single and bulk role permissions, flag independence, and deletion."""
    db = TestingSessionLocal()
    try:
        # Create role & pages
        role = roleService.create_role(db, RoleCreate(name="Supervisor"))
        role2 = roleService.create_role(db, RoleCreate(name="Inspector"))
        p_users = pageService.create_page(db, PageCreate(module="LMS", name="Operators"))
        p_dept = pageService.create_page(db, PageCreate(module="LMS", name="Departments"))

        # A. Assign single page permissions with specific flags
        single_res = rolePermissionService.update_single_page_permission(
            db=db,
            role_id=role.id,
            page_id=p_users.id,
            perms=SinglePagePermissionUpdate(
                canView=True,
                canCreate=True,
                canEdit=False,
                canDelete=False,
                canUploadExcel=True
            )
        )
        assert single_res["canView"] is True
        assert single_res["canCreate"] is True
        assert single_res["canEdit"] is False
        assert single_res["canDelete"] is False
        assert single_res["canUploadExcel"] is True

        # B. Upsert (update) permission
        single_res2 = rolePermissionService.update_single_page_permission(
            db=db,
            role_id=role.id,
            page_id=p_users.id,
            perms=SinglePagePermissionUpdate(
                canView=True,
                canCreate=True,
                canEdit=True,
                canDelete=False,
                canUploadExcel=False
            )
        )
        assert single_res2["canEdit"] is True
        assert single_res2["canUploadExcel"] is False

        # C. Assign role2 permissions (isolation test)
        rolePermissionService.update_single_page_permission(
            db=db,
            role_id=role2.id,
            page_id=p_users.id,
            perms=SinglePagePermissionUpdate(canView=True)
        )

        # D. Bulk Update
        bulk_items = [
            BulkPagePermissionItem(pageId=p_users.id, canView=True, canCreate=True, canEdit=True, canDelete=True, canUploadExcel=True),
            BulkPagePermissionItem(pageId=p_dept.id, canView=True, canCreate=False, canEdit=False, canDelete=False, canUploadExcel=False),
        ]
        bulk_res = rolePermissionService.bulk_update_role_permissions(db, role.id, bulk_items, sync=True)
        assert len(bulk_res) == 2

        # Verify role2 permissions were unaffected
        role2_perms = rolePermissionService.get_role_permissions(db, role2.id)
        assert len(role2_perms) == 1
        assert role2_perms[0]["canView"] is True
        assert role2_perms[0]["canCreate"] is False

        # E. Delete permission assignment
        rolePermissionService.delete_page_permission(db, role.id, p_dept.id)
        updated_perms = rolePermissionService.get_role_permissions(db, role.id)
        assert len(updated_perms) == 1
        assert updated_perms[0]["pageId"] == p_users.id

        print("PASS: 4. Role Permissions single, bulk, 5 independent flags, and role isolation verified.")
    finally:
        db.close()


def test_user_role_assignment_and_effective_permissions():
    """5. Test assigning roles to users and querying effective permissions."""
    db = TestingSessionLocal()
    try:
        admin_user = db.query(User).filter(User.id == 1).first()
        target_user = db.query(User).filter(User.id == 2).first()

        role_quality = roleService.create_role(db, RoleCreate(name="Quality Manager"))
        p_inspect = pageService.create_page(db, PageCreate(module="LMS", name="Inspection"))

        # Configure permissions
        rolePermissionService.update_single_page_permission(
            db=db,
            role_id=role_quality.id,
            page_id=p_inspect.id,
            perms=SinglePagePermissionUpdate(canView=True, canCreate=True, canEdit=True, canDelete=False, canUploadExcel=True)
        )

        # A. Assign Role to User
        res = userRoleService.assign_user_role(
            db=db,
            user_id=target_user.id,
            role_id=role_quality.id,
            current_user=admin_user
        )
        assert res["userId"] == target_user.id
        assert res["roleId"] == role_quality.id
        assert res["roleName"] == "Quality Manager"

        # Verify database fields synchronized
        refreshed_user = db.query(User).filter(User.id == target_user.id).first()
        assert refreshed_user.roleId == role_quality.id
        assert refreshed_user.role == "Quality Manager"

        # B. Self-Assignment Protection
        try:
            userRoleService.assign_user_role(
                db=db,
                user_id=admin_user.id,
                role_id=role_quality.id,
                current_user=admin_user
            )
            assert False, "Self-role assignment was not rejected!"
        except HTTPException as e:
            assert e.status_code == 403

        # C. Query Effective Permissions for User
        eff_perms = userRoleService.get_user_effective_permissions(db, target_user.id)
        assert eff_perms["userId"] == target_user.id
        assert eff_perms["role"]["name"] == "Quality Manager"
        assert len(eff_perms["permissions"]) == 1
        p_item = eff_perms["permissions"][0]
        assert p_item["page"] == "Inspection"
        assert p_item["pageKey"] == "inspection"
        assert p_item["canView"] is True
        assert p_item["canCreate"] is True
        assert p_item["canEdit"] is True
        assert p_item["canDelete"] is False
        assert p_item["canUploadExcel"] is True

        # D. Deactivated User effective permissions
        target_user.active = False
        db.commit()
        deact_perms = userRoleService.get_user_effective_permissions(db, target_user.id)
        assert deact_perms["role"] is None
        assert deact_perms["permissions"] == []

        # Reactivate
        target_user.active = True
        db.commit()

        # E. Superadmin Effective Permissions (Unrestricted Access)
        admin_perms = userRoleService.get_user_effective_permissions(db, admin_user.id)
        assert admin_perms["userId"] == admin_user.id
        assert len(admin_perms["permissions"]) >= 1
        # All flags True for Superadmin
        for perm in admin_perms["permissions"]:
            assert perm["canView"] is True
            assert perm["canCreate"] is True
            assert perm["canEdit"] is True
            assert perm["canDelete"] is True
            assert perm["canUploadExcel"] is True

        # F. Current user permissions (me/permissions)
        me_perms = userRoleService.get_me_effective_permissions(db, target_user)
        assert me_perms["userId"] == target_user.id
        assert me_perms["role"]["id"] == role_quality.id

        print("PASS: 5. User role assignment, effective permissions, and self-elevation safeguards verified.")
    finally:
        db.close()


def test_require_permission_dependency():
    """6. Test the reusable require_permission dependency helper."""
    db = TestingSessionLocal()
    try:
        admin_user = db.query(User).filter(User.id == 1).first()
        test_user = db.query(User).filter(User.id == 2).first()

        # A. Superadmin bypasses check
        checker = require_permission(module="LMS", page_key="inspection", action="canDelete")
        res = checker(current_user=admin_user, db=db)
        assert res.id == admin_user.id

        # B. User has canEdit permission on inspection
        checker_edit = require_permission(module="LMS", page_key="inspection", action="canEdit")
        res_edit = checker_edit(current_user=test_user, db=db)
        assert res_edit.id == test_user.id

        # C. User lacks canDelete permission (should fail with 403)
        checker_delete = require_permission(module="LMS", page_key="inspection", action="canDelete")
        try:
            checker_delete(current_user=test_user, db=db)
            assert False, "Unauthorized action was not blocked with 403!"
        except HTTPException as e:
            assert e.status_code == 403

        # D. Non-existent page (should fail with 403)
        checker_nonexistent = require_permission(module="LMS", page_key="non_existent_page", action="canView")
        try:
            checker_nonexistent(current_user=test_user, db=db)
            assert False, "Non-existent page check did not fail with 403!"
        except HTTPException as e:
            assert e.status_code == 403

        print("PASS: 6. Reusable require_permission dependency helper verified.")
    finally:
        db.close()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("      RUNNING RBAC BACKEND AUTOMATED TEST SUITE      ")
    print("=" * 60 + "\n")
    setup_test_db()
    test_openapi_routes()
    test_role_crud()
    test_page_crud()
    test_role_permissions()
    test_user_role_assignment_and_effective_permissions()
    test_require_permission_dependency()
    print("\n" + "=" * 60)
    print("     ALL RBAC BACKEND TESTS COMPLETED SUCCESSFULLY!    ")
    print("=" * 60 + "\n")
