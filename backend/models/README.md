# Artefatos de modelo

Este diretório guarda modelos treinados em runtime. Binários (`*.joblib`,
`*.pkl`) e o adapter LoRA **não são versionados** no Git.

## LightGBM (modelo principal)

- Treino com PostgreSQL: `cd backend && python -m app.ml.train --source db`
- Treino com seed determinístico: `cd backend && python -m app.ml.train --source seed`
- Saída: `backend/models/recommender.joblib`
- Sem o arquivo, a API usa fallback por popularidade (degradação graciosa).
- O artefato deve ser treinado no **mesmo ambiente** da API. Modelos
  serializados com NumPy 2.x não carregam em ambientes com NumPy 1.26
  (`ModuleNotFoundError: numpy._core`); nesse caso, retreine.
- O artefato atual foi regenerado com NumPy 1.26.0 e carrega com
  `recommender.load() == True` (26 features).

## LoRA (re-ranking opcional/experimental)

- Dependências: `cd backend && pip install -r requirements-llmops.txt`
- Treino com PostgreSQL: `python scripts/train_lora.py --source db`
- Treino com seed determinístico: `python scripts/train_lora.py --source seed`
- Saída: `backend/models/lora_reranker/`
- Só é carregado com `ENABLE_LORA_RERANKER=true`.
- Sem dependências ou sem adapter treinado, o serving usa o fallback
  determinístico.
- Treino de referência executado localmente: 40 amostras, 3 épocas,
  `sentence-transformers/all-MiniLM-L6-v2`, loss final ~0,47. A qualidade
  do adapter (AUC/NDCG) ainda não foi avaliada e ele não foi publicado.
- O adapter não é commitado. Use `scripts/publish_lora.py` apenas depois
  de avaliar e documentar o artefato.

## Docker

- Desenvolvimento: `./backend` é montado em `/app`, então este diretório é
  compartilhado com o container.
- Produção: o volume nomeado `backend_models` é montado em `/app/models`.
  Treine em um job separado para que o artefato sobreviva à recriação do
  container.
