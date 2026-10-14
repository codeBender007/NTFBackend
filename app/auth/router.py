"""
Auth Module Router Aggregator
Aggregates and registers all authentication and authorization endpoints.
"""
from fastapi import APIRouter
from app.auth.routes.authApi import router as authApiRouter

router = APIRouter()
router.include_router(authApiRouter)
