from fastapi import APIRouter

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

# Dedicated router for RBAC management endpoints
rbac_router = APIRouter()
rbac_router.include_router(roleRouter)
rbac_router.include_router(pageRouter)
rbac_router.include_router(rolePermissionRouter)
rbac_router.include_router(userRoleRouter)

# Main LMS Router combining all hierarchy, user, and RBAC routes
router = APIRouter()

# LMS Hierarchy & Resource Routers
router.include_router(plantsRouter)
router.include_router(departmentsRouter)
router.include_router(subDepartmentsRouter)
router.include_router(linesRouter)
router.include_router(machineRouter)
router.include_router(usersRouter)

# Mount RBAC under LMS router as well
router.include_router(rbac_router)