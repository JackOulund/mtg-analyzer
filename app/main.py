from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.routers import games


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting MTG Analyzer API...")
    yield
    print("Shutting down...")


app = FastAPI(
    title=settings.app_title,
    description=settings.app_description,
    version=settings.app_version,
    lifespan=lifespan,
)

app.include_router(games.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
