"""Re-ranking de recomendações com fine-tuning LoRA.

Este módulo implementa um segundo estágio de ranking sobre os scores
produzidos pelo modelo LightGBM. O objetivo do LoRA (Low-Rank Adaptation)
é ajustar o modelo base (um pequeno codificador de texto/tabular) às
preferências do usuário por turno, sem retreinar todos os pesos.

Design:
- Quando `transformers` + `peft` + `torch` estão disponíveis, carrega um
  modelo base pequeno e aplica adapters LoRA treinados.
- Quando não estão disponíveis (ambiente sem GPU/dependências LLMOps),
  opera em modo "fallback": aplica um ajuste determinístico baseado nas
  features do LightGBM, mantendo a API funcional.

Os artefatos (adapter LoRA + tokenizer/config) são salvos em
`backend/models/lora_reranker/` e podem ser publicados no Hugging Face Hub.
"""

import json
import logging
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.constants import TURNOS, Turno
from app.ml.features import build_candidate_features
from app.models import Restaurant

logger = logging.getLogger(__name__)

LORA_MODEL_DIR = Path(__file__).resolve().parents[2] / "models" / "lora_reranker"
LORA_CONFIG_FILE = LORA_MODEL_DIR / "adapter_config.json"
LORA_WEIGHTS_FILE = LORA_MODEL_DIR / "adapter_model.safetensors"

# ID do modelo base sugerido para fine-tuning LoRA (pode ser sobrescrito via env).
BASE_MODEL_ID = os.getenv(
    "LORA_BASE_MODEL_ID", "sentence-transformers/all-MiniLM-L6-v2"
)

# ID do repositório no Hugging Face Hub (pode ser sobrescrito via env).
HF_REPO_ID = os.getenv("LORA_HF_REPO_ID", "")


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value))


