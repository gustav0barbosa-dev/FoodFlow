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

As features seguem a documentação: ticket médio, frete médio, contagem por turno e **medoide** aproximado por moda ponderada pela recência. O turno solicitado entra como one-hot (`is_manha`, `is_tarde`, ...), então o modelo aprende rankings diferentes por período. O treino usa amostragem `1 positivo : 3 negativos` por turno e remove o restaurante-alvo do histórico para reduzir vazamento.

## Batch scoring

O job `scripts/batch_score.py` calcula os scores de todos os usuários para os quatro turnos e grava em `reco:scores:{user_id}:{turno}` com TTL de 24h. A API continua funcionando sem o job (cache miss → modelo/popularidade), mas o batch evita latência de inferência na primeira requisição após a invalidação.

```bash
cd backend
python scripts/batch_score.py                    # todos os usuários e turnos
python scripts/batch_score.py --turno tarde \
  --turno noite                                  # apenas alguns turnos
python scripts/batch_score.py --user-id <uuid> --dry-run
```

O script carrega `models/recommender.joblib`; se o modelo não existir, grava o fallback por popularidade. O resumo informa quantas combinações usaram modelo/popularidade e quantas foram gravadas no Redis.

Agendamento:

- **Docker Compose:** `docker compose --profile batch run --rm batch-scorer`;
- **Windows:** Task Scheduler diário chamando `.venv\Scripts\python.exe scripts\batch_score.py`;
- **Linux:** cron, por exemplo `0 3 * * * cd /app/backend && .venv/bin/python scripts/batch_score.py`.

Treinar novamente (`POST /api/v1/recommendations/train`) invalida todos os scores; rode o batch em seguida para repopular o cache.

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

## Migrações (Alembic)

O schema é versionado em `alembic/versions/`. O `scripts/init_db.py` executa `alembic upgrade head` antes do seed, então o fluxo local e o Docker Compose continuam iguais.

```bash
cd backend
python -m alembic upgrade head          # aplica migrações pendentes
python -m alembic current               # revisão aplicada no banco
python -m alembic history               # histórico de revisões
python -m alembic upgrade head --sql    # revisa o SQL sem conectar
python -m alembic revision --autogenerate -m "descricao"  # após mudar models.py
```

A migração inicial cria a extensão PostGIS. Se a role do banco não for superusuária, crie a extensão antes como `postgres`:

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
```

Bancos que foram criados pela versão anterior (`Base.metadata.create_all`) não possuem `alembic_version`. O `init_db.py` detecta a tabela `restaurants` e executa `stamp head` uma única vez antes de aplicar as migrações.

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

Os testes cobrem feature engineering, contexto de turno, geração do dataset de treino, batch scoring, migrações Alembic, round-trip do modelo, query PostGIS, validação de schemas e contratos da API (sem depender de banco).

## Estrutura

```
backend/
├── alembic.ini                  # configuração do Alembic
├── alembic/
│   ├── env.py
│   └── versions/                # migrações versionadas
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
│       ├── batch.py             # scoring em lote por usuário/turno
│       └── train.py             # dataset, treino e métricas
├── models/                      # artefatos .joblib (gitignored)
├── scripts/
│   ├── init_db.py               # migrações Alembic + seed
│   └── batch_score.py           # CLI do batch scoring (cron/Task Scheduler)
└── tests/
```
