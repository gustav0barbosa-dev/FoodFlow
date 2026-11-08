# Documentação Técnica --- Plataforma de Delivery com Recomendação Inteligente

> MVP de uma plataforma de delivery mobile-first, com busca de
> restaurantes por proximidade e recomendações personalizadas inspiradas
> na arquitetura de recomendação do iFood.

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
│  API GATEWAY / BACKEND (NestJS ou FastAPI)                   │
│  • /api/v1/restaurants/search  (geo)                         │
│  • /api/v1/recommendations     (personalizado)               │
│  • /api/v1/users/:id/events    (coleta de interações)        │
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
│  • Embeddings de itens/restaurantes                          │
│  • LLM opcional para enriquecimento de features (LoRA)       │
│  • Serving de scores (batch diário → Redis)                  │
└──────────────────────────────────────────────────────────────┘
```

### Decisões principais

-   **PostgreSQL + PostGIS:** consultas geoespaciais com `ST_DWithin` e
    índices GIST, permitindo buscas eficientes por raio.
-   **Redis:** cache de scores de recomendação. Na arquitetura de
    referência descrita, o iFood calcula scores no dia anterior (D1) e
    os disponibiliza no Redis para reduzir a latência.
-   **React Native com Expo:** um único código-base para iOS e Android,
    com integração nativa de GPS e mapas.
-   **Modelo de recomendação leve (LightGBM):** escolha para o MVP, com
    possibilidade de adicionar um **LLM como re-ranker ou enriquecedor
    de features** em uma segunda fase.

## 3. Modelo de dados e geolocalização

### 3.1 Entidades principais

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
    categories TEXT[],
    average_rating NUMERIC(2,1) DEFAULT 0,
    review_count INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_restaurants_location
    ON restaurants USING GIST (location);

CREATE TABLE users (
    id UUID PRIMARY KEY,
    dietary_preferences TEXT[], -- vegano, vegetariano etc.
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE orders (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    restaurant_id UUID REFERENCES restaurants(id),
    items JSONB, -- itens pedidos com IDs de taxonomia
    order_value NUMERIC,
    delivery_fee NUMERIC,
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
        ST_MakePoint($lon, $lat)::geography
    ) / 1000 AS distance_km
FROM restaurants r
WHERE ST_DWithin(
    r.location,
    ST_MakePoint($lon, $lat)::geography,
    $radius_km * 1000
)
ORDER BY distance_km ASC
LIMIT $limit OFFSET $offset;
```

Esse padrão permite buscar restaurantes dentro de um raio definido. Os
campos `average_rating` e `review_count` são mantidos por **triggers**
no PostgreSQL para evitar a execução de `AVG()` em cada consulta.

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
2.  **Features do restaurante/lista:** embedding médio dos itens
    vendidos, valor médio, frete médio e volume de pedidos por turno.
3.  **Modelo:** LightGBM com restrições de monotonicidade nas features
    de similaridade, de modo que maior similaridade resulte em score
    maior.
4.  **Serving:** scores pré-calculados diariamente para usuários ativos
    e armazenados no **Redis**. A API consulta os scores e os combina
    com a lista de restaurantes próximos.

### 4.2 Pipeline de treino (offline)

``` text
Eventos de clique/pedido
        ↓
Feature Store (PostgreSQL/Redis)
        ↓
Treino LightGBM (scikit-learn / LightGBM)
  • Target: restaurante pedido vs. restaurante exibido e não pedido
  • Amostragem sem viés de visibilidade (1 positivo : 1 negativo por sessão)
        ↓
Salvar modelo (MLflow / joblib)
        ↓
Batch scoring diário → Redis
(chave: user_id:turno → scores)
```

A documentação de referência menciona o uso de **amostragem de
impressões** para evitar viés de visibilidade e **bootstrapping** a
partir de interações de carrosséis de categoria quando ainda não há
dados de produção.

No MVP, o desenvolvimento pode começar com dados sintéticos ou com um
dataset público do Yelp/Google Places para lidar com o *cold start*.
Posteriormente, os dados podem ser substituídos por interações reais do
aplicativo.

### 4.3 Uso de LLMs (diferencial para a vaga AI Engineer)

Embora o modelo principal seja o LightGBM, o projeto prevê incorporar
**LLMs de forma pragmática**, alinhando-se às abordagens descritas na
documentação de referência, como LCM (*Language-Centric Model*) e
agentes conversacionais.

-   **Enriquecimento de features:** utilizar um LLM para gerar
    descrições semânticas de restaurantes e itens a partir de avaliações
    e cardápios. Em seguida, gerar embeddings densos (por exemplo,
    `text-embedding-3-small`) para alimentar o LightGBM com features de
    similaridade.
