# 🍴 FoodFlow — Plataforma de Delivery com Recomendação Personalizada

Projeto de portfólio construído para a vaga de **Estágio/Residência em AI Engineer** no iFood. O objetivo é desenvolver um app de delivery mobile-first (inspirado em iFood, 99Food e Keeta) com **busca de restaurantes por proximidade** e um **sistema de recomendação personalizado** que aprende as preferências do usuário — análogo ao sistema **Red** do iFood.

> ⚠️ **Status atual:** frontend MVP e backend MVP (Fase 1/2) implementados. O frontend ainda consome dados mockados; a integração com a API e o pipeline de LLMOps são os próximos passos. Este README documenta o que já foi entregue e o que vem a seguir.

---

## 📌 Índice

- [Visão geral](#-visão-geral)
- [O que já foi entregue](#-o-que-já-foi-entregue)
- [Stack técnica](#-stack-técnica)
- [Estrutura do repositório](#-estrutura-do-repositório)
- [Como rodar o projeto](#-como-rodar-o-projeto)
- [Telas implementadas](#-telas-implementadas)
- [Arquitetura de IA planejada (backend)](#-arquitetura-de-ia-planejada-backend)
- [Roadmap](#-roadmap)
- [Conexão com a vaga de AI Engineer](#-conexão-com-a-vaga-de-ai-engineer)

---

## 🎯 Visão geral

**FoodFlow** é um app de delivery que:

- 📍 Localiza restaurantes próximos ao usuário (geolocalização).
- 🍽️ Exibe informações completas: nome, endereço, telefone, avaliações, cardápio, taxa de entrega e tempo estimado.
- ✨ Personaliza o feed de descoberta com base no histórico e preferências do usuário — destacado pela badge **“✨ Para você”**.
- 📱 Funciona como aplicativo mobile (React Native previsto; protótipo atual em React + Vite simulando viewport mobile).

---

## ✅ O que já foi entregue

### 1. Documentação técnica de desenvolvimento

Documento completo cobrindo:

- Arquitetura de alto nível (mobile app + API + PostgreSQL/PostGIS + Redis + pipeline de ML).
- Modelagem de dados geoespacial (PostGIS, `ST_DWithin`, índices GIST).
- Estratégia de recomendação inspirada no **Red** do iFood (LightGBM + features por turno + medoides + batch scoring via Redis).
- Uso de **LLMs** para enriquecimento de features e re-ranking (LoRA, embeddings, orquestração de agentes).
- Pipeline de **MLOps/LLMOps** (MLflow, DVC, batch scoring, monitoramento de drift, A/B test).
- Considerações de **LGPD** (localização e dados sensíveis).
- Mapeamento explícito de cada requisito da vaga → solução proposta.

📄 *Local:* documentação entregue junto ao projeto (arquivo `.md` separado ou seção no repositório).

### 2. Prompt para o Lovable (protótipo frontend)

Prompt estruturado para geração do protótipo visual no [Lovable](https://lovable.dev), contendo:

- Identidade visual (cores, tipografia, componentes).
- Especificação detalhada das **6 telas** (Onboarding, Home, Buscar, Detalhe do Restaurante, Pedidos, Perfil).
- Estrutura de mock data, comportamentos esperados e critérios de sucesso.
- Restrições de escopo (sem auth real, sem backend, sem pagamento real).

### 3. Esqueleto do projeto no VSCode (este repositório)

App **funcional e navegável** construído do zero com:

- ✅ Configuração completa: **Vite + React 18 + TypeScript + Tailwind CSS + React Router + Zustand + Framer Motion + Lucide + Sonner**.
- ✅ **Moldura de celular** no desktop (`MobileFrame`) — o app aparece centralizado em uma viewport de ~430px, simulando um dispositivo real.
- ✅ **Bottom tab bar** funcional com 4 abas: Início, Buscar, Pedidos, Perfil.
- ✅ **Todas as telas principais** navegáveis, com transições, estados de loading (skeletons) e toasts.
- ✅ **Store de carrinho** (Zustand) com contador reativo no bottom nav.
- ✅ **Mock data tipada** com 12 restaurantes completos (menus + avaliações).
- ✅ **Busca e filtros client-side** funcionando.
- ✅ **Design system** vermelho `#EA1D2C` (iFood-like), cards arredondados, tipografia Inter/Poppins.

### 4. Backend MVP (FastAPI + PostGIS + Redis + LightGBM)

- ✅ **Busca geoespacial** com `ST_DWithin`, índice GIST e distância calculada na mesma query.
- ✅ **Detalhe do restaurante** com últimas 10 avaliações agregadas.
- ✅ **Avaliações idempotentes** via header `Idempotency-Key` e atualização transacional de `average_rating`/`review_count`.
- ✅ **Coleta de eventos** em PostgreSQL + Redis Stream.
- ✅ **Recomendação LightGBM** com features por turno (one-hot do turno solicitado), medoides ponderados por recência e `1 positivo : 3 negativos` no treino.
- ✅ **Serving com cache Redis** e fallback por popularidade para cold start.
- ✅ **Batch scoring** por usuário/turno via `scripts/batch_score.py`, com agendamento por cron/Task Scheduler ou profile `batch` do Docker Compose.
- ✅ **Seed idempotente**: 12 restaurantes, 4 usuários, 30 pedidos e 36 avaliações.
- ✅ **42 testes automatizados** cobrindo features, treino, modelo, batch scoring, query PostGIS, schemas e API.

📄 Detalhes em [`backend/README.md`](backend/README.md).

---

## 🧱 Stack técnica

### Frontend (atual)

| Camada | Tecnologia |
|---|---|
| Build | **Vite 5** |
| UI | **React 18 + TypeScript** |
| Estilo | **Tailwind CSS 3** |
| Roteamento | **React Router 6** |
| Estado global | **Zustand** |
| Animações | **Framer Motion** |
| Ícones | **Lucide React** |
| Toasts | **Sonner** |
| Fontes | **Inter + Poppins** (Google Fonts) |

### Backend (MVP implementado)

| Camada | Tecnologia |
|---|---|
| API | **FastAPI (Python 3.11)** |
| Banco | **PostgreSQL 16 + PostGIS** |
| Cache | **Redis 7** (scores + Redis Stream) |
| Recomendação | **LightGBM** + features por turno |
| LLMs | **LoRA + Hugging Face** (re-ranking / enriquecimento — roadmap) |
| MLOps | **MLflow + DVC** (roadmap) |
| Mobile nativo | **React Native + Expo** (migração do protótipo) |

---

## 📁 Estrutura do repositório

```
foodflow/
├── README.md
├── CHANGELOG.md
├── docker-compose.yml              ← PostgreSQL/PostGIS + Redis + API
├── package.json                    ← scripts delegados do monorepo
├── docs/
│   └── arquitetura-tecnica.md      ← documentação técnica completa
├── backend/
│   ├── README.md
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── app/
│   │   ├── main.py                 ← FastAPI + lifespan
│   │   ├── models.py               ← Restaurant, User, Order, Review, Event
│   │   ├── schemas.py
│   │   ├── crud.py                 ← busca geoespacial, reviews, eventos
│   │   ├── seeds.py / seed_data.py ← seed idempotente
│   │   ├── api/                    ← restaurants, reviews, recommendations, events
│   │   ├── cache/redis_client.py   ← scores + Redis Stream
│   │   ├── core/                   ← config + constantes
│   │   └── ml/                     ← features, recommender, train
│   └── tests/
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.ts
    ├── tailwind.config.ts
    └── src/
        ├── main.tsx
        ├── App.tsx                 ← rotas + moldura de celular
        ├── lib/                    ← utils, busca, eventos, métricas
        ├── types/                  ← Restaurant, MenuItem, Review, CartLine
        ├── data/mockData.ts        ← 12 restaurantes mockados
        ├── store/                  ← Zustand (carrinho, pedidos, favoritos…)
        ├── components/             ← layout, home, restaurant, cart, common
        └── pages/                  ← Onboarding, Home, Search, RestaurantDetail…
```

---

## ▶️ Como rodar o projeto

### Pré-requisitos

- **Node.js 18+** ([download](https://nodejs.org))
- **npm** (vem com Node)
- **VSCode** com extensões recomendadas: *ESLint*, *Tailwind CSS IntelliSense*, *Prettier*

### Passo a passo

```bash
# 1. Clone / abra o projeto
cd foodflow

# 2. Instale as dependências
npm install

# 3. Rode em modo de desenvolvimento
npm run dev
```

O app abrirá em **`http://localhost:5173`**.

### ⚠️ Problema comum no Windows (PowerShell)

Se aparecer o erro:

> `npm.ps1 não pode ser carregado porque a execução de scripts foi desabilitada`

Execute uma vez no PowerShell:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Feche e reabra o terminal. Alternativa: use **Command Prompt (cmd)** no terminal do VSCode.

### Rodando o backend

Com Docker Compose (recomendado):

```bash
# Na raiz: sobe PostgreSQL/PostGIS, Redis e a API (seed automático)
docker compose up -d
```

Alternativa local:

1. **Criar banco e extensão PostGIS.** Abra o `psql` como superusuário:

```sql
psql -U postgres
CREATE ROLE foodflow LOGIN PASSWORD 'foodflow';
CREATE DATABASE foodflow OWNER foodflow;
\connect foodflow
CREATE EXTENSION IF NOT EXISTS postgis;
\q
```

Se o PostGIS não estiver instalado no PostgreSQL local, instale pelo Stack Builder do instalador do PostgreSQL. Verifique a conexão:

```bash
pg_isready -U foodflow -d foodflow
```

2. **Subir o Redis (opcional).** No WSL:

```bash
wsl sudo service redis-server start
wsl redis-cli ping
```

Resposta esperada: `PONG`. Se não quiser subir o Redis agora, pule esta etapa.

3. **Rodar o backend:**

```powershell
cd C:\Users\gsilva\Documents\FoodFlow\backend

# Criar o ambiente virtual com Python 3.11
py -3.11 -m venv .venv

# Ativar (se o PowerShell bloquear, veja a observação abaixo)
.\.venv\Scripts\Activate.ps1

# Instalar dependências
python -m pip install --upgrade pip
pip install -r requirements.txt

# Criar o .env local
Copy-Item .env.example .env

# Criar tabelas e rodar o seed idempotente
python scripts/init_db.py

# Subir a API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Saída esperada do seed:

```text
✅ Banco inicializado: {'restaurants': 12, 'users': 4, 'orders_created': 30, 'reviews_created': 36}
```

Se o PowerShell bloquear a ativação:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Ou use o Python do venv diretamente:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

A API estará em `http://localhost:8000` e o Swagger em `http://localhost:8000/docs`.

4. **Rodar os testes.** Os testes não precisam de PostgreSQL nem Redis:

```powershell
cd C:\Users\gsilva\Documents\FoodFlow\backend
pip install -r requirements-dev.txt
pytest -q
```

Resultado esperado: `42 passed`.

5. **Verificação rápida da API.** Com a API rodando:

```bash
curl.exe http://localhost:8000/health

curl.exe "http://localhost:8000/api/v1/restaurants/search?lat=-23.5325&lon=-46.7939&radius_km=5"

# Treinar o modelo com os pedidos do seed
curl.exe -X POST "http://localhost:8000/api/v1/recommendations/train"

# Testar recomendação para a usuária Ana Souza
curl.exe "http://localhost:8000/api/v1/recommendations?user_id=a54a52c3-8543-56d3-8e4b-6d8220667bd5&lat=-23.5325&lon=-46.7939&turno=tarde"

# Calcular/gravar scores em lote para todos os usuários e turnos
cd C:\Users\gsilva\Documents\FoodFlow\backend
.\.venv\Scripts\python.exe scripts\batch_score.py
```

Documentação interativa: **`http://localhost:8000/docs`**.

### Scripts disponíveis

| Comando | Descrição |
|---|---|
| `npm run dev:web` | Frontend em modo desenvolvimento |
| `npm run build:web` | Build de produção do frontend |
| `npm run test:web` | Testes do frontend (Vitest) |
| `npm run dev:api` | API FastAPI local |
| `npm run test:api` | Testes do backend (pytest) |
| `npm run db:up` / `db:down` | Sobe/derruba os serviços Docker |
| `npm run db:init` | Cria tabelas e roda o seed |
| `npm run batch:score` | Calcula e grava os scores de recomendação no Redis |

---

## 📱 Telas implementadas

### 1. Onboarding (`/`)
Splash com logo, CTA "Usar minha localização" → toast de sucesso → redireciona para Home.

### 2. Home (`/home`)
- Header com saudação, localização e ícone de carrinho.
- Barra de busca (leads to `/buscar`).
- **Seção "Recomendados para você"** — carrossel horizontal com badge “✨ Para você” nos cards recomendados.
- **Seção "Perto de você"** — lista vertical com filtros por chips (Todos, Vegano, Promoções, Frete grátis, Mais bem avaliados).
- **Grid de Categorias** (Pizza, Hambúrguer, Japonês, etc.).
- Skeleton loading durante ~500ms simulando latência de API.

### 3. Buscar (`/buscar`)
Campo de busca com autofocus, chips de buscas recentes, filtro client-side por nome/categoria, e estado vazio.

### 4. Detalhe do Restaurante (`/restaurante/:id`)
- Hero com imagem e botão de voltar.
- Card de informações: nota, endereço, telefone clicável (`tel:`), taxa e tempo.
- Badge **“✨ Recomendado para você”** quando aplicável.
- **Tabs**: Cardápio (itens com botão “+” que adiciona ao carrinho), Avaliações (lista com estrelas), Sobre (placeholder).
- Rodapé fixo: **“Ver sacola · R$ X,XX”** atualiza em tempo real.

### 5. Pedidos (`/pedidos`)
Histórico mockado de pedidos com status "Entregue" e botão "Pedir novamente".

### 6. Perfil (`/perfil`)
Avatar, dados do usuário, preferências alimentares (Vegano, Vegetariano, etc.) e seção de **preferências de recomendação** (placeholder para features de IA).

---

## 🧠 Arquitetura de IA (backend)

O backend já implementa o caminho de eventos, treino, serving, cache e batch scoring. O que falta é a integração do frontend:

```
Eventos do app (cliques, pedidos, avaliações)
        ↓
Feature Store (PostgreSQL + Redis)
        ↓
Pipeline de treino (LightGBM com features por turno + medoides)
        ↓
Batch scoring diário → Redis (chave: user_id:turno → scores)
        ↓
API /recommendations (FastAPI/NestJS) lê scores do Redis
        ↓
Frontend recebe lista ordenada por score
```

**Implementado no MVP:** busca PostGIS, coleta de eventos, features por turno, treino LightGBM, serving com cache Redis, fallback por popularidade e batch scoring por usuário/turno.

**LLMs no fluxo (diferencial AI Engineer — roadmap):**
- Enriquecimento de features com embeddings (descrições de menu + reviews).
- Re-ranking com LLM pequeno ajustado via **LoRA** (Llama 3.2 1B / Qwen 2.5 1.5B).
- Orquestração de agente (LangChain) para consultas em linguagem natural ("quero algo vegano e barato").
- Modelo/adapter publicado no **Hugging Face Hub**.

📄 Detalhes completos em `docs/arquitetura-tecnica.md` e [`backend/README.md`](backend/README.md).

---

## 🗺️ Roadmap

### ✅ Concluído
- [x] Documentação técnica e arquitetura de IA
- [x] Prompt de protótipo visual (Lovable)
- [x] Esqueleto do projeto (Vite + React + TS + Tailwind)
- [x] Layout mobile com moldura de celular
- [x] 6 telas navegáveis com mock data
- [x] Store de carrinho com Zustand
- [x] Busca e filtros client-side
- [x] Sistema de toasts + skeleton loading
- [x] `mockData.ts` com 12 restaurantes completos
- [x] Página de sacola (`/sacola`) com confirmação de pedido
- [x] Modal "Ver no mapa" e transições entre rotas
- [x] Ajustes de acessibilidade (foco, `aria-label`, contraste)
- [x] API FastAPI + PostgreSQL/PostGIS + Redis
- [x] Busca geoespacial, detalhe e avaliações idempotentes
- [x] Coleta de eventos (`POST /events`) em PostgreSQL + Redis Stream
- [x] Endpoint `/recommendations` com LightGBM e fallback por popularidade
- [x] Pipeline de treino LightGBM com seed de pedidos e avaliações
- [x] Batch scoring diário por usuário/turno → Redis

### 🔄 Em andamento / Próximos passos
- [ ] Integrar o frontend à API (substituir mocks por chamadas HTTP)
- [ ] Migrations com Alembic (hoje `create_all` + DDL incremental)
- [ ] Monitoramento de latência e drift do recomendador
- [ ] Responsividade refinada para telas maiores

### 🎯 Longo prazo (LLMOps e portfólio)
- [ ] Fine-tuning **LoRA** de LLM pequeno para re-ranking
- [ ] Publicação do adapter no **Hugging Face Hub**
- [ ] Deploy do backend (AWS/GCP) com monitoramento
- [ ] A/B test: feed personalizado vs. feed por distância
- [ ] Migração do protótipo para **React Native + Expo** (app nativo)
- [ ] Artigo técnico publicado (Medium/dev.to) explicando a arquitetura

---

## 🎯 Conexão com a vaga de AI Engineer

| Requisito da vaga | Como o projeto atende |
|---|---|
| **GitHub com implementações de ML** | Este repositório + pipeline de treino a ser adicionado |
| **Modelos publicados no Hugging Face** | Adapter LoRA do re-ranker (roadmap) |
| **Projetos de pesquisa / artigos técnicos** | Documentação técnica + artigo no Medium (roadmap) |
| **Competições Kaggle** | Uso de dataset público de delivery para benchmark |
| **Construção de software com IA** | App frontend + API backend (FastAPI) + integração de modelo |
| **Operacionalização de LLMs** | Fine-tuning LoRA + serving via vLLM/Ollama |
| **MLOps / LLMOps** | MLflow, DVC, batch scoring, monitoramento de drift |
| **Trabalho remoto, 30h/semana** | Escopo dimensionado para ~4 meses em regime parcial |

---

## 👤 Autor

**Gustavo** — Candidato à vaga de Estágio/Residência em AI Engineer no iFood.

- 📧 [e-mail de contato]
- 💼 [LinkedIn]
- 🐙 [GitHub]

---

## 📄 Licença

Este é um projeto de portfólio acadêmico, sem fins comerciais. Inspirado na experiência de produto do iFood, 99Food e Keeta, mas sem qualquer vínculo oficial com essas empresas.