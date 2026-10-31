from fastapi import APIRouter
from app.api.v1.endpoints import auth, customers, health, meta, profile, staff

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(meta.router, tags=["metadata"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(staff.router, prefix="/staff", tags=["staff"])
api_router.include_router(customers.router, prefix="/customers", tags=["customers"])
api_router.include_router(profile.router, prefix="/profile", tags=["profile"])
