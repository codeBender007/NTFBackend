# pyrefly: ignore [missing-import]
from fastapi import FastAPI
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware

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

# Base health route
@app.get("/", tags=["Health"])
def healthCheck():
    return {"status": "online", "message": "NTF Backend API is running successfully"}

# Routers include karein with /api/v1 prefix
app.include_router(departmentsRouter, prefix="/api/v1")
app.include_router(subDepartmentsRouter, prefix="/api/v1")
app.include_router(linesRouter, prefix="/api/v1")
app.include_router(machineRouter, prefix="/api/v1")