-   **Fine-tuning leve (LoRA):** opcionalmente, ajustar um LLM
    open-source pequeno (por exemplo, Llama 3.2 1B ou Qwen 2.5 1.5B) com
    **LoRA** para tarefas de *re-ranking* ou geração de explicações,
    como "Por que recomendamos este restaurante?". Técnicas de
    *parameter-efficient fine-tuning* permitem personalização sem
    realizar um fine-tuning completo.
-   **Orquestração de agentes:** um agente simples, utilizando LangChain
    ou LlamaIndex, pode receber a localização do usuário, consultar a
    API de restaurantes próximos e usar o LLM para filtrar e ordenar os
    resultados com base em preferências declaradas, por exemplo: "quero
    algo vegano e barato". Isso demonstra conhecimentos de
    **orquestração de agentes** e **RAG**.

**Publicação no Hugging Face:** o modelo LoRA ajustado --- ou um modelo
de embeddings fine-tuned --- poderá ser publicado no Hugging Face Hub
como parte do portfólio.

## 5. Backend e APIs

### 5.1 Stack recomendada

  -----------------------------------------------------------------------
  Camada                  Tecnologia              Justificativa
  ----------------------- ----------------------- -----------------------
  API                     **NestJS                NestJS oferece
                          (Node/TypeScript)** ou  estrutura modular e
                          **FastAPI (Python)**    integração com
                                                  Socket.io. FastAPI
                                                  facilita a integração
                                                  com o ecossistema
                                                  Python de ML. Para um
                                                  perfil AI Engineer,
                                                  **FastAPI** é vantajoso
                                                  por unificar backend e
                                                  serving de ML.

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

  -----------------------------------------------------------------------------------------------------
  Método                  Endpoint                                              Finalidade
  ----------------------- ----------------------------------------------------- -----------------------
  `GET`                   `/api/v1/restaurants/search?lat=&lon=&radius_km=`     Busca geoespacial de
                                                                                restaurantes.

  `GET`                   `/api/v1/restaurants/:id`                             Retorna detalhes do
                                                                                restaurante, incluindo
                                                                                telefone, endereço e
                                                                                avaliações agregadas.

  `GET`                   `/api/v1/recommendations?user_id=&lat=&lon=&turno=`   Retorna lista ordenada
                                                                                por score, consultando
                                                                                o Redis; utiliza
                                                                                popularidade como
                                                                                fallback para novos
                                                                                usuários.

  `POST`                  `/api/v1/events`                                      Registra cliques,
                                                                                visualizações e pedidos
                                                                                para alimentar o
                                                                                pipeline de treino.

  `POST`                  `/api/v1/reviews`                                     Recebe avaliações, com
                                                                                idempotência via header
                                                                                `Idempotency-Key`.
  -----------------------------------------------------------------------------------------------------

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
    -   Chama `GET /restaurants/search` para obter restaurantes
        próximos.
    -   Chama `GET /recommendations` e mescla os resultados --- por
        exemplo, 70% recomendados e 30% próximos por distância --- para
        evitar uma "bolha" e garantir relevância local.
    -   Exibe cards com nome, avaliação, distância, tempo estimado e
        telefone.
2.  **Detalhe do restaurante**
    -   Exibe endereço completo, com botão "Abrir no mapa".
    -   Exibe telefone com link `tel:`.
    -   Apresenta as últimas 10 avaliações e a média.
    -   Exibe cardápio com itens identificados por IDs de taxonomia para
        alimentar o recomendador.
3.  **Perfil / Preferências**
    -   Permite configurar preferências alimentares (vegano, vegetariano
        e sem glúten).
    -   Exibe histórico de pedidos para dar transparência ao algoritmo.

### 6.3 Coleta de eventos para o recomendador

Cada interação relevante --- clique no card, abertura do restaurante,
adição ao carrinho e pedido concluído --- é enviada ao backend via
`POST /events`.

Esses eventos são a **matéria-prima** para o treinamento do modelo,
seguindo o princípio de aprender com cliques e compras.

## 7. MLOps / LLMOps

Para atender ao requisito de aplicar **MLOps e LLMOps em projetos de
alto impacto**, o projeto inclui:

-   **Versionamento de dados e modelos:** DVC ou MLflow para rastrear
    datasets, hiperparâmetros e artefatos do LightGBM.
-   **Pipeline de treino reprodutível:** script Python (`train.py`) que
    lê features do PostgreSQL, treina o modelo, avalia com métricas
    offline (acurácia e AUC) e registra os resultados no MLflow.
-   **Batch scoring diário:** job agendado (Airflow ou Cron) que gera
    scores para usuários ativos e os grava no Redis.
