"""Treino offline do adapter LoRA do re-rankador.

Este módulo concentra a lógica de treinamento. Ele é independente do
processo da API: deve ser executado como comando via
`scripts/train_lora.py`, nunca dentro de uma requisição HTTP.

Gera um dataset sintético a partir dos pedidos do banco
(usuário × restaurante × turno) e treina um adapter LoRA sobre um modelo
base pequeno (ex: all-MiniLM-L6-v2), salvando o artefato em
`backend/models/lora_reranker/`.

Quando `transformers` + `peft` + `torch` não estão instalados, gera um
artefato de placeholder (config + metadados) apenas para demonstrar a
estrutura esperada. O serving detecta o placeholder e usa o fallback.
"""

import json
import logging
import random
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import TURNOS, Turno
from app.database import AsyncSessionLocal
from app.ml.features import build_user_features, order_turno
from app.ml.reranker import BASE_MODEL_ID, LORA_MODEL_DIR
from app.models import Order, Restaurant, User

logger = logging.getLogger(__name__)

RANDOM_SEED = 42
EPOCHS = 3
BATCH_SIZE = 8
LEARNING_RATE = 2e-4
LORA_R = 8
LORA_ALPHA = 16
LORA_DROPOUT = 0.05

MAX_SAMPLES_PER_USER_TURNO = 20


def _build_input_text(
    user_features: dict[str, Any],
    restaurant: Restaurant,
    turno: Turno,
) -> str:
    """Converte (features do usuário, restaurante, turno) em texto.

    O mesmo formato é usado no treino e na inferência, garantindo que o
    adapter veja a mesma distribuição de entrada.
    """
    dietary = (
        ", ".join(user_features.get("dietary_preferences", []) or [])
        or "sem preferências"
    )
    return (
        f"usuario: total_orders={user_features.get('total_orders', 0)}; "
        f"preferencias={dietary}; turno={turno}; "
        f"restaurante={restaurant.name}; "
        f"categoria={(restaurant.categories[0] if restaurant.categories else '')}; "
        f"nota={restaurant.average_rating}; frete={restaurant.delivery_fee}; "
        f"tempo={restaurant.delivery_time_min}-{restaurant.delivery_time_max} min"
    )


def build_lora_training_frame(
    users: list[User],
    orders: list[Order],
    restaurants: list[Restaurant],
) -> list[dict[str, Any]]:
    """Gera amostras de texto (input, label) para treino do LoRA.

    Cada amostra é um texto descritivo (usuário, restaurante, turno) e um
    label binário: 1 se o usuário pediu naquele restaurante no turno, 0 caso
    contrário (amostragem negativa equilibrada).
    """
    if not users or not restaurants:
        return []

    restaurant_by_id = {restaurant.id: restaurant for restaurant in restaurants}
    rng = random.Random(RANDOM_SEED)
    samples: list[dict[str, Any]] = []

    for user in users:
        user_orders = [order for order in orders if order.user_id == user.id]
        if not user_orders:
            continue

        orders_by_turno: dict[Turno, list[Order]] = {turno: [] for turno in TURNOS}
        for order in user_orders:
            orders_by_turno[order_turno(order)].append(order)

        for turno in TURNOS:
            turno_orders = orders_by_turno[turno]
            if not turno_orders:
                continue

            positive_ids = {
                order.restaurant_id
                for order in turno_orders
                if order.restaurant_id in restaurant_by_id
            }
            if not positive_ids:
                continue

            for restaurant_id in list(positive_ids)[:MAX_SAMPLES_PER_USER_TURNO]:
                history_without_target = [
                    order
                    for order in user_orders
                    if order.restaurant_id != restaurant_id
                ]
                features = build_user_features(history_without_target, user)
                restaurant = restaurant_by_id[restaurant_id]
                text = _build_input_text(features, restaurant, turno)
                samples.append({"text": text, "label": 1.0})

            negative_candidates = [
                restaurant
                for restaurant in restaurants
                if restaurant.id not in positive_ids
            ]
            sample_size = min(
                len(negative_candidates),
                max(1, len(positive_ids)),
            )
            if sample_size == 0:
                continue

            features = build_user_features(user_orders, user)
            for restaurant in rng.sample(negative_candidates, sample_size):
                text = _build_input_text(features, restaurant, turno)
                samples.append({"text": text, "label": 0.0})

    return samples


async def load_training_data(
    session: AsyncSession,
) -> tuple[list[User], list[Order], list[Restaurant]]:
    users = (await session.execute(select(User))).scalars().all()
    orders = (await session.execute(select(Order))).scalars().all()
    restaurants = (await session.execute(select(Restaurant))).scalars().all()
    return list(users), list(orders), list(restaurants)


