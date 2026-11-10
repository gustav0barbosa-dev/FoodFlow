import contextlib

import pytest

from app.core.constants import Turno
from app.ml.reranker import (
    LoRAReranker,
    normalize_scores,
    reranker,
)
from app.models import Restaurant


def _make_restaurant(
    restaurant_id: str,
    name: str = "Restaurante Teste",
    category: str = "Brasileira",
    rating: float = 4.5,
    review_count: int = 100,
    delivery_fee: float = 5.0,
    delivery_time_min: int = 25,
    delivery_time_max: int = 35,
) -> Restaurant:
    return Restaurant(
        id=restaurant_id,
        name=name,
        address="Rua Teste, 1",
        categories=[category],
        average_rating=rating,
        review_count=review_count,
        delivery_fee=delivery_fee,
        delivery_time_min=delivery_time_min,
        delivery_time_max=delivery_time_max,
    )


class TestNormalizeScores:
    def test_normalize_keeps_order(self):
        scores = {"r1": 0.2, "r2": 0.8, "r3": 0.5}
        result = normalize_scores(scores)
        assert result["r2"] == 1.0
        assert result["r3"] == 0.5
        assert result["r1"] == 0.0

    def test_normalize_empty(self):
        assert normalize_scores({}) == {}

    def test_normalize_all_equal(self):
        scores = {"r1": 0.5, "r2": 0.5}
        result = normalize_scores(scores)
        assert result["r1"] == 0.5
        assert result["r2"] == 0.5


class TestFallbackRerank:
    def setup_method(self):
        self.reranker = LoRAReranker()
        self.reranker.available = False  # força fallback
        self.reranker.model = None
        self.reranker.tokenizer = None

    def test_fallback_returns_all_restaurants(self):
        restaurants = [
            _make_restaurant("r1", rating=4.5, review_count=100, delivery_fee=5.0),
            _make_restaurant("r2", rating=3.0, review_count=10, delivery_fee=15.0),
        ]
        lightgbm = {"r1": 0.9, "r2": 0.1}

        result = self.reranker.rerank(
            {}, restaurants, lightgbm, "tarde"
        )

        assert set(result.keys()) == {"r1", "r2"}
        assert result["r1"] > result["r2"]

    def test_fallback_scores_in_0_1(self):
        restaurants = [_make_restaurant("r1", rating=5.0, review_count=200)]
        result = self.reranker.rerank({}, restaurants, {"r1": 0.0}, "noite")
        assert 0.0 <= result["r1"] <= 1.0

    def test_fallback_turno_bonus(self):
        restaurants = [_make_restaurant("r1", rating=4.0, review_count=50)]
        lightgbm = {"r1": 0.5}
        base = self.reranker.rerank({}, restaurants, lightgbm, "tarde")
        noite = self.reranker.rerank({}, restaurants, lightgbm, "noite")
        madrugada = self.reranker.rerank({}, restaurants, lightgbm, "madrugada")

        # noite e madrugada devem ter bonus maior que tarde
        assert noite["r1"] >= base["r1"]
        assert madrugada["r1"] >= base["r1"]

    def test_empty_restaurants(self):
        result = self.reranker.rerank({}, {}, {}, "tarde")
        assert result == {}

    def test_global_reranker_instance(self):
        assert reranker is not None
        assert hasattr(reranker, "rerank")


class TestRerankerMetadata:
    def test_load_when_no_adapter_returns_false(self):
        # Sem artefato salvo, deve retornar False sem erro.
        assert reranker.load() is False

    def test_optional_deps_are_not_imported_eagerly(self):
        # Importar o módulo não deve importar torch/transformers/peft.
        instance = LoRAReranker()
        assert instance._deps_checked is False
        assert instance.available is False
        assert instance.model is None


class _FakeTensor:
    def __init__(self, value: float) -> None:
        self._value = value

    def reshape(self, *_args: int) -> "_FakeTensor":
        return self

    def __getitem__(self, _index: int) -> "_FakeTensor":
        return self

    def item(self) -> float:
        return self._value


class _FakeOutputs:
    def __init__(self, logit: float) -> None:
        self.logits = _FakeTensor(logit)


class _FakeModel:
    def __init__(self, logit: float) -> None:
        self._logit = logit

    def __call__(self, **_inputs):
        return _FakeOutputs(self._logit)


class _FakeTokenizer:
    def __call__(self, _text: str, **_kwargs):
        return {"input_ids": [[0]], "attention_mask": [[1]]}


class _FakeTorch:
    @staticmethod
    def no_grad():
        return contextlib.nullcontext()


class TestLoRAInference:
    def test_uses_sequence_classification_logits(self):
        instance = LoRAReranker()
        instance.available = True
        instance._torch = _FakeTorch()
        instance._AutoModelForSequenceClassification = object()
        instance.tokenizer = _FakeTokenizer()
        instance.model = _FakeModel(logit=10.0)

        restaurants = [
            _make_restaurant("r1", rating=4.0),
            _make_restaurant("r2", rating=3.0),
        ]

        scores = instance.rerank(
            {"total_orders": 3}, restaurants, {"r1": 0.5, "r2": 0.5}, "tarde"
        )

        # Logit alto -> probabilidade ~1. O resultado é normalizado no grupo.
        assert set(scores) == {"r1", "r2"}
        assert all(0.0 <= score <= 1.0 for score in scores.values())

    def test_falls_back_when_model_output_is_not_scalar(self):
        class _VectorTensor(_FakeTensor):
            def item(self) -> float:
                raise ValueError("only one element tensors can be converted")

        class _BrokenModel:
            def __call__(self, **_inputs):
                outputs = _FakeOutputs(0.0)
                outputs.logits = _VectorTensor(0.0)
                return outputs

        instance = LoRAReranker()
        instance.available = True
        instance._torch = _FakeTorch()
        instance._AutoModelForSequenceClassification = object()
        instance.tokenizer = _FakeTokenizer()
        instance.model = _BrokenModel()

        restaurants = [_make_restaurant("r1")]
        scores = instance.rerank({}, restaurants, {"r1": 0.5}, "tarde")

        assert "r1" in scores
        assert 0.0 <= scores["r1"] <= 1.0
