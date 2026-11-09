# 🍴 FoodFlow

**Plataforma de Delivery com Recomendação Personalizada**

Projeto de portfólio desenvolvido para a vaga de **Estágio/Residência em AI Engineer** no iFood. O FoodFlow é um app de delivery mobile-first inspirado em iFood, 99Food e Keeta, com **busca de restaurantes por proximidade** (PostGIS) e um **sistema de recomendação personalizado** (LightGBM + LightGBM + LoRA re-ranking) que aprende as preferências do usuário por turno — análogo ao sistema **Red** do iFood.

## 📌 Índice

- [Visão geral](#-visão-geral)
- [Stack técnica](#-stack-técnica)
- [Estrutura do repositório](#-estrutura-do-repositório)
- [Como rodar o projeto](#-como-rodar-o-projeto)
- [Endpoints da API](#-endpoints-da-api)
- [Telas implementadas](#-telas-implementadas)
- [Arquitetura de IA](#-arquitetura-de-ia)
- [Roadmap](#-roadmap)
- [Autor](#-autor)
- [Licença](#-licença)

---

## 🎯 Visão geral

O FoodFlow é uma plataforma completa de delivery que combina busca geoespacial, recomendação personalizada e experiência mobile-first.

### Funcionalidades principais

| Recurso | Descrição |
|---------|-----------|
| 📍 **Busca geoespacial** | Restaurantes próximos calculados com PostGIS (`ST_DWithin` + índice GIST) |
| ✨ **Recomendação personalizada** | LightGBM com features por turno (manhã/tarde/noite/madrugada) + re-ranking LoRA |
| 🎯 **A/B Test** | Experimento controlado: feed personalizado vs. feed por distância |
| 📊 **Monitoramento de drift** | PSI (Population Stability Index) por feature com alertas automáticos |
| 🔄 **Batch scoring** | Scores pré-calculados por usuário/turno gravados no Redis |
| ⭐ **Avaliações idempotentes** | Header `Idempotency-Key` para evitar duplicatas |
| 📱 **App mobile nativo** | React Native + Expo com todas as telas principais |

---

## 🧱 Stack técnica

### Frontend Web

| Camada | Tecnologia |
|--------|------------|
| Build | Vite 5 |
| UI | React 18 + TypeScript |
| Estilo | Tailwind CSS 3 |
| Roteamento | React Router 6 |
| Estado global | Zustand |
| Animações | Framer Motion |
| Ícones | Lucide React |
| Toasts | Sonner |
| Testes | Vitest + Testing Library |

### Backend

| Camada | Tecnologia |
|--------|------------|
| API | FastAPI (Python 3.11) |
| Banco | PostgreSQL 16 + PostGIS |
| Cache | Redis 7 |
| Recomendação | LightGBM + features por turno |
| Re-ranking | LoRA (transformers + peft + torch) |
| MLOps | Métricas de drift, A/B test, batch scoring |
| Observabilidade | X-Request-ID, X-Process-Time, readiness, métricas Prometheus |

### Mobile

| Camada | Tecnologia |
|--------|------------|
| Framework | React Native + Expo SDK 58 |
| Roteamento | Expo Router |
| Estado | Zustand |
| Geolocalização | expo-location |

---

## 📁 Estrutura do repositório

```
foodflow/
├── README.md
├── CHANGELOG.md
├── docker-compose.yml              # PostgreSQL/PostGIS + Redis + API
├── docker-compose.prod.yml         # Produção (Dockerfile.prod)
├── package.json                    # scripts delegados do monorepo
├── docs/
│   └── arquitetura-tecnica.md      # documentação técnica completa
├── backend/
│   ├── README.md
│   ├── Dockerfile                  # desenvolvimento
│   ├── Dockerfile.prod             # produção
│   ├── requirements.txt
│   ├── requirements-llmops.txt     # dependências opcionais de LLM
│   ├── alembic.ini                 # migrações
│   ├── alembic/                    # migrações versionadas
│   ├── app/
│   │   ├── main.py                 # FastAPI + lifespan + middleware
│   │   ├── models.py               # Restaurant, User, Order, Review, Event
│   │   ├── schemas.py
│   │   ├── crud.py                 # busca geoespacial, reviews, eventos
│   │   ├── seeds.py / seed_data.py # seed idempotente
│   │   ├── api/                    # restaurants, reviews, recommendations, events, drift, experiment
│   │   ├── cache/redis_client.py   # scores + Redis Stream + métricas A/B
│   │   ├── core/                   # config + constantes
│   │   └── ml/                     # features, recommender, train, reranker
│   ├── scripts/
│   │   ├── init_db.py              # migrações + seed
│   │   ├── batch_score.py          # batch scoring por usuário/turno
│   │   ├── drift_detect.py         # detecção de drift (PSI)
│   │   ├── train_lora.py           # fine-tuning LoRA
│   │   └── publish_lora.py         # publicação Hugging Face Hub
│   └── tests/
├── frontend/                       # Web (Vite + React + TS)
│   └── src/
│       ├── lib/                    # api, config, catalog, utils
│       ├── store/                  # Zustand (carrinho, pedidos, favoritos…)
│       ├── components/             # layout, home, restaurant, cart, common
│       └── pages/                  # Onboarding, Home, Search, RestaurantDetail…
├── mobile/                         # Mobile (React Native + Expo)
│   ├── src/app/                    # Expo Router (rotas baseadas em arquivos)
│   ├── src/store/                  # Zustand stores
│   ├── src/lib/                    # api, config, catalog, utils
│   └── src/types/                  # tipos TypeScript
└── mobile/                         # Mobile (React Native + Expo)
```

---

## ▶️ Como rodar o projeto

### Pré-requisitos

- **Node.js 18+** e **npm**
- **Python 3.11+** e **pip**
- **Docker** e **Docker Compose** (opcional, para rodar com containers)

### 1. Rodar com Docker Compose (recomendado)

```bash
# Na raiz do projeto
docker compose up -d
```

Isso sobe **PostgreSQL/PostGIS**, **Redis** e a **API FastAPI** com seed automático.

A API estará disponível em `http://localhost:8000` e o Swagger em `http://localhost:8000/docs`.

### 2. Rodar o frontend web

```bash
cd frontend
npm install
npm run dev
```

O app abrirá em `http://localhost:5173`.

### 3. Rodar o app mobile

```bash
cd mobile
npm install
npx expo start
```

Use o **Expo Go** no seu celular ou emulador para visualizar.

### 4. Rodar o backend localmente (sem Docker)

```bash
cd backend

# Criar ambiente virtual
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1  # PowerShell
# ou
source .venv/bin/activate     # Linux/Mac

# Instalar dependências
pip install -r requirements.txt

# Configurar variáveis de ambiente
Copy-Item .env.example .env     # Windows
# ou
cp .env.example .env            # Linux/Mac

# Inicializar banco (migrações + seed)
python scripts/init_db.py

# Subir a API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Deploy de produção

```bash
# Na raiz do projeto
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

Defina as variáveis de ambiente antes de subir (ou crie um `.env` na raiz):

```bash
DATABASE_URL=postgresql+asyncpg://foodflow:foodflow@postgres:5432/foodflow
REDIS_URL=redis://redis:6379/0
CORS_ORIGINS=https://app.seudominio.com,https://www.seudominio.com
```

O endpoint `/ready` serve como readiness probe e `/api/v1/metrics` expõe métricas no formato Prometheus.

---

## 🔌 Endpoints da API

### Restaurantes

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/api/v1/restaurants/search` | Busca geoespacial por lat/lon com raio e limite |
| `GET` | `/api/v1/restaurants/{id}` | Detalhe do restaurante com avaliações |

### Recomendações

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/api/v1/recommendations` | Recomendações personalizadas (parâmetro `experiment` opcional: `personalized` \| `distance`) |
| `POST` | `/api/v1/recommendations/train` | Treina o modelo LightGBM |
| `POST` | `/api/v1/recommendations/train-lora` | Treina o adapter LoRA de re-ranking |
| `POST` | `/api/v1/recommendations/rerank` | Re-executa re-ranking sobre scores em cache |

### Avaliações

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `POST` | `/api/v1/reviews` | Cria avaliação (idempotente via `Idempotency-Key`) |
| `PUT` | `/api/v1/reviews/{id}` | Atualiza avaliação do próprio usuário |
| `DELETE` | `/api/v1/reviews/{id}` | Remove avaliação do próprio usuário |

### Eventos

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `POST` | `/api/v1/events` | Coleta de eventos de interação do usuário |

### Monitoramento

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/health` | Health check + status do modelo |
| `GET` | `/ready` | Readiness (PostgreSQL, Redis, modelo) |
| `GET` | `/api/v1/metrics/recommendations` | Métricas de cache hit rate e estratégia |
| `GET` | `/api/v1/drift` | Relatório de drift de features (PSI) |
| `GET` | `/api/v1/experiment/ab-test` | Resultados do experimento A/B |
| `GET` | `/api/v1/metrics` | Métricas no formato Prometheus |

---

## 📱 Telas implementadas

### Web (React + Vite)

| Tela | Descrição |
|------|-----------|
| `/` | Onboarding com geolocalização |
| `/home` | Recomendados para você + Perto de você + Categorias |
| `/buscar` | Busca textual com filtros e resultados |
| `/restaurante/:id` | Detalhe do restaurante (cardápio, avaliações, sobre) |
| `/sacola` | Carrinho de compras com confirmação de pedido |
| `/pedidos` | Histórico de pedidos com status |
| `/perfil` | Dados do usuário, preferências, experimento A/B, eventos |

### Mobile (React Native + Expo)

| Tela | Descrição |
|------|-----------|
| Onboarding | Geolocalização e boas-vindas |
| Início | Recomendados e restaurantes próximos |
| Buscar | Busca textual |
| Detalhe do Restaurante | Cardápio, avaliações, informações |
| Sacola | Carrinho e finalização |
| Pedidos | Histórico de pedidos |
| Perfil | Preferências, experimento A/B, configurações |

---

## 🧠 Arquitetura de IA

O pipeline de recomendação segue o fluxo:

```
Eventos do app (cliques, pedidos, avaliações)
        ↓
PostgreSQL + Redis (feature store + cache)
        ↓
Pipeline de treino (LightGBM com features por turno)
        ↓
Batch scoring diário → Redis (chave: user_id:turno → scores)
        ↓
API /recommendations lê scores do Redis
        ↓
Re-ranking com adapter LoRA (quando disponível)
        ↓
Frontend recebe lista ordenada por score
```

### Componentes de IA implementados

- **LightGBM**: classificação binária (clicou/não clicou) com features por turno
- **LoRA**: fine-tuning de modelo pequeno para re-ranking de recomendações
- **Drift monitoring**: PSI (Population Stability Index) comparando treino vs. serving
- **A/B test**: comparação entre feed personalizado (ML) e feed por distância
- **Batch scoring**: scores pré-calculados por usuário/turno gravados no Redis

---

## 🗺️ Roadmap

### ✅ Concluído

- [x] Documentação técnica e arquitetura de IA
- [x] Frontend web (React + Vite + TypeScript + Tailwind)
- [x] App móvel (React Native + Expo)
- [x] Backend FastAPI + PostgreSQL/PostGIS + Redis
- [x] Busca geoespacial, detalhe e avaliações idempotentes
- [x] Coleta de eventos (PostgreSQL + Redis Stream)
- [x] Recomendação LightGBM com fallback por popularidade
- [x] Pipeline de treino e batch scoring
- [x] Migrations com Alembic
- [x] Observabilidade (request ID, latência, readiness, métricas)
- [x] Monitoramento de drift (PSI)
- [x] Re-ranking com LoRA
- [x] Experimento A/B de recomendações
- [x] Deploy de produção com Docker Compose

### 🔄 Em andamento / Próximos passos

- [ ] Deploy do backend na nuvem (AWS/GCP) com monitoramento

### 🎯 Longo prazo

- [ ] Publicação do adapter LoRA no Hugging Face Hub
- [ ] Artigo técnico publicado (Medium/dev.to) explicando a arquitetura

---

## 👤 Autor

**Gustavo Henrique Barbosa** — Software Developer / AI Engineer

- 📧 [barbosa.silva.gustavo56@gmail.com](mailto:barbosa.silva.gustavo56@gmail.com)
- 💼 [LinkedIn](https://www.linkedin.com/in/gustavo-henrique-barbosa-7571783b0/)
- 🐙 [GitHub](https://github.com/gustav0barbosa-dev)

---

## 📄 Licença

Este é um projeto de portfólio acadêmico, sem fins comerciais. Inspirado na experiência de produto do iFood, 99Food e Keeta, mas sem qualquer vínculo oficial com essas empresas.
