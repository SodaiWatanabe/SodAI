from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.db.session import dispose_engine
from app.routers import api_router
from app.services.inference.coordinator import create_generation_coordinator
from app.services.inference.pseudo_worker import create_pseudo_generation_worker

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    coordinator = create_generation_coordinator(settings)
    pseudo_worker = create_pseudo_generation_worker(settings)
    coordinator.start()
    pseudo_worker.start()
    try:
        yield
    finally:
        await pseudo_worker.stop()
        await coordinator.stop()
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
