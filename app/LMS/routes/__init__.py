"""
LMS routes package.
"""
from app.LMS.routes.plantsApi import router as plantsRouter
from app.LMS.routes.departmentsApi import router as departmentsRouter
from app.LMS.routes.subDepartmentsApi import router as subDepartmentsRouter
from app.LMS.routes.linesApi import router as linesRouter
from app.LMS.routes.machineApi import router as machineRouter

__all__ = [
    "plantsRouter",
    "departmentsRouter",
    "subDepartmentsRouter",
    "linesRouter",
    "machineRouter",
]