def _try_train_with_llm_deps(
    samples: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Tenta treinar o adapter LoRA com transformers/peft/torch.

    Retorna metadados do treino ou None se as dependências não estiverem
    disponíveis (nesse caso, gera um artefato placeholder).
    """
    try:
        import torch  # type: ignore
        from torch.utils.data import Dataset  # type: ignore
        from transformers import (  # type: ignore
            AutoModelForSequenceClassification,
            AutoTokenizer,
            Trainer,
            TrainingArguments,
        )
        from peft import (  # type: ignore
            LoraConfig,
            get_peft_model,
            prepare_model_for_kbit_training,
            TaskType,
        )
    except Exception as exc:
        logger.info(
            "Dependências de LLM não disponíveis (%s); gerando artefato placeholder.",
            exc,
        )
        return None

    class _PairDataset(Dataset):
        def __init__(
            self,
            samples: list[dict[str, Any]],
            tokenizer: Any,
            max_length: int = 128,
        ):
            self.samples = samples
            self.tokenizer = tokenizer
            self.max_length = max_length

        def __len__(self) -> int:
            return len(self.samples)

        def __getitem__(self, idx: int) -> dict[str, Any]:
            item = self.samples[idx]
            enc = self.tokenizer(
                item["text"],
                return_tensors="pt",
                truncation=True,
                max_length=self.max_length,
                padding="max_length",
            )
            return {
                "input_ids": enc["input_ids"].squeeze(0),
                "attention_mask": enc["attention_mask"].squeeze(0),
                "labels": torch.tensor(item["label"], dtype=torch.float32),
            }

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_ID)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    base_model = AutoModelForSequenceClassification.from_pretrained(
        BASE_MODEL_ID, num_labels=1
    )
    base_model = prepare_model_for_kbit_training(base_model)

    lora_config = LoraConfig(
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        bias="none",
        task_type=TaskType.SEQ_CLS,
        target_modules=["query", "value"],
    )
    model = get_peft_model(base_model, lora_config)

    train_args = TrainingArguments(
        output_dir=str(LORA_MODEL_DIR),
        num_train_epochs=EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        learning_rate=LEARNING_RATE,
        logging_steps=10,
        save_strategy="no",
        report_to="none",
        seed=RANDOM_SEED,
    )

    dataset = _PairDataset(samples, tokenizer)
    trainer = Trainer(
        model=model,
        args=train_args,
        train_dataset=dataset,
        tokenizer=tokenizer,
    )
    trainer.train()

    metrics = {
        "train_samples": len(samples),
        "epochs": EPOCHS,
        "learning_rate": LEARNING_RATE,
        "lora_r": LORA_R,
        "lora_alpha": LORA_ALPHA,
        "lora_dropout": LORA_DROPOUT,
        "base_model": BASE_MODEL_ID,
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }

    LORA_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(LORA_MODEL_DIR))
    tokenizer.save_pretrained(str(LORA_MODEL_DIR))
    (LORA_MODEL_DIR / "reranker_metadata.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    logger.info("Adapter LoRA treinado e salvo em %s.", LORA_MODEL_DIR)
    return metrics


def _generate_placeholder_artifact() -> dict[str, Any]:
    """Gera um artefato placeholder quando as dependências não estão instaladas."""
    LORA_MODEL_DIR.mkdir(parents=True, exist_ok=True)

    adapter_config = {
        "peft_type": "LORA",
        "task_type": "SEQ_CLS",
        "r": LORA_R,
        "lora_alpha": LORA_ALPHA,
        "lora_dropout": LORA_DROPOUT,
        "bias": "none",
        "target_modules": ["query", "value"],
        "base_model_name_or_path": BASE_MODEL_ID,
        "inference_mode": True,
        "placeholder": True,
    }
    (LORA_MODEL_DIR / "adapter_config.json").write_text(
        json.dumps(adapter_config, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    (LORA_MODEL_DIR / "adapter_model.safetensors").write_bytes(b"")

    (LORA_MODEL_DIR / "tokenizer.json").write_text(
        json.dumps({"vocab": {}, "placeholder": True}), encoding="utf-8"
    )

    metadata = {
        "train_samples": 0,
        "epochs": EPOCHS,
        "learning_rate": LEARNING_RATE,
        "lora_r": LORA_R,
        "lora_alpha": LORA_ALPHA,
        "lora_dropout": LORA_DROPOUT,
        "base_model": BASE_MODEL_ID,
        "placeholder": True,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "note": "Artefato placeholder gerado sem dependências de LLM. "
        "Instale transformers/peft/torch para treino real.",
    }
    (LORA_MODEL_DIR / "reranker_metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    logger.info(
        "Artefato placeholder salvo em %s (sem treino real).", LORA_MODEL_DIR
    )
    return metadata


async def train_lora() -> dict[str, Any] | None:
    """Executa o pipeline de treino LoRA a partir dos dados do banco."""
    async with AsyncSessionLocal() as session:
        users, orders, restaurants = await load_training_data(session)

    return _train_from_entities(users, orders, restaurants)


def train_lora_from_seed() -> dict[str, Any] | None:
    """Treina o LoRA a partir do seed determinístico, sem acessar o banco."""
    from app.ml.train import build_seed_entities

    users, orders, restaurants = build_seed_entities()
    return _train_from_entities(users, orders, restaurants)


def _train_from_entities(
    users: list[User],
    orders: list[Order],
    restaurants: list[Restaurant],
) -> dict[str, Any] | None:
    samples = build_lora_training_frame(users, orders, restaurants)
    if not samples:
        logger.warning("Nenhuma amostra gerada; treino LoRA ignorado.")
        return None

    logger.info("Geradas %d amostras para treino LoRA.", len(samples))

    metrics = _try_train_with_llm_deps(samples)
    if metrics is None:
        metrics = _generate_placeholder_artifact()

    return metrics
