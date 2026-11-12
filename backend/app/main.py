import logging
import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import (
    drift,
    events,
    experiment,
    interactions,
    metrics,
    ml,
    recommendations,
    restaurants,
    reviews,
    street_view,
    users,
)
from app.cache.redis_client import close_redis, ping_redis
from app.core.config import settings
from app.database import get_db
from app.ml.recommender import recommender
from app.ml.reranker import reranker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("foodflow.request")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # LightGBM é o modelo principal; ausência de artefato cai em popularidade.
    recommender.load()

    # LoRA é opcional e experimental. Não importamos torch/transformers/peft
    # no carregamento do módulo: `reranker.load()` só resolve essas
    # dependências quando explicitamente habilitado.
    if settings.enable_lora_reranker:
        loaded = reranker.load()
        logger.info(
            "LoRA re-ranker %s.",
            "carregado" if loaded else "indisponível (usando fallback)",
        )
    else:
        logger.info(
            "LoRA re-ranker desabilitado (ENABLE_LORA_RERANKER=false); "
            "usando fallback determinístico."
        )

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
app.include_router(users.router, prefix="/api/v1")
app.include_router(interactions.router, prefix="/api/v1")
app.include_router(recommendations.router, prefix="/api/v1")
app.include_router(drift.router, prefix="/api/v1")
app.include_router(experiment.router, prefix="/api/v1")
app.include_router(ml.router, prefix="/api/v1")
app.include_router(street_view.router, prefix="/api/v1")
app.include_router(metrics.router, prefix="/api/v1")


@app.middleware("http")
async def request_context(request: Request, call_next):
    """Propaga request id e mede a latência de cada requisição."""
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    request.state.request_id = request_id
    started = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.exception(
            "%s %s falhou após %.2f ms request_id=%s",
            request.method,
            request.url.path,
            elapsed_ms,
            request_id,
        )
        raise

    elapsed_ms = (time.perf_counter() - started) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{elapsed_ms:.2f}ms"
    logger.info(
        "%s %s -> %s em %.2f ms request_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
        request_id,
    )
    return response


@app.get("/ready")
async def ready(session: AsyncSession = Depends(get_db)):
    """Readiness: o banco é obrigatório; Redis e modelo são degradáveis."""
    try:
        await session.execute(text("SELECT 1"))
        database_ok = True
    except SQLAlchemyError:
        database_ok = False

    redis_ok = await ping_redis()
    payload = {
        "status": "ready" if database_ok else "degraded",
        "database": database_ok,
        "redis": redis_ok,
        "model_loaded": recommender.model is not None,
        "reranker_loaded": reranker.model is not None,
        "reranker_enabled": settings.enable_lora_reranker,
    }
    return JSONResponse(
        status_code=200 if database_ok else 503,
        content=payload,
    )


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": app.version,
        "model_loaded": recommender.model is not None,
        "reranker_loaded": reranker.model is not None,
    }
