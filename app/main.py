from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.api.plantsApi import router as plantsRouter
from app.api.departmentsApi import router as departmentsRouter
from app.api.subDepartmentsApi import router as subDepartmentsRouter
from app.api.linesApi import router as linesRouter
from app.api.machineApi import router as machineRouter

app = FastAPI(
    title="NTF Automobile LMS/CMS Portal",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS configuration frontend (React/Vite/Next) ke liye
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Production me specific frontend URL daal sakte hain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global error handler for database integrity constraints
@app.exception_handler(IntegrityError)
def integrity_exception_handler(request: Request, exc: IntegrityError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": "Database integrity constraint violation. Please verify that related parent entities exist and child constraints are satisfied.",
            "error": str(exc.orig) if hasattr(exc, "orig") else str(exc)
        }
    )

@app.exception_handler(SQLAlchemyError)
def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "A database error occurred.", "error": str(exc)}
    )

# Base health route
@app.get("/", tags=["Health"])
def healthCheck():
    return {"status": "online", "message": "NTF Backend API is running successfully"}

# Routers include karein with /api/v1 prefix
app.include_router(plantsRouter, prefix="/api/v1")
app.include_router(departmentsRouter, prefix="/api/v1")
app.include_router(subDepartmentsRouter, prefix="/api/v1")
app.include_router(linesRouter, prefix="/api/v1")
app.include_router(machineRouter, prefix="/api/v1")