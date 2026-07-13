from fastapi import APIRouter

from app.routers.account import router as account_router
from app.routers.health import router as health_router
from app.routers.realtime import router as realtime_router
from app.routers.threads import router as threads_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(account_router)
api_router.include_router(threads_router)
api_router.include_router(realtime_router)
