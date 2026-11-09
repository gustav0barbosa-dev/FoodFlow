import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import events, recommendations, restaurants, reviews
from app.cache.redis_client import close_redis
from app.core.config import settings
from app.ml.recommender import recommender

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    recommender.load()
    yield
    await close_redis()


app = FastAPI(
    title="FoodFlow API",
    description="Catálogo geoespacial e recomendação personalizada (LightGBM + Redis).",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(restaurants.router, prefix="/api/v1")
app.include_router(reviews.router, prefix="/api/v1")
app.include_router(events.router, prefix="/api/v1")
app.include_router(recommendations.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": app.version,
        "model_loaded": recommender.model is not None,
    }
