# FoodFlow Backend

API REST em **FastAPI** com **PostgreSQL 16 + PostGIS** e **Redis**, seguindo a arquitetura documentada em `docs/arquitetura-tecnica.md`.

## Stack

| Camada | Tecnologia |
|--------|------------|
| API | FastAPI (Python 3.11) |
| Banco | PostgreSQL 16 + PostGIS |
| Cache | Redis 7 |
| ORM | SQLAlchemy 2.0 (async) |
| Geo | GeoAlchemy2 |

## Endpoints (Fase 1)

| Método | Endpoint | Finalidade |
|--------|----------|------------|
| `GET` | `/health` | Health check |
| `GET` | `/api/v1/restaurants/search?lat=&lon=&radius_km=` | Busca geoespacial (PostGIS `ST_DWithin`) |
| `GET` | `/api/v1/restaurants/{id}` | Detalhes do restaurante |
| `POST` | `/api/v1/events` | Coleta de eventos para o recomendador |

## Como rodar

### Com Docker Compose (recomendado)

```bash
# Na raiz do projeto
docker compose up -d
```

Isso sobe PostgreSQL + PostGIS, Redis e o backend, e roda o seed automaticamente.

### Localmente (sem Docker)

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env  # ajuste as URLs se necessário
python scripts/init_db.py
uvicorn app.main:app --reload
```

A API estará disponível em `http://localhost:8000`.

## Testando o endpoint de busca

```bash
curl "http://localhost:8000/api/v1/restaurants/search?lat=-23.5325&lon=-46.7939&radius_km=5"
```

## Estrutura

```
backend/
├── Dockerfile
├── requirements.txt
├── .env.example
├── app/
│   ├── __init__.py
│   ├── core/
│   │   └── config.py
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── crud.py
│   ├── seeds.py
│   └── api/
│       ├── __init__.py
│       ├── restaurants.py
│       └── events.py
└── scripts/
    └── init_db.py
```
