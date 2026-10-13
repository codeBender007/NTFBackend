"""
Dashboard Module Router Aggregator
Aggregates and registers all domain routes for the Dashboard service.
"""
from fastapi import APIRouter

router = APIRouter()

# Future sub-route modules will be mounted here as developed:
# from app.dashboard.routes.analyticsApi import router as analyticsRouter
# router.include_router(analyticsRouter, prefix="/analytics", tags=["Dashboard - Analytics"])
