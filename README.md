# 🍴 FoodFlow

**Plataforma de Delivery com Recomendação Personalizada**

Projeto de portfólio desenvolvido para a vaga de **Estágio/Residência em AI Engineer** no iFood. O FoodFlow é um app de delivery mobile-first inspirado em iFood, 99Food e Keeta, com **busca de restaurantes por proximidade** (PostGIS) e um **sistema de recomendação personalizado** (LightGBM + re-ranking LoRA opcional) que aprende as preferências do usuário por turno — análogo ao sistema **Red** do iFood.

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
| ✨ **Recomendação personalizada** | LightGBM com features por turno (manhã/tarde/noite/madrugada); re-ranking LoRA opcional |
| 🎯 **A/B Test** | Experimento controlado: feed personalizado vs. feed por distância |
| 📱 **Feed personalizado no mobile** | Home consome `GET /recommendations` com fallback para catálogo/mock |
| 📊 **Monitoramento de drift** | PSI (Population Stability Index) por feature com alertas automáticos |
| 🔄 **Batch scoring** | Scores pré-calculados por usuário/turno gravados no Redis |
| ⭐ **Avaliações idempotentes** | Header `Idempotency-Key` para evitar duplicatas |
| 📱 **App mobile nativo** | React Native + Expo; catálogo, detalhe e perfil integrados à API com fallback local |

### Status de integração

| Componente | Estado |
|---|---|
| Frontend web | Integrado à API (`src/lib/api.ts`), com fallback local |
| Backend | LightGBM é o modelo principal; sem artefato usa popularidade |
| Re-ranking LoRA | Experimental e opcional (`ENABLE_LORA_RERANKER=true`); avaliação offline mostra que não supera o LightGBM no seed |
| Mobile | Catálogo, detalhe, perfil e feed de recomendações via API; mock como fallback offline |
| Persistência de modelos | Volume `backend_models` em produção; fallback quando ausente |
| Docker Compose | Script de validação end-to-end e workflow de CI adicionados; execução local pendente por ausência de Docker neste ambiente |

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
| Re-ranking | LoRA experimental (transformers + peft + torch) |
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
├── scripts/
│   └── validate_compose.sh         # validação end-to-end do Compose (dev + prod)
├── .github/workflows/
│   └── compose-validation.yml      # validação do Compose em runner com Docker
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
│   │   └── ml/                     # features, recommender, train, lora_training, lora_evaluation, reranker
│   ├── scripts/
│   │   ├── init_db.py              # migrações + seed
│   │   ├── batch_score.py          # batch scoring por usuário/turno
│   │   ├── drift_detect.py         # detecção de drift (PSI)
│   │   ├── train_lora.py           # CLI de fine-tuning LoRA (lógica em app/ml/lora_training.py)
│   │   ├── evaluate_lora.py        # avaliação offline do LoRA (AUC/NDCG@5)
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
│   ├── src/data/mockData.ts        # fallback local quando a API está offline
│   └── src/types/                  # tipos TypeScript
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

Isso sobe **PostgreSQL/PostGIS**, **Redis** e a **API FastAPI**. As migrações e o seed são aplicados por um serviço `migrate` pontual antes de a API iniciar.

A API estará disponível em `http://localhost:8000` e o Swagger em `http://localhost:8000/docs`.

Para validar migrate, PostGIS, Redis, endpoints e o volume `backend_models` de ponta a ponta em uma máquina com Docker:

```bash
bash scripts/validate_compose.sh
```