class LoRAReranker:
    """Re-ranking com LoRA sobre os scores do LightGBM.

    A classe expõe uma única interface, `rerank`, que recebe os scores
    brutos do LightGBM e devolve scores ajustados. Quando as dependências
    de LLM não estão instaladas, aplica um fallback determinístico baseado
    nas features do candidato (rating, frete, tempo de entrega e turno).
    """

    def __init__(self, model_dir: Path | str | None = None) -> None:
        # Permite avaliar um adapter temporário (por exemplo, em um split de
        # validação) sem sobrescrever o artefato usado em serving.
        self.model_dir: Path = (
            Path(model_dir) if model_dir is not None else LORA_MODEL_DIR
        )
        self.available: bool = False
        self._deps_checked: bool = False
        self._torch = None
        self._AutoModelForSequenceClassification = None
        self._AutoTokenizer = None
        self._PeftModel = None
        self._get_peft_model = None
        self._LoraConfig = None
        self._task_type = None
        self.model = None
        self.tokenizer = None
        self.metadata: dict[str, Any] = {}
        # Importante: não importamos torch/transformers/peft aqui. As
        # dependências opcionais só são carregadas em `load()`, quando o LoRA
        # está explicitamente habilitado.

    # ------------------------------------------------------------------
    # Importação condicional das dependências de LLM
    # ------------------------------------------------------------------

    def _try_import_llm_deps(self) -> bool:
        """Importa torch/transformers/peft sob demanda.

        Só é chamado por `load()`. Mantém o import do módulo leve para que a
        API funcione sem as dependências de LLMOps instaladas.
        """
        if self._deps_checked:
            return self.available

        self._deps_checked = True
        try:
            import torch  # type: ignore
            from transformers import (  # type: ignore
                AutoModelForSequenceClassification,
                AutoTokenizer,
            )
            from peft import (  # type: ignore
                LoraConfig,
                PeftModel,
                get_peft_model,
                TaskType,
            )

            self._torch = torch
            self._AutoModelForSequenceClassification = (
                AutoModelForSequenceClassification
            )
            self._AutoTokenizer = AutoTokenizer
            self._PeftModel = PeftModel
            self._get_peft_model = get_peft_model
            self._LoraConfig = LoraConfig
            self._task_type = TaskType
            self.available = True
            logger.info("Dependências de LLM (transformers/peft/torch) carregadas.")
        except Exception as exc:  # dependências opcionais não instaladas
            logger.info(
                "Dependências de LLM não disponíveis (%s); o re-rankador usará "
                "fallback determinístico.",
                exc,
            )
            self.available = False
        return self.available

    # ------------------------------------------------------------------
    # Carregamento / salvamento do adapter LoRA
    # ------------------------------------------------------------------

    def load(self) -> bool:
        """Carrega o adapter LoRA e o tokenizer, se existirem.

        Retorna False (sem levantar exceção) quando as dependências opcionais
        não estão instaladas, quando não há adapter ou quando o artefato é
        apenas um placeholder. Nesses casos a API segue com fallback.
        """
        config_file = self.model_dir / "adapter_config.json"
        weights_file = self.model_dir / "adapter_model.safetensors"
        if not config_file.exists() or not weights_file.exists():
            logger.info(
                "Adapter LoRA não encontrado em %s; usando fallback.", self.model_dir
            )
            return False

        if not self._try_import_llm_deps():
            logger.info("Re-rankador LoRA indisponível; usando fallback.")
            return False

        try:
            meta_path = self.model_dir / "reranker_metadata.json"
            if meta_path.exists():
                self.metadata = json.loads(meta_path.read_text(encoding="utf-8"))

            if self.metadata.get("placeholder"):
                logger.info(
                    "Adapter LoRA é um placeholder (sem treino real); usando fallback."
                )
                return False

            tokenizer = self._AutoTokenizer.from_pretrained(str(self.model_dir))
            # A inferência precisa usar a mesma arquitetura do treino:
            # AutoModelForSequenceClassification com num_labels=1.
            base_model = self._AutoModelForSequenceClassification.from_pretrained(
                BASE_MODEL_ID, num_labels=1
            )
            model = self._PeftModel.from_pretrained(base_model, str(self.model_dir))
            model.eval()

            self.tokenizer = tokenizer
            self.model = model
            logger.info("Adapter LoRA carregado de %s.", self.model_dir)
            return True
        except Exception as exc:
            logger.warning(
                "Falha ao carregar adapter LoRA (%s): %s", self.model_dir, exc
            )
            self.available = False
            self.model = None
            self.tokenizer = None
            return False

    def save(
        self,
        model: Any,
        tokenizer: Any,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Salva o adapter LoRA, tokenizer e metadados em disco."""
        self.model_dir.mkdir(parents=True, exist_ok=True)
        model.save_pretrained(str(self.model_dir))
        tokenizer.save_pretrained(str(self.model_dir))

        bundle = {
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "base_model": BASE_MODEL_ID,
            "hf_repo_id": HF_REPO_ID,
            **(metadata or {}),
        }
        (self.model_dir / "reranker_metadata.json").write_text(
            json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        self.metadata = bundle
        self.model = model
        self.tokenizer = tokenizer
        self.available = True
        logger.info("Adapter LoRA salvo em %s.", self.model_dir)

    # ------------------------------------------------------------------
    # Fallback determinístico (sem dependências de LLM)
    # ------------------------------------------------------------------

    @staticmethod
    def _fallback_adjustment(
        restaurant: Restaurant,
        turno: Turno,
        lightgbm_score: float,
    ) -> float:
        """Ajuste determinístico baseado nas features do restaurante.

        Usado quando o adapter LoRA não está disponível. Não é treino de
        fato, mas mantém o comportamento de re-ranking previsível e
        determinístico para ambientes sem GPU/dependências LLMOps.
        """
        rating = float(restaurant.average_rating or 0.0) / 5.0
        review_volume = math.log1p(float(restaurant.review_count or 0))
        delivery_penalty = 1.0 / (1.0 + 0.1 * float(restaurant.delivery_fee or 0))
        time_penalty = 1.0 / (
            1.0 + 0.05 * float((restaurant.delivery_time_min + restaurant.delivery_time_max) / 2)
        )

        # Sinal por turno: restaurantes com taxa/frete menores ganham leve
        # prioridade à noite/madrugada (cenário de delivery rápido).
        turno_bonus: dict[Turno, float] = {
            "manha": 0.0,
            "tarde": 0.0,
            "noite": 0.05,
            "madrugada": 0.08,
        }

        adjusted = (
            0.6 * lightgbm_score
            + 0.2 * rating
            + 0.1 * min(review_volume / 5.0, 1.0)
            + 0.1 * delivery_penalty
            + 0.1 * time_penalty
            + turno_bonus.get(turno, 0.0)
        )
        return _sigmoid(adjusted)

    # ------------------------------------------------------------------
    # Re-ranking público
    # ------------------------------------------------------------------

    def rerank(
        self,
        user_features: dict[str, Any],
        restaurants: list[Restaurant],
        lightgbm_scores: dict[str, float],
        turno: Turno = "tarde",
    ) -> dict[str, float]:
        """Ajusta os scores do LightGBM com o adapter LoRA (ou fallback).

        Retorna um dicionário {restaurant_id: score} normalizado em [0, 1],
        preservando a ordem quando o re-rankador não está disponível.
        """
        if not restaurants:
            return {}

        # Se o LoRA não estiver disponível, aplica fallback determinístico.
        if not self.available or self.model is None or self.tokenizer is None:
            return self._fallback(restaurants, lightgbm_scores, turno)

        # Caminho com LoRA real: monta texto de entrada por (usuário, restaurante, turno)
        # e obtém o score do adapter.
        if self._torch is None or self._AutoModelForSequenceClassification is None:
            return self._fallback(
                restaurants, lightgbm_scores, turno
            )

        try:
            torch = self._torch
            raw_scores: dict[str, float] = {}
            with torch.no_grad():
                for restaurant in restaurants:
                    text = self._build_input_text(user_features, restaurant, turno)
                    inputs = self.tokenizer(
                        text,
                        return_tensors="pt",
                        truncation=True,
                        max_length=128,
                    )
                    outputs = self.model(**inputs)
                    # O modelo de sequence classification (num_labels=1) devolve
                    # logits de shape (batch, 1); extraímos um único escalar.
                    logit = float(outputs.logits.reshape(-1)[0].item())
                    raw_scores[str(restaurant.id)] = _sigmoid(logit)

            return normalize_scores(raw_scores)
        except Exception as exc:
            logger.warning("Falha no re-rank com LoRA (%s); usando fallback.", exc)
            return self._fallback(restaurants, lightgbm_scores, turno)

    def _fallback(
        self,
        restaurants: list[Restaurant],
        lightgbm_scores: dict[str, float],
        turno: Turno,
    ) -> dict[str, float]:
        """Aplica o ajuste determinístico a todos os candidatos."""
        raw_scores = {
            str(r.id): self._fallback_adjustment(
                r, turno, lightgbm_scores.get(str(r.id), 0.5)
            )
            for r in restaurants
        }
        return normalize_scores(raw_scores)

    @staticmethod
    def _build_input_text(
        user_features: dict[str, Any],
        restaurant: Restaurant,
        turno: Turno,
    ) -> str:
        """Converte (features do usuário, restaurante, turno) em texto para o LoRA."""
        dietary = ", ".join(
            user_features.get("dietary_preferences", []) or []
        ) or "sem preferências"
        return (
            f"usuario: total_orders={user_features.get('total_orders', 0)}; "
            f"preferencias={dietary}; turno={turno}; "
            f"restaurante={restaurant.name}; categoria={restaurant.categories[0] if restaurant.categories else ''}; "
            f"nota={restaurant.average_rating}; frete={restaurant.delivery_fee}; "
            f"tempo={restaurant.delivery_time_min}-{restaurant.delivery_time_max} min"
        )


def normalize_scores(scores: dict[str, float]) -> dict[str, float]:
    """Escala os scores do re-rankador para [0, 1] mantendo a ordem do ranking."""
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


reranker = LoRAReranker()
