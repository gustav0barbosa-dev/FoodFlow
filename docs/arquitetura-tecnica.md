# Documentação Técnica --- Plataforma de Delivery com Recomendação Inteligente

> MVP de uma plataforma de delivery mobile-first, com busca de
> restaurantes por proximidade e recomendações personalizadas inspiradas
> na arquitetura de recomendação do iFood.

## Estado atual da implementação

Este documento descreve a arquitetura-alvo **e** o que já está
implementado no repositório. A tabela abaixo prevalece em caso de dúvida
entre proposta e realidade.

| Componente | Estado atual |
|---|---|
| Backend | Implementado em **FastAPI** (Python 3.11), com catálogo, recomendações, eventos, avaliações, usuários e observabilidade. |
| Banco e migrações | **PostgreSQL 16 + PostGIS** via Alembic; seed determinístico para catálogo, usuários, pedidos e avaliações. |
| Busca geoespacial | Implementada com `ST_DWithin` e índice GIST. |
| Recomendação | **LightGBM** implementado, com features por turno e fallback por popularidade/distância. |
| Cache e batch scoring | Redis é **opcional** (a API degrada sem ele); `scripts/batch_score.py` permite pré-calcular scores de forma manual ou agendada. |
| A/B test e drift | Implementados (atribuição estável por SHA-256 e PSI por feature). |
| Mobile | React Native + Expo; catálogo, detalhe, perfil e feed de recomendações consomem a API, com mock como fallback offline. |
| Docker Compose | Arquivos de desenvolvimento e produção definidos, com script de validação end-to-end e workflow de CI. A execução live ainda não foi feita neste ambiente por ausência de Docker. |
| LoRA | **Experimental e opcional**: treino offline, carregamento sob flag e fallback determinístico. Avaliação offline (AUC/NDCG@5) implementada; no seed o LoRA não superou o LightGBM, então permanece desabilitado por padrão. |
| MLflow / DVC | **Não implementados**; o versionamento atual usa joblib + metadados JSON + Git. |
| Embeddings, agentes e RAG | **Planejados**; não fazem parte do runtime atual. |
| Airflow | **Não implementado**; o batch é executado por script, cron/Task Scheduler ou profile do Compose. |
| Hugging Face | Há um adapter publicado, mas ele usa base Llama 3.2 1B e métricas não reproduzíveis pelo runtime atual (MiniLM); a avaliação local não confirma o ganho. |

## 1. Visão geral e escopo do projeto

O objetivo é construir uma plataforma de delivery **mobile-first** que:

-   Localize restaurantes próximos ao usuário por geolocalização.
-   Exiba informações completas dos restaurantes, como nome, endereço,
    telefone, avaliações e categorias.
-   Personalize a experiência de descoberta com um **algoritmo de
    recomendação que aprende preferências**, considerando turno do dia,
    histórico de pedidos e similaridade de itens --- de forma análoga ao
    sistema **Red** do iFood.
-   Seja implementável como **projeto de portfólio para a vaga de AI
    Engineer**, demonstrando domínio de **ML/LLMs, engenharia de
    software, APIs, mobile e MLOps/LLMOps**.

O escopo do MVP inclui apenas o **aplicativo do cliente (consumidor)** e
o **backend de catálogo e recomendação**. Funcionalidades de painel de
restaurante, aplicativo de entregador e pagamento real ficam fora do
MVP, mas a arquitetura já considera sua possível inclusão futura.

## 2. Arquitetura de alto nível

``` text
┌──────────────────────────────────────────────────────────────┐
│  MOBILE APP (React Native / Expo)                            │
│  • Geolocalização (expo-location)                            │
│  • Mapa (react-native-maps)                                  │
│  • Feed de restaurantes e recomendações                      │
└──────────────────────┬───────────────────────────────────────┘
                       │ HTTPS / JSON
┌──────────────────────▼───────────────────────────────────────┐
│  BACKEND (FastAPI)                                           │
│  • /api/v1/restaurants/search  (geo)                         │
│  • /api/v1/restaurants/:id     (detalhe)                     │
│  • /api/v1/recommendations     (personalizado)               │
│  • /api/v1/users/:id           (perfil)                      │
│  • /api/v1/events              (coleta de interações)        │
└───────┬───────────────────────────────┬─────────────────────┘
        │                               │
┌───────▼──────────┐          ┌─────────▼─────────────────────┐
│  PostgreSQL      │          │  Redis                        │
│  + PostGIS       │          │  • Cache de scores do Red     │
│  (restaurantes,  │          │  • Sessões e features         │
│   avaliações,    │          │    pré-computadas             │
│   usuários)      │          └───────────────────────────────┘
└──────────────────┘
        │
┌───────▼──────────────────────────────────────────────────────┐
│  PIPELINE DE ML / LLMOPS                                     │
│  • Treino do modelo de recomendação (LightGBM)               │
│  • Embeddings de itens/restaurantes (planejado)              │
│  • Re-rank LoRA opcional (experimental) + fallback           │
│  • Batch scoring agendável → Redis                           │
└──────────────────────────────────────────────────────────────┘
```

