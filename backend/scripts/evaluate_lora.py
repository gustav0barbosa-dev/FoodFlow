"""Avaliação offline do adapter LoRA com AUC e NDCG@5.

Executa um split temporal (treina em pedidos antigos e avalia nos recentes)
e compara quatro estratégias: popularidade, LightGBM, LoRA e híbrido.

Uso:
    python scripts/evaluate_lora.py --source seed
    python scripts/evaluate_lora.py --source db --holdout-days 14
    python scripts/evaluate_lora.py --source seed --output models/lora_evaluation.json

O treino do adapter é feito em um diretório temporário e descartado ao final;
o artefato de serving (`backend/models/lora_reranker/`) não é alterado.
"""

import json
import sys
from pathlib import Path

# Quando executado como `python scripts/evaluate_lora.py`, o Python adiciona
# apenas `backend/scripts` ao sys.path. Incluímos `backend/` para importar app.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.ml.lora_evaluation import evaluate  # noqa: E402


def _format_table(result: dict) -> str:
    rows = [
        ("Estratégia", "AUC", "NDCG@5"),
        ("popularidade", result["metrics"]["popularity"]["auc"], result["metrics"]["popularity"]["ndcg_at_5"]),
        ("lightgbm", result["metrics"]["lightgbm"]["auc"], result["metrics"]["lightgbm"]["ndcg_at_5"]),
    ]
    for strategy in ("lora", "hybrid"):
        metrics = result["metrics"].get(strategy)
        if metrics is not None:
            rows.append((strategy, metrics["auc"], metrics["ndcg_at_5"]))
        else:
            rows.append((strategy, "n/d", "n/d"))

    widths = [max(len(str(row[column])) for row in rows) for column in range(3)]
    lines = []
    for index, row in enumerate(rows):
        lines.append(
            " | ".join(
                str(value).ljust(widths[column])
                for column, value in enumerate(row)
            )
        )
        if index == 0:
            lines.append("-+-".join("-" * width for width in widths))
    return "\n".join(lines)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Avaliação offline do re-ranker LoRA (AUC/NDCG@5)"
    )
    parser.add_argument(
        "--source",
        choices=("db", "seed"),
        default="seed",
        help="'db' usa os pedidos do PostgreSQL; 'seed' usa o seed determinístico.",
    )
    parser.add_argument(
        "--holdout-days",
        type=int,
        default=7,
        help="Janela recente reservada para avaliação (padrão: 7 dias).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Caminho opcional para salvar o relatório em JSON.",
    )
    args = parser.parse_args()

    try:
        result = evaluate(source=args.source, holdout_days=args.holdout_days)
    except ValueError as exc:
        print(f"Avaliação não executada: {exc}")
        return 1

    print(
        f"Avaliação LoRA ({result['source']}, holdout_days={result['holdout_days']})"
    )
    print(json.dumps(result["split"], indent=2, ensure_ascii=False))
    if not result["lora"].get("available", False):
        print(f"LoRA indisponível: {result['lora'].get('reason')}")
    else:
        print(
            "Adapter temporário treinado com "
            f"{result['lora'].get('train_samples')} amostras."
        )
    print()
    print(_format_table(result))
    print()
    print(result["notes"])

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"\nRelatório salvo em {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
