from huggingface_hub import HfApi, create_repo, upload_folder

# Configure com o seu usuário do Hugging Face
repo_id = "barbosaDev01/foodflow-llm-reranker-lora"
api = HfApi()

# Cria o repositório (se não existir)
create_repo(repo_id=repo_id, repo_type="model", exist_ok=True)

# Faz o upload de todos os arquivos da pasta do seu modelo LoRA
# (adapter_config.json, adapter_model.safetensors, etc.)
api.upload_folder(
    folder_path="./backend/models/lora_reranker",
    repo_id=repo_id,
    repo_type="model",
)
print(f"Modelo enviado! Acesse: https://huggingface.co/{repo_id}")