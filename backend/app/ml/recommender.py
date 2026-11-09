"""Serving do recomendador LightGBM com cache de scores no Redis."""
import asyncio
import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from lightgbm import LGBMClassifier

from app.core.constants import Turno
from app.ml.features import build_candidate_features
from app.models import Restaurant

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "recommender.joblib"


def popularity_score(restaurant: Restaurant) -> float:
    """Fallback para cold start: nota ponderada pelo volume de avaliações."""
    rating = float(restaurant.average_rating or 0.0) / 5.0
    return rating * (1.0 + math.log1p(float(restaurant.review_count or 0)))


def popularity_scores(restaurants: list[Restaurant]) -> dict[str, float]:
    raw = {str(r.id): popularity_score(r) for r in restaurants}
    max_score = max(raw.values(), default=0.0)
    if max_score <= 0:
        return {restaurant_id: 0.0 for restaurant_id in raw}
    return {restaurant_id: value / max_score for restaurant_id, value in raw.items()}


def normalize_scores(scores: dict[str, float]) -> dict[str, float]:
    """Escala os scores do modelo para [0, 1] mantendo a ordem do ranking."""
    if not scores:
        return {}

    lowest = min(scores.values())
    highest = max(scores.values())
    if highest - lowest < 1e-9:
        return {restaurant_id: 0.5 for restaurant_id in scores}

    return {
        restaurant_id: round((score - lowest) / (highest - lowest), 6)
        for restaurant_id, score in scores.items()
    }


class Recommender:
    def __init__(self) -> None:
        self.model: LGBMClassifier | None = None
        self.feature_names: list[str] = []
        self.metadata: dict[str, Any] = {}

    def load(self) -> bool:
        if not MODEL_PATH.exists():
            logger.info("Modelo não encontrado em %s; usando fallback.", MODEL_PATH)
            return False

        try:
            bundle = joblib.load(MODEL_PATH)
        except Exception as exc:  # artefato inválido não deve derrubar a API
            logger.warning("Falha ao carregar o modelo (%s): %s", MODEL_PATH, exc)
            return False

        if isinstance(bundle, dict):
            model = bundle.get("model")
            if model is None:
                logger.warning("Artefato sem chave 'model'; fallback será usado.")
                return False
            self.model = model
            self.feature_names = list(bundle.get("feature_names", []))
            self.metadata = dict(bundle.get("metadata", {}))
        else:  # compatibilidade com o formato antigo (apenas o estimador)
            self.model = bundle
            self.feature_names = list(getattr(bundle, "feature_name_", []) or [])
            self.metadata = {}

        if not self.feature_names:
            self.feature_names = list(getattr(self.model, "feature_name_", []) or [])

        logger.info(
            "Modelo carregado de %s (%d features).",
            MODEL_PATH,
            len(self.feature_names),
        )
        return True

    def save(
        self,
        model: LGBMClassifier,
        feature_names: list[str],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        bundle = {
            "model": model,
            "feature_names": feature_names,
            "metadata": {
                "trained_at": datetime.now(timezone.utc).isoformat(),
                **(metadata or {}),
            },
        }
        joblib.dump(bundle, MODEL_PATH)
        self.model = model
        self.feature_names = feature_names
        self.metadata = bundle["metadata"]

    def predict_scores(
        self,
        user_features: dict[str, Any],
        restaurants: list[Restaurant],
        turno: Turno = "tarde",
    ) -> dict[str, float]:
        if self.model is None or not restaurants:
            return {str(restaurant.id): 0.5 for restaurant in restaurants}

        rows = [
            build_candidate_features(user_features, restaurant, turno)
            for restaurant in restaurants
        ]
        frame = pd.DataFrame(rows)

        if self.feature_names:
            frame = frame.reindex(columns=self.feature_names, fill_value=0.0)
        frame = frame.fillna(0.0).astype(float)

        probabilities = self.model.predict_proba(frame)[:, 1]
        raw_scores = {
            str(restaurant.id): float(score)
            for restaurant, score in zip(restaurants, probabilities, strict=True)
        }

        # Registra as features usadas em serving para monitoramento de drift
        # sem bloquear a predição (usa o event loop atual).
        try:
            from app.services.drift import drift_monitor  # evita import circular

            loop = asyncio.get_event_loop()
            for _, row in frame.iterrows():
                for feature in drift_monitor.feature_names:
                    if feature in row:
                        value = row[feature]
                        if pd.notna(value):
                            asyncio.run_coroutine_threadsafe(
                                drift_monitor.record_serving(feature, float(value)),
                                loop,
                            )
        except Exception as exc:  # drift não deve falhar a predição
            logger.warning("Falha ao registrar features de serving para drift: %s", exc)

        return normalize_scores(raw_scores)


recommender = Recommender()
