"""Publicação do adapter LoRA no Hugging Face Hub.

Envia o artefato salvo em `backend/models/lora_reranker/` para o repositório
definido em `LORA_HF_REPO_ID` (ou variável de ambiente `LORA_HF_REPO_ID`).

Quando `huggingface_hub` não está instalado ou o repositório não está
configurado, o script imprime instruções de publicação manual.

Uso:
    python scripts/publish_lora.py
    # ou com o módulo do projeto:
    python -m scripts.publish_lora

Variáveis de ambiente:
    LORA_HF_REPO_ID   ID do repositório no Hugging Face Hub (ex: usuario/foodflow-lora-reranker)
    HF_TOKEN          Token de acesso do Hugging Face (pode ser definido via `huggingface-cli login`)
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(BACKEND_ROOT))

from app.ml.reranker import BASE_MODEL_ID, HF_REPO_ID, LORA_MODEL_DIR  # noqa: E402

logger = logging.getLogger(__name__)


def _read_metadata() -> dict[str, Any]:
    meta_path = LORA_MODEL_DIR / "reranker_metadata.json"
    if meta_path.exists():
        return json.loads(meta_path.read_text(encoding="utf-8"))
    return {}


def publish_to_hf() -> bool:
    """Publica o adapter LoRA no Hugging Face Hub.

    Retorna True se a publicação foi iniciada com sucesso, False caso
    contrário (dependências ausentes, repo não configurado, etc.).
    """
    repo_id = os.getenv("LORA_HF_REPO_ID") or HF_REPO_ID
    if not repo_id:
        logger.warning(
            "LORA_HF_REPO_ID não definido. Pule a publicação ou defina a "
            "variável de ambiente e execute novamente."
        )
        print_instructions()
        return False

    try:
        from huggingface_hub import HfApi, create_repo, upload_folder  # type: ignore
    except Exception as exc:
        logger.warning(
            "huggingface_hub não instalado (%s). Pule a publicação ou instale "
            "a dependência e execute novamente.",
            exc,
        )
        print_instructions()
        return False

    try:
        api = HfApi()
        create_repo(repo_id, repo_type="model", exist_ok=True)
        upload_folder(
            folder_path=str(LORA_MODEL_DIR),
            repo_id=repo_id,
            repo_type="model",
            commit_message="treino: adapter LoRA para re-ranking de recomendações",
        )
        logger.info("Adapter LoRA publicado em https://huggingface.co/%s", repo_id)
        print(
            f"\n✅ Publicado com sucesso em https://huggingface.co/{repo_id}\n"
        )
        return True
    except Exception as exc:
        logger.warning("Falha ao publicar no Hugging Face Hub: %s", exc)
        print_instructions()
        return False


def print_instructions() -> None:
    """Imprime instruções de publicação manual."""
    metadata = _read_metadata()
    print("\n--- Instruções de publicação no Hugging Face Hub ---")
    print("1. Instale a dependência:")
    print("   pip install huggingface_hub")
    print("\n2. Autentique (execute uma vez):")
    print("   huggingface-cli login")
    print("\n3. Publique a pasta do adapter:")
    print(f"   cd {LORA_MODEL_DIR.parent.parent}")
    print(f"   huggingface-cli upload {os.getenv('LORA_HF_REPO_ID', '<seu-usuario>/<repo>')} models/lora_reranker/")
    print(f"\n   Ou via Python:")
    print(f"     from huggingface_hub import HfApi, upload_folder")
    print(f"     api = HfApi()")
    print(f"     api.create_repo('<seu-usuario>/<repo>', repo_type='model', exist_ok=True)")
    print(f"     upload_folder(folder_path='models/lora_reranker', repo_id='<seu-usuario>/<repo>', repo_type='model')")
    print("\n----------------------------------------------------\n")


if __name__ == "__main__":
    publish_to_hf()
