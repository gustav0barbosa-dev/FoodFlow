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
- [Simulação e cardápios sintéticos](#-simulação-e-cardápios-sintéticos)
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
| 🗺️ **Descoberta no OpenStreetMap** | Restaurantes reais próximos via Overpass API, com cache Redis e mapa Leaflet (sem chave); o detalhe persiste o estabelecimento e abre a mesma tela do catálogo |
| 🍽️ **Cardápio por restaurante** | `menu_items` via `GET /api/v1/restaurants/{id}/menu`; itens gerados por script têm `source=synthetic` e aparecem marcados como “Exemplo” na UI |
| 🧠 **Histórico no recomendador** | `VIEW`, `CLICK`, `FAVORITE` e `PURCHASE` alimentam features e afinidade sem retreinar o modelo |
| ✨ **Recomendação personalizada** | LightGBM com features por turno (manhã/tarde/noite/madrugada); re-ranking LoRA opcional |
| 🎯 **A/B Test** | Experimento controlado: feed personalizado vs. feed por distância |
| 🧪 **Simulação de usuários** | Agentes sintéticos com personas geram backfill/live, comparam grupos contra o oráculo e separam qualidade de ordenação de cobertura de seleção |
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
| Simulação e cardápios sintéticos | Scripts idempotentes (`enrich_restaurants.py`, `generate_synthetic_restaurants.py`, `simulate.py`) com `--dry-run`, `--yes`, bloqueio de produção e banco separado recomendado |
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
| Mapas | Leaflet + React-Leaflet (tiles OpenStreetMap) |
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
| Descoberta geográfica | OpenStreetMap + Overpass API |
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
│   ├── arquitetura-tecnica.md      # documentação técnica completa
│   ├── especificacao-metricas-v2.md
│   └── simulacao.md                # cardápios sintéticos, agentes e métricas
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
│   │   ├── models.py               # Restaurant, MenuItem, User, Order, Review, Interaction…
│   │   ├── schemas.py
│   │   ├── crud.py                 # busca geoespacial, cardápio, reviews, eventos
│   │   ├── seeds.py / seed_data.py # seed idempotente
│   │   ├── api/                    # restaurants, reviews, recommendations, events, drift, experiment
│   │   ├── cache/redis_client.py   # scores + Redis Stream + métricas A/B
│   │   ├── core/                   # config + constantes
│   │   ├── simulation/             # personas, funil, cardápios e guardas de escrita
│   │   └── ml/                     # features, recommender, train, lora_training, lora_evaluation, reranker
│   ├── scripts/
│   │   ├── init_db.py              # migrações + seed
│   │   ├── ingest_osm.py           # ingestão por bbox (Overpass)
│   │   ├── enrich_restaurants.py   # cardápio sintético + frete/prazo
│   │   ├── generate_synthetic_restaurants.py  # catálogo sintético (plano B ao OSM)
│   │   ├── simulate.py             # backfill, live, report e cleanup
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

Para cardápio sintético no ambiente Docker (necessário para testar o fluxo de pedido):

```bash
docker compose run --rm backend python scripts/enrich_restaurants.py --yes
```

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

# Opcional: cardápio sintético para testar o fluxo de pedido
python scripts/enrich_restaurants.py --yes

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
# Descoberta de restaurantes reais via OpenStreetMap + Overpass API.
# Instâncias públicas não exigem chave; use uma instância própria em produção
# com tráfego elevado.
OVERPASS_API_URL=https://overpass-api.de/api/interpreter
OVERPASS_CACHE_TTL_SECONDS=300
OVERPASS_TIMEOUT_SECONDS=25
OVERPASS_USER_AGENT=FoodFlow/0.2
# Opcional: habilita o re-ranker LoRA (requer requirements-llmops.txt e adapter)
ENABLE_LORA_RERANKER=false
# Opcional: Street View. A chave fica apenas no backend; sem ela o bloco fica oculto.
GOOGLE_MAPS_API_KEY=
STREET_VIEW_TIMEOUT_SECONDS=5
STREET_VIEW_RADIUS_METERS=50
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
| `GET` | `/api/v1/restaurants/nearby` | Restaurantes reais próximos via OpenStreetMap/Overpass (`lat`, `lon`, `radius`, `category`); sem cardápio/entrega |
| `GET` | `/api/v1/restaurants/osm/{osm_type}/{osm_id}` | Detalhe do OSM (persiste no primeiro acesso; `refresh=true` reconsulta a Overpass) |
| `GET` | `/api/v1/restaurants/{id}` | Detalhe do restaurante com avaliações |
| `GET` | `/api/v1/restaurants/{id}/menu` | Cardápio do restaurante (itens com `source=synthetic` são exemplos gerados por script) |

### Recomendações

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/api/v1/recommendations` | Recomendações com `mode=experiment` (padrão, atribuição persistente) ou `mode=demo` (permite `experiment` manual: `baseline` \| `personalized` \| `distance`); devolve `X-Experiment-Group`, `X-Experiment-Mode`, `X-Experiment-Version`, `X-Recommendation-Id`, `X-Model-Version` e `X-Recommendation-Strategy` |
| `POST` | `/api/v1/recommendations/train` | Retorna `202`; o treino é offline (`python -m app.ml.train`) |
| `POST` | `/api/v1/recommendations/train-lora` | Solicita treino LoRA offline (`202`; execute `python scripts/train_lora.py`) |
| `POST` | `/api/v1/recommendations/rerank` | Re-executa re-ranking sobre scores em cache |

### Usuários

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/api/v1/users/{id}` | Perfil do usuário (nome, e-mail e preferências alimentares) |
| `GET` | `/api/v1/users/{id}/preferences` | Perfil derivado do histórico (categorias, cozinhas, restaurantes) |
| `POST` | `/api/v1/interactions` | Registra `IMPRESSION`, `VIEW`, `VIEW_DETAILS`, `CLICK`, `FAVORITE`, `PURCHASE` ou `DISMISS` com contexto do experimento (idempotência opcional) |

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
| `GET` | `/api/v1/experiment/ab-test` | Métricas dos 3 grupos a partir dos eventos no banco (Redis só como diagnóstico), com coorte válida, contaminação, IC bootstrap por usuário e plano de amostra |
| `GET` | `/api/v1/ml/metrics` | Relatório v3 do último treino offline (split temporal, P@K/R@K/NDCG@K/MAP@K, ILD, novidade, PR AUC/Brier/Log Loss, calibração, sensibilidade, política temporal, rolling-window, baselines e comparação com produção) |
| `GET` | `/api/v1/street-view/metadata` | Disponibilidade do panorama nas coordenadas |
| `GET` | `/api/v1/street-view/image` | Proxy da imagem do Street View (chave somente no backend) |
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
| `/restaurante/osm/:osmType/:osmId` | Detalhe de restaurante do OpenStreetMap na mesma tela (apenas dados disponíveis) |
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
Interações (IMPRESSION/VIEW/VIEW_DETAILS/CLICK/FAVORITE/PURCHASE/DISMISS) → perfil derivado + features
        ↓
PostgreSQL + Redis (feature store + cache)
        ↓
Pipeline de treino (LightGBM com features por turno)
        ↓
Batch scoring diário → Redis (chave: user_id:turno → scores)
        ↓
API /recommendations lê scores do Redis e aplica afinidade recente (grupo personalized)
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

- **LightGBM**: classificação binária do alvo `purchased` (compra/pedido observado, não clique) com features por turno
- **Interações**: `IMPRESSION`/`VIEW`/`VIEW_DETAILS`/`CLICK`/`FAVORITE`/`PURCHASE`/`DISMISS` com pesos, decaimento de recência e contexto A/B (grupo, posição e versão do modelo); afinidade reordena o ranking sem retreinar
- **LoRA**: extensão experimental de re-ranking; carregada apenas com `ENABLE_LORA_RERANKER=true` e dependências de LLMOps instaladas. Sem adapter, usa fallback determinístico.
- **Drift monitoring**: PSI (Population Stability Index) comparando treino vs. serving
- **A/B test**: três grupos estáveis — `baseline` (popularidade), `personalized` (LightGBM + afinidade) e `distance`; métricas lidas dos eventos oficiais no banco, com fase explícita (`collecting`/`insufficient_data`/`ready`/`statistical_analysis`). `ready` é apenas volume mínimo descritivo; a inferência só ocorre em `statistical_analysis`, sobre a **coorte válida** (usuários contaminados excluídos), com **bootstrap agrupado por usuário**, intervalo de confiança e correção de Bonferroni. O `baseline` precisa de volume mínimo; sem ele a inferência fica bloqueada. O p-valor vem de distribuição nula sob H0 e a evidência principal é o IC 95% da diferença. O teste z por impressão é apenas fallback explícito. Modo `demo` fica fora das métricas oficiais.
- **Métricas de treino (schema v3)**: alvo `purchased`, negativos observados × não observados, split temporal por contexto, P@K, R@K, NDCG@K, MAP@K, ILD@K, novidade, cobertura de catálogo/usuários, IC bootstrap por usuário, ROC AUC/PR AUC/Brier/Log Loss, calibração (ECE), sensibilidade a negativos observados/não observados, política temporal das features, rolling-window opcional, baselines com os mesmos candidatos, comparação com o modelo em produção, hash do dataset e decisão de promoção/rollback em `GET /api/v1/ml/metrics`
- **Batch scoring**: scores pré-calculados por usuário/turno gravados no Redis

### Avaliação e métricas (v2/v3)

A especificação completa está em
[`docs/especificacao-metricas-v2.md`](docs/especificacao-metricas-v2.md).
Pontos centrais:

- alvo `purchased` (compra observada) e negativos não observados com peso
  reduzido apenas no treino;
- métricas de ranking por contexto com macro-média, IC bootstrap por usuário,
  ILD e novidade;
- ROC AUC, PR AUC, Brier, Log Loss e calibração com disponibilidade própria;
- sensibilidade a negativos observados/não observados, sem substituir a
  avaliação principal do catálogo inteiro;
- A/B com coorte válida, baseline obrigatório, inferência por usuário e plano
  de amostra;
- atributos atuais do restaurante documentados como risco de vazamento
  temporal; `--strict-temporal` os exclui;
- avaliação rolling-window walk-forward opcional (`--rolling-window`);
- comparação do candidato com o modelo em produção nos mesmos contextos;
- treino `--source seed` é apenas avaliação e **nunca** substitui o modelo em
  produção.

### Avaliação offline do LoRA

`python scripts/evaluate_lora.py --source seed` treina em pedidos antigos e avalia em pedidos recentes (split temporal), sem vazamento de dados e sem sobrescrever o adapter de serving. Os números abaixo são **avaliação offline do seed**, não treino com dados reais de produção. Resultado com a janela de 7 dias:

| Estratégia | AUC | NDCG@5 |
|---|---|---|
| Popularidade | 0.5051 | 0.3268 |
| **LightGBM** | **0.6727** | **0.5002** |
| LoRA | 0.3574 | 0.2018 |
| Híbrido (LightGBM + LoRA) | 0.5903 | 0.4223 |

O LoRA não superou o LightGBM em nenhuma das janelas testadas (7, 10 e 14 dias). Por isso ele permanece **experimental e desabilitado por padrão**; o seed pequeno torna os números indicativos, e o comando aceita `--source db` para reavaliar com dados reais.

> **Atenção:** o adapter publicado no Hugging Face usa base Llama 3.2 1B e o card reporta NDCG@5 0.72 → 0.79. Esses números não são reproduzíveis pelo runtime atual (`all-MiniLM-L6-v2`) e o card contém placeholders. Alinhe base/target modules e reavalie antes de habilitar o LoRA em produção.

---

## 🧪 Simulação e cardápios sintéticos

O OSM e o Street View não fornecem cardápio. Para destravar o fluxo de pedido e
testar o recomendador sem APIs pagas, o projeto inclui cardápios sintéticos e um
simulador de usuários com personas. **Tudo é sintético** e serve para validar
pipeline, A/B e regressões — não é evidência de desempenho com pessoas reais.

```bash
cd backend
python scripts/init_db.py                          # aplica até a migração 0006

# Restaurantes reais (OSM) e/ou sintéticos como plano B
python scripts/ingest_osm.py --south -23.55 --west -46.82 --north -23.51 --east -46.77
python scripts/generate_synthetic_restaurants.py --count 150 --dry-run
python scripts/generate_synthetic_restaurants.py --count 150 --yes

# Cardápio sintético e preenchimento de frete/prazo neutros
python scripts/enrich_restaurants.py --fill-delivery --dry-run
python scripts/enrich_restaurants.py --fill-delivery --yes

# Histórico retroativo, treino e agentes usando a API real
python scripts/simulate.py backfill --users 300 --days 21 --run-id exp1 --yes
python -m app.ml.train --source db
python scripts/simulate.py live --run-id exp1 --rounds 5 --yes
python scripts/simulate.py live --run-id exp1-unseen --unseen-users --rounds 5 --yes

# Relatório e limpeza auditável
python scripts/simulate.py report --run-id exp1 --by-cohort --by-persona
python scripts/simulate.py cleanup --run-id exp1 --dry-run
python scripts/simulate.py cleanup --run-id exp1 --include-restaurants --yes
```

**Segurança:** os comandos que escrevem exibem o banco de destino, exigem
`--yes`, aceitam `--dry-run` sem gravar, bloqueiam produção (`FOODFLOW_ENV` ou
nome do banco com `prod`) e exigem `--allow-remote-db` para hosts remotos. Rode
sempre em um banco separado (`DATABASE_URL=.../foodflow_sim`): o treino lê todas
as linhas e dados simulados contaminariam um treino com usuários reais.

**Métricas:** o relatório separa duas perguntas:

- `ordenacao servida` (NDCG@10): a API ordenou bem os restaurantes que mostrou?
- `recall do top-10 ideal` e `cobertura do oraculo`: a seleção contra **todos**
  os candidatos elegíveis foi boa? A cobertura compara compras esperadas da
  lista servida com as do top-10 ideal (1.0 = perfeito).

No modo `live`, o universo elegível é calculado **antes** de chamar a API; usar a
própria resposta como universo mediria apenas a ordenação. Os ICs usam bootstrap
de **usuários** (não de sessões), e o relatório aceita `--by-persona`,
`--by-cohort` e `--by-period day|week|month`.

**Coortes e idempotência:** `--unseen-users` cria uma coorte sem histórico no
treino; `--require-unseen` falha se ela não existir. Restaurantes sintéticos têm
UUID determinístico, o backfill bloqueia um `run_id` já usado, e pedidos,
avaliações e restaurantes guardam `simulation_run_id`/`simulation_mode` para
auditoria. O `cleanup` grava um JSON com banco, filtros e contagens.

Detalhes completos em [`docs/simulacao.md`](docs/simulacao.md).

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
- [x] Avaliação offline do LoRA com AUC/NDCG@5 no seed (LightGBM superior; LoRA mantido experimental; não é evidência de produção)
- [x] Feed personalizado no mobile consumindo `GET /recommendations`
- [x] Experimento A/B de recomendações
- [x] Descoberta no OpenStreetMap com detalhe persistido e mesma tela do catálogo
- [x] Histórico de interações (visualização, clique, favorito e compra) no recomendador
- [x] Cardápios sintéticos (`menu_items`) com endpoint de cardápio e aviso de item de exemplo
- [x] Simulador de usuários com backfill/live, coortes `known`/`unseen`, métricas de ordenação vs. seleção e cleanup auditável
- [x] Guardas de escrita nos scripts (`--dry-run`, `--yes`, bloqueio de produção e host remoto)
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
