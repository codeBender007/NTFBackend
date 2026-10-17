"""
LMS routes package.
"""
from app.LMS.routes.plantsApi import router as plantsRouter
from app.LMS.routes.departmentsApi import router as departmentsRouter
from app.LMS.routes.subDepartmentsApi import router as subDepartmentsRouter
from app.LMS.routes.linesApi import router as linesRouter
from app.LMS.routes.machineApi import router as machineRouter
from app.LMS.routes.usersApi import router as usersRouter
from app.LMS.routes.roleRoutes import router as roleRouter
from app.LMS.routes.pageRoutes import router as pageRouter
from app.LMS.routes.rolePermissionRoutes import router as rolePermissionRouter
from app.LMS.routes.userRoleRoutes import router as userRoleRouter

__all__ = [
    "plantsRouter",
    "departmentsRouter",
    "subDepartmentsRouter",
    "linesRouter",
    "machineRouter",
    "usersRouter",
    "roleRouter",
    "pageRouter",
    "rolePermissionRouter",
    "userRoleRouter",
]