O mesmo script roda no workflow **Compose validation** (`.github/workflows/compose-validation.yml`) em um runner do GitHub Actions.

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
# Opcional: habilita o re-ranker LoRA (requer requirements-llmops.txt e adapter)
ENABLE_LORA_RERANKER=false
```

O endpoint `/ready` serve como readiness probe e `/api/v1/metrics` expõe métricas no formato Prometheus.

Em produção, os modelos ficam no volume nomeado `backend_models` (`/app/models`). Treine-os
em um job separado (por exemplo, `docker compose run --rm backend python scripts/train_lora.py`)
para que o artefato sobreviva à recriação do container.

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
| `POST` | `/api/v1/recommendations/train-lora` | Solicita treino LoRA offline (`202`; execute `python scripts/train_lora.py`) |
| `POST` | `/api/v1/recommendations/rerank` | Re-executa re-ranking sobre scores em cache |

### Usuários

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/api/v1/users/{id}` | Perfil do usuário (nome, e-mail e preferências alimentares) |

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
Re-ranking LoRA opcional (ENABLE_LORA_RERANKER=true) ou fallback determinístico
        ↓
Frontend recebe lista ordenada por score
```

## 🤖 LLMOps (Hugging Face)

O adaptador LoRA responsável pelo re-ranking personalizado das recomendações foi treinado, publicado e testado publicamente no Hugging Face Hub.

👉 **[Acesse o modelo: barbosaDev01/foodflow-llm-reranker-lora](https://huggingface.co/barbosaDev01/foodflow-llm-reranker-lora)**

- **Arquitetura:** Fine-tuning LoRA sobre o modelo base `sentence-transformers/all-MiniLM-L6-v2`.
- **Tarefa:** Re-ranking de restaurantes baseado no contexto do usuário (turno, preferências e distância).
- **Teste de Inferência:** O modelo foi carregado e validado no Google Colab.
  ![Teste do Modelo no Colab](docs/screenshots/huggingface-colab.png)

### Componentes de IA implementados

- **LightGBM**: classificação binária (clicou/não clicou) com features por turno
- **LoRA**: extensão experimental de re-ranking; carregada apenas com `ENABLE_LORA_RERANKER=true` e dependências de LLMOps instaladas. Sem adapter, usa fallback determinístico.
- **Drift monitoring**: PSI (Population Stability Index) comparando treino vs. serving
- **A/B test**: comparação entre feed personalizado (ML) e feed por distância
- **Batch scoring**: scores pré-calculados por usuário/turno gravados no Redis

### Avaliação offline do LoRA

`python scripts/evaluate_lora.py --source seed` treina em pedidos antigos e avalia em pedidos recentes (split temporal), sem vazamento de dados e sem sobrescrever o adapter de serving. Resultado com a janela de 7 dias:

| Estratégia | AUC | NDCG@5 |
|---|---|---|
| Popularidade | 0.5051 | 0.3268 |
| **LightGBM** | **0.6727** | **0.5002** |
| LoRA | 0.3574 | 0.2018 |
| Híbrido (LightGBM + LoRA) | 0.5903 | 0.4223 |

O LoRA não superou o LightGBM em nenhuma das janelas testadas (7, 10 e 14 dias). Por isso ele permanece **experimental e desabilitado por padrão**; o seed pequeno torna os números indicativos, e o comando aceita `--source db` para reavaliar com dados reais.

> **Atenção:** o adapter publicado no Hugging Face usa base Llama 3.2 1B e o card reporta NDCG@5 0.72 → 0.79. Esses números não são reproduzíveis pelo runtime atual (`all-MiniLM-L6-v2`) e o card contém placeholders. Alinhe base/target modules e reavalie antes de habilitar o LoRA em produção.

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
- [x] Estrutura de re-ranking com LoRA (opcional; fallback por padrão)
- [x] Avaliação offline do LoRA com AUC/NDCG@5 (LightGBM superior; LoRA mantido experimental)
- [x] Feed personalizado no mobile consumindo `GET /recommendations`
- [x] Experimento A/B de recomendações
- [x] Script e workflow de validação do Docker Compose

### 🔄 Em andamento / Próximos passos

- [ ] Deploy do backend na nuvem (AWS/GCP) com monitoramento

### 🎯 Longo prazo

- [x] Publicação do adapter LoRA no Hugging Face Hub (alinhamento ao modelo base do runtime pendente)
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
