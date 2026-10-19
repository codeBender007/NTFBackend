import urllib.request
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def post_json(url, payload, headers=None):
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=hdrs, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"Error {e.code} on POST {url}: {e.read().decode('utf-8')}")
        raise

def put_json(url, payload, headers=None):
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=hdrs, method="PUT")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"Error {e.code} on PUT {url}: {e.read().decode('utf-8')}")
        raise

def get_json(url, headers=None):
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs, method="GET")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"Error {e.code} on GET {url}: {e.read().decode('utf-8')}")
        raise

print("==================================================")
print("   STEP-BY-STEP RBAC WORKFLOW VERIFICATION TEST   ")
print("==================================================")

# 0. Authenticate
print("\n[0] Authenticating as Superadmin...")
login_payload = {
    "email": "superadmin@ntfauto.com",
    "password": "SuperAdmin@NTF2026"
}
status, login_res = post_json(f"{BASE_URL}/api/auth/login", login_payload)
token = login_res["access_token"]
auth_headers = {"Authorization": f"Bearer {token}"}
print(f"  Superadmin authenticated successfully. (Status: {status})")

# a. Creating a Role
suffix = int(time.time()) % 10000
role_name = f"Test Auditor {suffix}"
print(f"\n[A] Creating Role: '{role_name}'...")
role_payload = {
    "name": role_name,
    "description": "Auditor role for inspecting compliance records"
}
status, new_role = post_json(f"{BASE_URL}/api/v1/lms/roles", role_payload, auth_headers)
role_id = new_role["id"]
print(f"  Role created successfully! ID: {role_id}, Name: {new_role['name']}")

# b. Creating a Page with proper pageKey
page_name = f"Compliance Logs {suffix}"
page_key = f"compliance_logs_{suffix}"
print(f"\n[B] Creating Page: '{page_name}' with pageKey='{page_key}'...")
page_payload = {
    "module": "LMS",
    "name": page_name,
    "pageKey": page_key,
    "isActive": True
}
status, new_page = post_json(f"{BASE_URL}/api/v1/lms/pages", page_payload, auth_headers)
page_id = new_page["id"]
print(f"  Page created successfully! ID: {page_id}, Module: {new_page['module']}, pageKey: {new_page['pageKey']}")

# c. Assigning Page Permissions to that Role
print(f"\n[C] Assigning Permissions on Page ID {page_id} to Role ID {role_id}...")
permissions_payload = [
    {
        "pageId": page_id,
        "canView": True,
        "canCreate": True,
        "canEdit": False,
        "canDelete": False,
        "canUploadExcel": True
    }
]
status, assigned_list = put_json(f"{BASE_URL}/api/v1/lms/roles/{role_id}/permissions", permissions_payload, auth_headers)
print(f"  Permissions assigned! Records updated: {len(assigned_list)}")

# d. Fetching Assigned Pages for that Role to verify assignment
print(f"\n[D] Verifying Assigned Pages:")

# Via Query Parameter:
status, query_pages = get_json(f"{BASE_URL}/api/v1/lms/pages/assigned?roleId={role_id}", auth_headers)
print(f"  [Query Parameter] GET /api/v1/lms/pages/assigned?roleId={role_id} -> Status: {status}, Count: {len(query_pages)}")
assert len(query_pages) == 1, "Expected 1 assigned page via query param"
q_page = query_pages[0]
print(f"    Returned fields: id={q_page['id']}, pageId={q_page['pageId']}, name='{q_page['name']}', pageKey='{q_page['pageKey']}', module='{q_page['module']}'")
print(f"    Permissions: canView={q_page['canView']}, canCreate={q_page['canCreate']}, canEdit={q_page['canEdit']}, canDelete={q_page['canDelete']}, canUploadExcel={q_page['canUploadExcel']}")

# Via Path Parameter (Roles router):
status, path_pages = get_json(f"{BASE_URL}/api/v1/lms/roles/{role_id}/pages", auth_headers)
print(f"  [Path Parameter]  GET /api/v1/lms/roles/{role_id}/pages -> Status: {status}, Count: {len(path_pages)}")
assert len(path_pages) == 1, "Expected 1 assigned page via path param"

# Via Path Parameter (Role Permissions router):
status, perm_pages = get_json(f"{BASE_URL}/api/v1/lms/roles/{role_id}/permissions", auth_headers)
print(f"  [Path Parameter]  GET /api/v1/lms/roles/{role_id}/permissions -> Status: {status}, Count: {len(perm_pages)}")
assert len(perm_pages) == 1, "Expected 1 assigned page via permissions param"

# Also check Role Details
status, role_detail = get_json(f"{BASE_URL}/api/v1/lms/roles/{role_id}", auth_headers)
print(f"  [Role Details]    GET /api/v1/lms/roles/{role_id} -> Status: {status}, Pages attached: {len(role_detail['pages'])}")

print("\n==================================================")
print("     ALL RBAC WORKFLOW VERIFICATIONS PASSED!      ")
print("==================================================")