-   **Monitoramento:** métricas de latência da API de recomendação, taxa
    de acerto offline versus online (A/B test) e drift de features.
-   **LLMOps (opcional):** fine-tuning com LoRA usando `peft` e
    `transformers`; publicação do adapter no Hugging Face; serving via
    **vLLM** ou **Ollama** para o agente de *re-ranking*.

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

  -----------------------------------------------------------------------
  Requisito da vaga                   Como o projeto cobre
  ----------------------------------- -----------------------------------
  **GitHub com implementações de ML** Repositório público com pipeline de
                                      treino LightGBM, notebooks de
                                      análise exploratória, feature
                                      engineering e scripts de serving.

  **Modelos publicados no Hugging     Publicação do adapter LoRA --- ou
  Face**                              modelo de embeddings fine-tuned ---
                                      utilizado no re-ranking ou
                                      enriquecimento.

  **Projetos de pesquisa / artigos    README detalhado com fundamentação
  técnicos**                          no artigo do Red (iFood) e nas
                                      técnicas de recomendação com LLMs.
                                      Opcionalmente, publicação de um
                                      artigo no Medium ou dev.to
                                      explicando a arquitetura.

  **Competições Kaggle**              Uso de um dataset público de
                                      delivery (por exemplo, "Food
                                      Delivery Dataset" do Kaggle) para
                                      pré-treino ou benchmark do
                                      recomendador.

  **Construção e integração de        API em FastAPI/NestJS que integra o
  soluções de software com IA**       modelo LightGBM ao aplicativo
                                      mobile, com busca geoespacial e
                                      serving de recomendações via Redis.

  **Operacionalização de modelos      Pipeline de batch scoring,
  (LLMs)**                            monitoramento e, opcionalmente,
                                      serving de LLM com LoRA para
                                      re-ranking.

  **MLOps / LLMOps**                  MLflow, DVC, agendamento de jobs,
                                      monitoramento de drift e A/B test.

  **Trabalho remoto, 30h/semana**     O escopo do MVP foi dimensionado
                                      para ser construído em
                                      aproximadamente 3--4 meses em
                                      regime parcial.
  -----------------------------------------------------------------------

## 10. Roadmap de desenvolvimento

  -----------------------------------------------------------------------
  Fase                    Período                 Entregável
  ----------------------- ----------------------- -----------------------
  **Fase 1**                             Modelagem do banco
                                                  (PostGIS), endpoint de
                                                  busca geoespacial e
                                                  aplicativo React Native
                                                  com mapa e lista de
                                                  restaurantes próximos.

  **Fase 2**                                Coleta de eventos,
                                                  feature store básica,
                                                  treino do primeiro
                                                  modelo LightGBM com
                                                  dados
                                                  sintéticos/públicos e
                                                  serving via Redis.

  **Fase 3**                            Integração do feed
                                                  personalizado no
                                                  aplicativo, tela de
                                                  detalhes do restaurante
                                                  (telefone e avaliações)
                                                  e pipeline de
                                                  avaliações.

  **Fase 4**                            Fine-tuning LoRA de um
                                                  LLM pequeno para
                                                  re-ranking, publicação
                                                  no Hugging Face,
                                                  documentação técnica e
                                                  artigo de portfólio.

  **Fase 5 (opcional)**   ---                     Deploy em nuvem
                                                  (AWS/GCP),
                                                  monitoramento com
                                                  Prometheus/Grafana e
                                                  A/B test do feed
                                                  personalizado versus
                                                  feed por distância.
  -----------------------------------------------------------------------

## 11. Considerações finais

Este projeto foi concebido para unir **engenharia de software sólida**
--- APIs, banco geoespacial e desenvolvimento mobile --- com **IA
aplicada**, por meio de recomendação personalizada com LightGBM e LLMs.

A proposta utiliza como inspiração a arquitetura de recomendação Red do
iFood. Ao publicar o código no GitHub, o modelo no Hugging Face e um
artigo técnico explicando as decisões, o projeto poderá compor um
portfólio alinhado às competências esperadas na trilha **AI Engineer**:
construir, integrar e operacionalizar soluções de IA de ponta a ponta,
com ênfase em **LLMs e MLOps/LLMOps**.

------------------------------------------------------------------------

## Observações de implementação

-   Este documento descreve a arquitetura e o escopo propostos para o
    MVP; não significa que todos os componentes já estejam
    implementados.
-   Tecnologias e serviços marcados como opcionais representam
    possibilidades de evolução, não requisitos obrigatórios da primeira
    versão.
-   A arquitetura deverá ser revisada conforme as decisões técnicas
    tomadas durante a implementação.
