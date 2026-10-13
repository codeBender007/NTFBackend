"""
CMS (Content Management System) Module Router Aggregator
Aggregates and registers all domain routes for the CMS service.
"""
from fastapi import APIRouter

router = APIRouter()

# Future sub-route modules will be mounted here as developed:
# from app.CMS.routes.documentsApi import router as documentsRouter
# router.include_router(documentsRouter, prefix="/documents", tags=["CMS - Documents"])
