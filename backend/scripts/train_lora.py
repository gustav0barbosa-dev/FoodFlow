"""Ponto de entrada CLI para o treino do adapter LoRA.

A lógica fica em `app.ml.lora_training`; este script é apenas um wrapper
para execução manual/scheduled. O treinamento é uma operação offline e
nunca deve ser disparado dentro da API.

Uso:
    python scripts/train_lora.py

Variáveis de ambiente opcionais:
    LORA_BASE_MODEL_ID  ID do modelo base no Hugging Face
                        (padrão: sentence-transformers/all-MiniLM-L6-v2)
    LORA_HF_REPO_ID     ID do repositório de destino no Hugging Face Hub
"""

import asyncio
import sys
from pathlib import Path

# Quando executado como `python scripts/train_lora.py`, o Python adiciona
# apenas `backend/scripts` ao sys.path. Incluímos `backend/` para importar app.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.ml.lora_training import train_lora, train_lora_from_seed  # noqa: E402


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Fine-tuning LoRA do re-ranker")
    parser.add_argument(
        "--source",
        choices=("db", "seed"),
        default="db",
        help="'db' usa os pedidos do PostgreSQL; 'seed' usa o seed determinístico.",
    )
    args = parser.parse_args()

    if args.source == "seed":
        result = train_lora_from_seed()
    else:
        result = asyncio.run(train_lora())

    if result is None:
        print("Dados insuficientes para treino LoRA; artefato nao salvo.")
        return 1

    placeholder = result.get("placeholder", False)
    status = " (placeholder)" if placeholder else ""
    print(f"Treino LoRA concluido{status}: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
