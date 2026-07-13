from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.db.session import dispose_engine
from app.routers import api_router
from app.services.conversation import get_conversation_service_singleton
from app.services.inference.coordinator import get_inference_coordinator

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    coordinator = get_inference_coordinator()
    coordinator.start()
    yield
    await coordinator.stop()
    await get_conversation_service_singleton().shutdown()
    await dispose_engine()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url=f"{settings.api_prefix}/docs",
    openapi_url=f"{settings.api_prefix}/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    return {"name": settings.app_name, "docs": f"{settings.api_prefix}/docs"}
