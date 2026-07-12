from fastapi import APIRouter

from app.routers.account import router as account_router
from app.routers.conversations import router as conversations_router
from app.routers.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(account_router)
api_router.include_router(conversations_router)
