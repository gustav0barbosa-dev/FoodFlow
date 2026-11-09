import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from lightgbm import LGBMClassifier
from app.cache.redis_client import get_scores, set_scores
from app.core.config import settings

MODEL_PATH = Path("models/recommender.joblib")


class Recommender:
    def __init__(self):
        self.model: LGBMClassifier | None = None
        self.feature_names: list[str] = []

    def load(self) -> bool:
        if MODEL_PATH.exists():
            self.model = joblib.load(MODEL_PATH)
            return True
        return False

    def save(self, model: LGBMClassifier, feature_names: list[str]):
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, MODEL_PATH)
        self.model = model
        self.feature_names = feature_names

    def predict_scores(self, user_features: dict, restaurant_ids: list[str]) -> dict[str, float]:
        if self.model is None:
            return {rid: 0.5 for rid in restaurant_ids}

        X = self._build_X(user_features, restaurant_ids)
        if X.empty:
            return {rid: 0.5 for rid in restaurant_ids}

        proba = self.model.predict_proba(X)[:, 1]
        return dict(zip(restaurant_ids, proba.tolist()))

    def _build_X(self, user_features: dict, restaurant_ids: list[str]) -> pd.DataFrame:
        rows = []
        for rid in restaurant_ids:
            row = {**user_features, "restaurant_id": rid}
            rows.append(row)
        return pd.DataFrame(rows)


recommender = Recommender()
