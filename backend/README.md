# FoodFlow Backend

API REST em **FastAPI** com **PostgreSQL 16 + PostGIS**, **Redis** e recomendação **LightGBM**, seguindo a arquitetura documentada em [`docs/arquitetura-tecnica.md`](../docs/arquitetura-tecnica.md).

## Stack

| Camada | Tecnologia |
|--------|------------|
| API | FastAPI (Python 3.11) |
| Banco | PostgreSQL 16 + PostGIS |
| Cache | Redis 7 |
| ORM | SQLAlchemy 2.0 (async) |
| Geo | GeoAlchemy2 |
| ML | LightGBM + scikit-learn + pandas |

## Endpoints

| Método | Endpoint | Finalidade |
|--------|----------|------------|
| `GET` | `/health` | Health check + status do modelo |
| `GET` | `/api/v1/restaurants/search?lat=&lon=&radius_km=` | Busca geoespacial (PostGIS `ST_DWithin`) |
| `GET` | `/api/v1/restaurants/{id}` | Detalhe do restaurante + últimas 10 avaliações |
| `POST` | `/api/v1/reviews` | Cria avaliação com idempotência via `Idempotency-Key` |
| `GET` | `/api/v1/recommendations?user_id=&lat=&lon=&turno=` | Ranking personalizado (Redis → LightGBM → popularidade) |
| `POST` | `/api/v1/recommendations/train` | Treina o modelo com os pedidos existentes |
| `POST` | `/api/v1/events` | Coleta de eventos para o pipeline de ML |

`turno` aceita `manha`, `tarde`, `noite` ou `madrugada` (padrão: `tarde`).

## Como a recomendação funciona

1. Busca até 50 restaurantes em um raio de 10 km via PostGIS.
2. Consulta scores no Redis (`reco:scores:{user_id}:{turno}`).
3. Em cache miss:
   - com modelo treinado **e** histórico do usuário: features por turno + LightGBM;
   - sem histórico (cold start): fallback por popularidade (nota + volume de avaliações).
4. Normaliza os scores para `[0, 1]`, grava no Redis com TTL de 24h e ordena os candidatos.

As features seguem a documentação: ticket médio, frete médio, contagem por turno e **medoide** aproximado por moda ponderada pela recência. O treino usa amostragem `1 positivo : 3 negativos` e remove o restaurante-alvo do histórico para reduzir vazamento.

> O batch scoring diário descrito na documentação ainda é feito sob demanda (lazy) e cacheado no Redis. A troca por um job agendado é o próximo passo de MLOps.

## Como rodar

### Com Docker Compose (recomendado)

```bash
# Na raiz do projeto
docker compose up -d
```

Isso sobe PostgreSQL + PostGIS, Redis e o backend, cria as tabelas e roda o seed automaticamente.

### Localmente (sem Docker)

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/init_db.py
uvicorn app.main:app --reload
```

A API estará disponível em `http://localhost:8000` e o Swagger em `http://localhost:8000/docs`.

## Seed

O `scripts/init_db.py` é **idempotente** e popula:

- 12 restaurantes de Osasco/SP com coordenadas reais aproximadas;
- 4 usuários com preferências alimentares;
- 30 pedidos distribuídos entre turnos (matéria-prima do treino);
- 36 avaliações (3 por restaurante) com agregados recalculados.

Os IDs são determinísticos (`uuid5`), então reiniciar o container não duplica dados.

## Testes

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

Os testes cobrem feature engineering, geração do dataset de treino, round-trip do modelo, query PostGIS, validação de schemas e contratos da API (sem depender de banco).

## Estrutura

```
backend/
├── Dockerfile
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
├── app/
│   ├── main.py                  # FastAPI + lifespan (carrega modelo)
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── crud.py                  # busca geoespacial, reviews, eventos
│   ├── seeds.py                 # seed idempotente
│   ├── seed_data.py             # dados do seed
│   ├── api/
│   │   ├── restaurants.py
│   │   ├── reviews.py
│   │   ├── recommendations.py
│   │   └── events.py
│   ├── cache/
│   │   └── redis_client.py      # scores + Redis Stream de eventos
│   ├── core/
│   │   ├── config.py
│   │   └── constants.py
│   └── ml/
│       ├── features.py          # features compartilhadas treino/serving
│       ├── recommender.py       # load/save + predict + fallback
│       └── train.py             # dataset, treino e métricas
├── models/                      # artefatos .joblib (gitignored)
├── scripts/
│   └── init_db.py
└── tests/
```
