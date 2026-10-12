from fastapi import APIRouter

from app.LMS.routes.plantsApi import router as plantsRouter
from app.LMS.routes.departmentsApi import router as departmentsRouter
from app.LMS.routes.subDepartmentsApi import router as subDepartmentsRouter
from app.LMS.routes.linesApi import router as linesRouter
from app.LMS.routes.machineApi import router as machineRouter

router = APIRouter()

router.include_router(plantsRouter)
router.include_router(departmentsRouter)
router.include_router(subDepartmentsRouter)
router.include_router(linesRouter)
router.include_router(machineRouter)