### Decisões principais

-   **PostgreSQL + PostGIS:** consultas geoespaciais com `ST_DWithin` e
    índices GIST, permitindo buscas eficientes por raio.
-   **Redis:** cache de scores de recomendação. Na arquitetura de
    referência descrita, o iFood calcula scores no dia anterior (D1) e
    os disponibiliza no Redis para reduzir a latência. No MVP atual o
    Redis é **opcional**: sem ele, a API calcula os scores sob demanda e
    continua respondendo (degradação graciosa).
-   **React Native com Expo:** um único código-base para iOS e Android,
    com integração nativa de GPS e mapas.
-   **Modelo de recomendação leve (LightGBM):** escolha para o MVP, com
    possibilidade de adicionar um **LLM como re-ranker ou enriquecedor
    de features** em uma segunda fase.

## 3. Modelo de dados e geolocalização

### 3.1 Entidades principais

O schema real e as migrações estão em
`backend/alembic/versions/0001_initial_schema.py`. O bloco abaixo é uma
visão conceitual simplificada; consulte a migração para os tipos,
constraints e índices exatos.

``` sql
-- Extensão PostGIS
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE restaurants (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    phone TEXT,
    address TEXT,
    location GEOGRAPHY(POINT, 4326) NOT NULL, -- latitude/longitude
    categories JSONB,
    average_rating NUMERIC(2,1) DEFAULT 0,
    review_count INT DEFAULT 0,
    delivery_fee NUMERIC DEFAULT 0,
    delivery_time_min INT DEFAULT 0,
    delivery_time_max INT DEFAULT 0,
    image_url TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_restaurants_location
    ON restaurants USING GIST (location);

CREATE TABLE users (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    dietary_preferences JSONB, -- vegano, vegetariano etc.
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE orders (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    restaurant_id UUID REFERENCES restaurants(id),
    items JSONB, -- itens pedidos com IDs de taxonomia
    order_value NUMERIC,
    delivery_fee NUMERIC,
    status TEXT,
    created_at TIMESTAMPTZ
);

CREATE TABLE reviews (
    id UUID PRIMARY KEY,
    restaurant_id UUID REFERENCES restaurants(id),
    user_id UUID REFERENCES users(id),
    rating INT CHECK (rating BETWEEN 1 AND 5),
    comment TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

### 3.2 Busca por proximidade (endpoint Geo)

**Endpoint:** `GET /api/v1/restaurants/search`

**Parâmetros:** `lat`, `lon`, `radius_km` (padrão: 5), `limit` e
`offset`.

``` sql
SELECT
    r.*,
    ST_Distance(
        r.location,
        ST_SetSRID(ST_MakePoint($lon, $lat), 4326)::geography
    ) / 1000 AS distance_km
FROM restaurants r
WHERE ST_DWithin(
    r.location,
    ST_SetSRID(ST_MakePoint($lon, $lat), 4326)::geography,
    $radius_km * 1000
)
ORDER BY distance_km ASC
LIMIT $limit OFFSET $offset;
```

Esse padrão permite buscar restaurantes dentro de um raio definido. Os
campos `average_rating` e `review_count` são recalculados pela aplicação
(`crud.refresh_restaurant_rating`) após criar, editar ou remover
avaliações, evitando a execução de `AVG()` em cada consulta.

## 4. Sistema de recomendação personalizado (inspirado no iFood)

### 4.1 Estratégia geral

A documentação de referência descreve a evolução do iFood de técnicas
como *matrix factorization* e *bandits* para um modelo de
**classificação com LightGBM** (Red), que pontua listas curadas por
usuário e turno do dia.

Para o MVP, será adotada uma abordagem simplificada, baseada nos mesmos
princípios:

1.  **Features do usuário:** perfil geral (total de pedidos e
    preferências alimentares), comportamento por turno (valor médio,
    frete médio e categorias mais consumidas) e **medoides** --- itens
    mais representativos por turno, combinando frequência e recência.
2.  **Features do restaurante/lista:** nota média, volume de avaliações,
    frete, tempo de entrega e indicador de restaurante mais frequente no
    turno. Embeddings de itens são evolução planejada.
3.  **Modelo:** LightGBM de classificação binária com 200 árvores,
    profundidade máxima 5 e one-hot do turno. A restrição de
    monotonicidade nas features de similaridade é uma evolução
    planejada, não implementada.
4.  **Serving:** a API consulta os scores no **Redis**; em caso de cache
    miss, calcula sob demanda com o LightGBM. O script
    `scripts/batch_score.py` permite pré-calcular os scores de usuários
    ativos de forma manual ou agendada. Sem Redis, a API continua
    funcionando e calcula os scores a cada requisição.

### 4.2 Pipeline de treino (offline)

``` text
Eventos de clique/pedido
        ↓
Dados de pedidos (PostgreSQL) + features calculadas
        ↓
Treino LightGBM (scikit-learn / LightGBM)
  • Target: restaurante pedido vs. candidatos não pedidos
  • Amostragem 1 positivo : 3 negativos por turno
        ↓
Salvar modelo (joblib + metadados JSON; MLflow não implementado)
        ↓
Batch scoring opcional/agendável → Redis
(chave: user_id:turno → scores)
```

A documentação de referência menciona o uso de **amostragem de
impressões** para evitar viés de visibilidade e **bootstrapping** a
partir de interações de carrosséis de categoria quando ainda não há
dados de produção.

No MVP, o treino pode usar os pedidos do PostgreSQL
(`python -m app.ml.train --source db`) ou o seed determinístico
(`python -m app.ml.train --source seed`), que permite gerar o artefato
sem depender de PostGIS. Posteriormente, os dados podem ser substituídos
por interações reais do aplicativo.

### 4.3 Uso de LLMs (experimental)

O modelo principal do MVP é o **LightGBM**. O uso de LLMs está em
estágio **experimental** e não é necessário para a API funcionar.

**Re-ranking com LoRA (extensão opcional):**

-   O treino é **offline**:
    `python scripts/train_lora.py --source seed` (ou `--source db`). O
    script gera pares sintéticos (usuário, restaurante, turno) e ajusta
    um classificador pequeno com `transformers` + `peft`.
-   O serving é habilitado por `ENABLE_LORA_RERANKER=true`. Se as
    dependências, o adapter real ou o artefato estiverem ausentes, o
    re-ranker aplica um **fallback determinístico** baseado em rating,
    frete, tempo de entrega e turno.
-   `POST /api/v1/recommendations/train-lora` retorna `202 Accepted` e
    apenas orienta o treino offline; ele **não treina dentro da
    requisição HTTP**.
-   O artefato esperado fica em `backend/models/lora_reranker/` e não é
    versionado no Git. Um placeholder é detectado e não carregado.
-   A imagem Docker padrão instala apenas `requirements.txt`; para usar
    LoRA dentro do container, é necessário um build com
    `requirements-llmops.txt` ou instalar as dependências no ambiente de
    serving.
-   A avaliação offline está implementada em `app/ml/lora_evaluation.py`
    e pode ser executada com
    `python scripts/evaluate_lora.py --source seed` (ou `--source db`).
    O treino do adapter de avaliação acontece em um diretório temporário
    e **não** sobrescreve o artefato de serving.
-   Existe um adapter publicado no Hugging Face com base Llama 3.2 1B e
    um card que reporta NDCG@5 0.79. O runtime deste repositório usa
    `sentence-transformers/all-MiniLM-L6-v2`, e a avaliação reproduzível
    com esse caminho **não confirma** o ganho. Antes de habilitar em
    produção, é necessário alinhar modelo base/target modules e reavaliar
    o artefato publicado.

#### Resultados da avaliação offline (seed, split temporal)

A avaliação treina em pedidos antigos e mede pedidos recentes, com
features do usuário calculadas apenas no histórico de treino (sem
vazamento). Cada contexto é um par (usuário, turno); os candidatos são os
12 restaurantes do seed. Métricas: AUC macro por contexto e NDCG@5 macro.

| Estratégia | AUC | NDCG@5 |
|---|---|---|
| Popularidade | 0.5051 | 0.3268 |
| LightGBM | **0.6727** | **0.5002** |
| LoRA | 0.3574 | 0.2018 |
| Híbrido (LightGBM + LoRA, 50/50) | 0.5903 | 0.4223 |

Em janelas alternativas de holdout (10 e 14 dias), o LoRA também ficou
abaixo do LightGBM (AUC 0.5182 e 0.3606, respectivamente; LightGBM 0.5939
e 0.5858). O híbrido não superou o LightGBM em nenhuma janela. O seed tem
apenas 30 pedidos, então os números são **indicativos**; ainda assim, o
sinal é consistente e suficiente para manter o LoRA como experimental e
**desabilitado por padrão** (`ENABLE_LORA_RERANKER=false`).

O card do adapter publicado no Hugging Face reporta NDCG@5 0.72 → 0.79
com base Llama 3.2 1B. Esses números não são reproduzíveis a partir deste
repositório (runtime MiniLM) e o card ainda contém placeholders; eles não
devem ser usados como evidência de qualidade até que o artefato seja
alinhado ao runtime e reavaliado.

**Evoluções planejadas (não implementadas):**

-   Enriquecimento de features com embeddings de descrições e cardápios.
-   Geração de explicações e agentes/RAG para filtros em linguagem
    natural.
-   Alinhamento do adapter publicado no Hugging Face ao modelo base do
    runtime (MiniLM) e reavaliação antes de habilitá-lo por padrão.

## 5. Backend e APIs

### 5.1 Stack recomendada

**Implementado:** FastAPI (Python 3.11), PostgreSQL 16 + PostGIS
(imagem `postgis/postgis:16-3.4` no Compose) e Redis 7. O Redis é
opcional no runtime e a API degrada sem ele. Fila assíncrona
(BullMQ/RabbitMQ) **não foi implementada**.

  -----------------------------------------------------------------------
  Camada                  Tecnologia              Justificativa
  ----------------------- ----------------------- -----------------------
  API                     **FastAPI (Python)**    Escolhido por unificar
                                                  backend e serving de ML
                                                  no ecossistema Python e
                                                  por facilitar a
                                                  integração com
                                                  LightGBM, pandas e
                                                  scikit-learn.

  Banco relacional        **PostgreSQL 16 +       Consultas geoespaciais
                          PostGIS**               eficientes e transações
                                                  ACID para avaliações.

  Cache                   **Redis**               Armazenamento de scores
                                                  de recomendação e
                                                  sessões.

  Fila (opcional)         **BullMQ (Redis) ou     Sincronização de
                          RabbitMQ**              índices e processamento
                                                  assíncrono de eventos.
  -----------------------------------------------------------------------

### 5.2 Endpoints principais

| Método | Endpoint | Finalidade |
|---|---|---|
| `GET` | `/api/v1/restaurants/search?lat=&lon=&radius_km=` | Busca geoespacial de restaurantes. |
| `GET` | `/api/v1/restaurants/{id}` | Detalhe do restaurante, incluindo avaliações. |
| `GET` | `/api/v1/recommendations?user_id=&lat=&lon=&turno=&experiment=` | Lista ordenada por score; usa Redis quando disponível e fallback por popularidade/distância. |
| `POST` | `/api/v1/recommendations/train` | Treina o LightGBM a partir dos pedidos do banco. |
| `POST` | `/api/v1/recommendations/train-lora` | Retorna `202`; o treino LoRA é uma operação offline. |
| `POST` | `/api/v1/recommendations/rerank` | Re-executa o re-ranking sobre scores já em cache. |
| `POST` | `/api/v1/events` | Registra cliques, visualizações e pedidos para o pipeline de treino. |
| `POST` | `/api/v1/reviews` | Cria avaliação, com idempotência via header `Idempotency-Key`. |
| `PUT` | `/api/v1/reviews/{id}` | Atualiza a avaliação do próprio usuário. |
| `DELETE` | `/api/v1/reviews/{id}` | Remove a avaliação do próprio usuário. |
| `GET` | `/api/v1/users/{id}` | Perfil público (nome, e-mail e preferências alimentares). |
| `GET` | `/health` | Health check com status do modelo e do Redis. |
| `GET` | `/ready` | Readiness (PostgreSQL obrigatório; Redis e modelo degradáveis). |
| `GET` | `/api/v1/metrics` | Métricas no formato Prometheus. |
| `GET` | `/api/v1/metrics/recommendations` | Cache hit rate e estratégia de scoring. |
| `GET` | `/api/v1/drift` | Relatório de drift de features (PSI). |
| `GET` | `/api/v1/experiment/ab-test` | Resultados acumulados do experimento A/B. |

## 6. Frontend mobile (aplicativo)

### 6.1 Stack

-   **React Native com Expo:** um único código para iOS e Android. O
    ecossistema Expo facilita o acesso ao GPS (`expo-location`), mapas
    (`react-native-maps`) e distribuição de builds.
-   **Flutter:** alternativa viável, com UI consistente e boa
    performance. Entretanto, o ecossistema de mapas e a integração com
    bibliotecas de ML no lado JS/TS favorecem React Native para um MVP
    rápido.

### 6.2 Telas principais

1.  **Home / Feed personalizado**
    -   Solicita permissão de localização.
    -   Chama `GET /restaurants/search` (via `catalogStore`) para obter
        restaurantes próximos; se a API estiver offline, usa o catálogo
        mock local.
    -   Em paralelo, chama `GET /recommendations` com `DEFAULT_USER_ID`,
        localização atual, `getCurrentTurno()` e o grupo A/B opcional. A
        seção "Recomendados para você" usa a ordem retornada pela API;
        se as recomendações falharem, mantém o fallback para os itens
        marcados no catálogo/mock.
    -   Exibe cards com nome, avaliação, distância, tempo estimado e
        telefone.
2.  **Detalhe do restaurante**
    -   Consome `GET /restaurants/{id}` e usa o mock como fallback.
    -   Exibe endereço completo, telefone com link `tel:` e avaliações.
    -   Exibe cardápio; a integração completa de itens com IDs de
        taxonomia permanece planejada.
3.  **Perfil / Preferências**
    -   Consome `GET /users/{id}` com o `DEFAULT_USER_ID` do seed (Ana
        Souza) e usa o mock como fallback.
    -   Exibe nome, e-mail e preferências alimentares retornadas pela
        API.
    -   Edição/persistência de preferências e histórico de pedidos no
        mobile ainda são evolutivas.

### 6.3 Coleta de eventos para o recomendador

Cada interação relevante --- clique no card, abertura do restaurante,
adição ao carrinho e pedido concluído --- é enviada ao backend via
`POST /events`.

Esses eventos são a **matéria-prima** para o treinamento do modelo,
seguindo o princípio de aprender com cliques e compras.

## 7. MLOps / LLMOps

Para atender ao requisito de aplicar **MLOps e LLMOps em projetos de
alto impacto**, o projeto separa o que já existe do que é evolução.

**Implementado no MVP:**

-   **Pipeline de treino reprodutível:** `app/ml/train.py` treina o
    LightGBM a partir do PostgreSQL (`--source db`) ou do seed
    determinístico (`--source seed`), avalia com AUC e salva o artefato
    joblib com metadados JSON.
-   **Batch scoring:** `scripts/batch_score.py` pré-calcula scores por
    usuário/turno no Redis; pode ser agendado por cron, Task Scheduler
    ou pelo profile `batch` do Compose.
-   **Monitoramento:** `/health`, `/ready`, métricas Prometheus, cache
    hit rate e relatório de drift por PSI.
-   **Avaliação offline do LoRA:** `scripts/evaluate_lora.py` compara
    popularidade, LightGBM, LoRA e híbrido com split temporal, AUC e
    NDCG@5, usando um adapter temporário que não altera o artefato de
    serving.
-   **Validação do Compose:** `scripts/validate_compose.sh` sobe as
    stacks de desenvolvimento e produção e verifica migrate, PostGIS,
    Redis, seed, endpoints e o volume `backend_models`. O workflow
    `.github/workflows/compose-validation.yml` executa o script em um
    runner com Docker.
-   **Experimento A/B:** atribuição estável por SHA-256 entre feed
    personalizado e feed por distância, com resultados em
    `/api/v1/experiment/ab-test`.
-   **Testes automatizados:** backend com pytest (102 testes), frontend
    web com lint/build/testes e mobile com `tsc --noEmit`.

**Planejado / não implementado:**

-   **Versionamento com DVC ou MLflow:** hoje o versionamento é feito
    por joblib + metadados + Git.
-   **Orquestração com Airflow:** o batch é um script avulso.
-   **LLMOps completo:** o treino LoRA é experimental e offline; a
    avaliação offline já existe, mas não há serving com vLLM/Ollama nem
    operação contínua do adapter em produção.
-   **Monitoramento em nuvem com Prometheus/Grafana:** as métricas
    existem, mas o deploy de observabilidade não foi montado.

## 8. Segurança e privacidade

-   **LGPD:** dados de localização e histórico de pedidos exigem
    cuidado. O aplicativo deve solicitar consentimento explícito para
    coleta de localização e armazenar apenas coordenadas aproximadas
    quando a precisão total não for necessária.
-   **Anonimização:** para o treinamento do modelo, utilizar IDs
    pseudonimizados e evitar armazenar comentários de avaliação que
    contenham dados pessoais.
-   **Idempotência em avaliações:** utilizar o header `Idempotency-Key`
    para evitar duplicatas, conforme o padrão de arquitetura de
    referência.

## 9. Como este projeto atende aos requisitos da vaga (AI Engineer)

| Requisito da vaga | Como o projeto cobre (estado atual) |
|---|---|
| **GitHub com implementações de ML** | Pipeline de treino LightGBM, feature engineering, serving, batch scoring e testes automatizados. Não há notebooks de análise exploratória no repositório. |
| **Modelos publicados no Hugging Face** | Há um adapter LoRA publicado, mas ele usa base Llama 3.2 1B e o card contém métricas não reproduzíveis pelo runtime MiniLM; alinhamento e reavaliação pendentes. |
| **Projetos de pesquisa / artigos técnicos** | README e documentação técnica com fundamentação no artigo do Red (iFood). Artigo em Medium/dev.to é plano futuro. |
| **Competições Kaggle** | O MVP usa seed determinístico; um dataset público de delivery para benchmark ainda não foi integrado. |
| **Construção e integração de soluções de software com IA** | API FastAPI que integra LightGBM, busca geoespacial PostGIS e app mobile; Redis é opcional. |
| **Operacionalização de modelos (LLMs)** | Batch scoring, monitoramento e A/B test implementados. Serving de LLM com LoRA é experimental/planejado. |
| **MLOps / LLMOps** | Drift por PSI, A/B test, batch scoring e testes estão implementados. MLflow, DVC e Airflow são planos futuros. |
| **Trabalho remoto, 30h/semana** | O escopo do MVP foi dimensionado para aproximadamente 3--4 meses em regime parcial. |

## 10. Roadmap de desenvolvimento

| Fase | Estado | Entregável |
|---|---|---|
| **Fase 1** | Implementada | Modelagem PostGIS, busca geoespacial, catálogo mobile e seed. |
| **Fase 2** | Implementada parcialmente | Eventos, treino LightGBM e batch scoring. A "feature store" é o próprio PostgreSQL, sem Redis como store dedicada. |
| **Fase 3** | Parcial | Detalhe do restaurante, avaliações e perfil via API. O feed personalizado no mobile está integrado a `GET /recommendations`, com fallback para catálogo/mock. |
| **Fase 4** | Experimental | Treino e avaliação offline do LoRA implementados (AUC/NDCG@5). O adapter não superou o LightGBM no seed e permanece desabilitado por padrão. |
| **Fase 5 (opcional)** | Pendente | Deploy em nuvem, Prometheus/Grafana e A/B test em produção. |

## 11. Considerações finais

Este projeto foi concebido para unir **engenharia de software sólida**
--- APIs, banco geoespacial e desenvolvimento mobile --- com **IA
aplicada**, por meio de recomendação personalizada com LightGBM e, de
forma experimental, re-ranking com LoRA.

A proposta utiliza como inspiração a arquitetura de recomendação Red do
iFood. O código, a documentação e os testes já demonstram a construção e
a integração do sistema. A publicação do adapter no Hugging Face e um
artigo técnico explicando as decisões são próximos passos para compor um
portfólio alinhado às competências esperadas na trilha **AI Engineer**.

------------------------------------------------------------------------

## Observações de implementação

-   A seção **Estado atual da implementação** resume o que já existe; em
    caso de divergência com as seções propositivas, ela prevalece.
-   Tecnologias e serviços marcados como opcionais ou planejados
    representam possibilidades de evolução, não requisitos da primeira
    versão.
-   A validação live do Docker Compose ainda não foi executada neste
    ambiente por ausência de Docker. O script `scripts/validate_compose.sh`
    e o workflow de CI foram adicionados para rodar a validação em uma
    máquina com Docker; o resultado deve ser registrado no histórico do
    workflow após o push.
-   A arquitetura deverá ser revisada conforme as decisões técnicas
    tomadas durante a implementação.
