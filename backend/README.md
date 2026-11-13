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
| `GET` | `/ready` | Readiness com PostgreSQL, Redis e modelo |
| `GET` | `/api/v1/metrics/recommendations` | Contadores de cache, modelo e popularidade |
| `GET` | `/api/v1/metrics` | Métricas no formato Prometheus |
| `GET` | `/api/v1/drift` | Relatório de drift de features (PSI) |
| `GET` | `/api/v1/experiment/ab-test` | Resultados do experimento A/B calculados a partir do banco (Redis apenas como diagnóstico) |
| `GET` | `/api/v1/ml/metrics` | Métricas do último treino offline (`models/training_metrics.json`) |
| `GET` | `/api/v1/street-view/metadata?lat=&lon=` | Informa se há panorama disponível; nunca expõe a chave |
| `GET` | `/api/v1/street-view/image?lat=&lon=` | Proxy da imagem do Street View (a chave fica no backend) |
| `GET` | `/api/v1/restaurants/search?lat=&lon=&radius_km=` | Busca geoespacial (PostGIS `ST_DWithin`) |
| `GET` | `/api/v1/restaurants/nearby?lat=&lon=&radius=&category=` | Descoberta no OpenStreetMap/Overpass; `radius` em metros e `category` opcional |
| `GET` | `/api/v1/restaurants/osm/{osm_type}/{osm_id}?refresh=` | Detalhe do OSM (persiste no primeiro acesso e devolve o UUID interno) |
| `GET` | `/api/v1/restaurants/{id}` | Detalhe do restaurante + últimas 10 avaliações |
| `GET` | `/api/v1/restaurants/{id}/menu` | Cardápio do restaurante (lista vazia se não houver itens); `source=synthetic` indica exemplo gerado por script |
| `POST` | `/api/v1/interactions` | Registra `IMPRESSION`, `VIEW`, `VIEW_DETAILS`, `CLICK`, `FAVORITE`, `PURCHASE` ou `DISMISS` (idempotência opcional) |
| `GET` | `/api/v1/users/{id}/preferences` | Perfil de preferências derivado do histórico |
| `POST` | `/api/v1/reviews` | Cria avaliação com idempotência via `Idempotency-Key` |
| `PUT` | `/api/v1/reviews/{id}` | Atualiza avaliação do próprio usuário |
| `DELETE` | `/api/v1/reviews/{id}` | Remove avaliação do próprio usuário |
| `GET` | `/api/v1/recommendations?user_id=&lat=&lon=&turno=&mode=&experiment=` | Ranking personalizado (Redis → LightGBM → popularidade). `mode=experiment` usa atribuição persistente; `mode=demo` aceita `experiment=baseline\|personalized\|distance` |
| `GET` | `/api/v1/experiment/ab-test` | Resultados do A/B com fases, coorte válida, contaminação, exigência de baseline, IC bootstrap por usuário, p-valor sob H0, Bonferroni e plano de amostra (Redis apenas como diagnóstico) |
| `POST` | `/api/v1/recommendations/train` | Retorna `202`; o treino do LightGBM é offline (`python -m app.ml.train`) |
| `POST` | `/api/v1/recommendations/train-lora` | Retorna `202`; treino LoRA é offline |
| `POST` | `/api/v1/recommendations/rerank` | Re-executa o re-ranking sobre scores em cache |
| `POST` | `/api/v1/events` | Coleta de eventos para o pipeline de ML |
| `GET` | `/api/v1/users/{id}` | Perfil do usuário (nome, e-mail e preferências) |

`turno` aceita `manha`, `tarde`, `noite` ou `madrugada` (padrão: `tarde`).

## OpenStreetMap + Overpass (descoberta de restaurantes reais)

A rota `/api/v1/restaurants/nearby` consulta o **OpenStreetMap** por meio da
**Overpass API** em uma camada separada do catálogo próprio. Ela apenas descobre
estabelecimentos reais; a persistência acontece quando o usuário abre o detalhe.

O detalhe fica em `/api/v1/restaurants/osm/{osm_type}/{osm_id}`. Na primeira
abertura o backend consulta a Overpass, grava o restaurante no PostGIS com
`source="osm"` e o par único `(osm_type, osm_id)` e devolve o UUID interno. Nas
aberturas seguintes usa o registro persistido; `refresh=true` força uma nova
consulta e, se a Overpass falhar, mantém o cache local. Campos ausentes no OSM
permanecem `null`/vazios — nenhum telefone, horário, site, cardápio ou avaliação
é inventado.

Parâmetros: `lat`, `lon`, `radius` (metros, 100–50000, padrão `3000`) e
`category` opcional (`restaurant`, `fast_food`, `cafe`, `bar`). A resposta é
normalizada:

```json
{
  "source": "OpenStreetMap",
  "count": 1,
  "restaurants": [
    {
      "osm_id": 123456789,
      "osm_type": "node",
      "name": "Restaurante Exemplo",
      "latitude": -23.551,
      "longitude": -46.634,
      "category": "restaurant",
      "cuisine": "italian",
      "address": { "street": "Rua Exemplo", "number": "100", "city": "São Paulo", "postcode": null },
      "phone": null,
      "website": null,
      "opening_hours": null,
      "osm_url": "https://www.openstreetmap.org/node/123456789",
      "distance_km": 0.42
    }
  ]
}
```

Configuração (opcional; os padrões funcionam nas instâncias públicas):

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `OVERPASS_API_URL` | `https://overpass-api.de/api/interpreter` | Instância consultada |
| `OVERPASS_CACHE_TTL_SECONDS` | `300` | TTL do cache Redis por região |
| `OVERPASS_TIMEOUT_SECONDS` | `25` | Timeout da consulta QL/HTTP |
| `OVERPASS_USER_AGENT` | `FoodFlow/0.2` | Identificação exigida pelas instâncias públicas |

O cache Redis usa a chave `nearby:osm:v1:{lat:.3f}:{lon:.3f}:{radius}:{category|all}`
e é consultado antes de qualquer chamada externa; as distâncias são recalculadas
para a origem da requisição. Consultas concorrentes à Overpass são limitadas a
duas. Erros são mapeados para `503` (rate limit), `504` (timeout) e `502`
(falha upstream); `category` inválida retorna `422`. Campos ausentes no OSM são
retornados como `null`; a persistência ocorre somente no endpoint de detalhe.

A Overpass API não oferece rotas nem geocodificação; para essas funcionalidades
será necessário integrar outro serviço compatível com OpenStreetMap. Os dados
são distribuídos sob a Open Database License (ODbL) e exigem a atribuição
“© OpenStreetMap contributors”.

### Ingestão por região (CLI)

O pipeline em lote é uma operação de manutenção — nunca um endpoint HTTP:

```bash
cd backend
python scripts/ingest_osm.py --south -23.60 --west -46.70 \
  --north -23.50 --east -46.60 [--category cafe]
```

A região é validada (área máxima de 1 grau²) para não sobrecarregar a Overpass.
O pipeline normaliza, valida, deduplica por `(osm_type, osm_id)` e faz upsert,
renovando `last_synced_at`; o resumo informa `fetched`, `deduplicated`,
`created`, `updated`, `skipped` e `errors` por linha. Reexecutar é idempotente.
`dietary_tags` é preenchido apenas quando a tag `diet:*` é explicitamente
afirmativa — ausência significa “não informado”, nunca “não possui”.

## Street View (opcional)

O detalhe do restaurante exibe um panorama quando há cobertura. A chave da
Google Maps API permanece **exclusivamente no backend**: o frontend consulta
`/api/v1/street-view/metadata` e carrega a imagem pelo proxy
`/api/v1/street-view/image`. `ZERO_RESULTS`/`NOT_FOUND` retornam
`available=false` (o componente fica oculto), enquanto autenticação, quota,
timeout e falhas são mapeados para `502`/`429`/`504` sem vazar a chave.

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `GOOGLE_MAPS_API_KEY` | vazio | Chave do backend; sem ela o componente não aparece |
| `STREET_VIEW_TIMEOUT_SECONDS` | `5` | Timeout das chamadas ao Google |
| `STREET_VIEW_RADIUS_METERS` | `50` | Raio de busca do panorama |

## Como a recomendação funciona

1. Busca até 50 restaurantes em um raio de 10 km via PostGIS.
2. Consulta scores no Redis (`reco:scores:{user_id}:{turno}`).
3. Em cache miss:
   - com modelo treinado **e** histórico do usuário: features por turno + LightGBM;
   - sem histórico (cold start): fallback por popularidade (nota + volume de avaliações).
4. Normaliza os scores para `[0, 1]`, grava no Redis com TTL de 24h e ordena os candidatos.
5. No grupo `personalized`, mistura a afinidade derivada das interações recentes
   (`blend_with_affinity`, `alpha=0.3`) para refletir o comportamento do usuário
   sem retreinar o modelo. O grupo de controle `distance` não recebe afinidade.

As features seguem a documentação: ticket médio, frete médio, contagem por turno e **medoide** aproximado por moda ponderada pela recência. O turno solicitado entra como one-hot (`is_manha`, `is_tarde`, ...), então o modelo aprende rankings diferentes por período. O treino avalia todos os restaurantes do catálogo como candidatos em cada contexto (sem amostragem `1:3`): o positivo é o pedido observado e os demais são negativos implícitos. Negativos com interação registrada antes do contexto recebem peso `1.0`; negativos não observados recebem peso `0.1`. O restaurante-alvo é removido do histórico para reduzir vazamento.

### Interações e perfil de preferências

O histórico comportamental fica na tabela `user_restaurant_interactions`
(append-only). Cada evento é registrado via `POST /api/v1/interactions`:

| Tipo | Peso |
|------|------|
| `IMPRESSION` | 0.0 (apenas exposição; base do CTR) |
| `VIEW` | 0.2 |
| `VIEW_DETAILS` | 0.4 |
| `CLICK` | 1.0 |
| `FAVORITE` | 2.5 |
| `PURCHASE` | 5.0 |
| `DISMISS` | 0.0 (tratado como sinal negativo separado) |

Os pesos decaem com a recência (meia-vida de 30 dias) e pedidos reais também
entram na afinidade de restaurante/categoria/cozinha. Cada interação aceita
`experiment_group`, `experiment_mode` (`experiment`/`demo`),
`experiment_version`, `recommendation_id`, `recommendation_position`,
`model_version` e `metadata` para atribuir o evento à exposição exibida.
`PURCHASE` só deve ser enviado na confirmação do pedido e aceita
`purchase_value`; o frontend usa `idempotency_key` para não duplicar a mesma
compra. Eventos com `experiment_mode='demo'` são gravados, mas excluídos das
métricas oficiais. As features do LightGBM passam a considerar contagens por
turno, afinidade por restaurante/categoria/cozinha e ticket médio; o perfil
agregado é exposto em `GET /api/v1/users/{id}/preferences`. Criar uma interação
invalida o cache de scores daquele usuário, então a próxima consulta já reflete
o novo histórico.

## Cardápios sintéticos e simulação de usuários

Nenhuma fonte aberta (OSM, Street View) publica cardápio. Para destravar o fluxo
de pedido e testar o recomendador sem APIs pagas, o backend inclui cardápios
sintéticos e um simulador de usuários. Tudo é **sintético**: os números medem o
modelo contra as regras do simulador, não contra pessoas reais.

### Cardápio e catálogo sintéticos

- `scripts/enrich_restaurants.py` cria itens plausíveis e determinísticos por
  restaurante, com `source='synthetic'`. O frontend os marca como “Exemplo”.
  `--fill-delivery` substitui apenas os valores neutros do OSM (frete `0` e
  prazo `20–30`). Reexecutar é idempotente: restaurantes que já têm cardápio são
  ignorados.
- `scripts/generate_synthetic_restaurants.py` gera um catálogo sintético (plano B
  ao OSM) com UUID determinístico por `(seed, centro, raio, índice)`; repetir o
  comando não duplica restaurantes. Cada registro guarda `simulation_run_id`.

### `scripts/simulate.py`

| Subcomando | O que faz |
|---|---|
| `backfill` | Gera histórico retroativo direto no banco com políticas `distance`, `popularity`, `random` ou `mixed`; eventos ficam com `experiment_mode='demo'` e fora das métricas oficiais. Bloqueia um `run_id` que já tenha eventos. |
| `live` | Agentes chamam `GET /recommendations` e `POST /interactions` de verdade, exercitando o A/B. Grava `sim_runs/<run-id>/live_sessions.jsonl`. |
| `report` | Compara grupos contra o oráculo, com `--by-persona`, `--by-cohort`, `--by-period` e `--require-unseen`. |
| `cleanup` | Remove usuários simulados e o que eles geraram; `--dry-run` só conta, `--include-restaurants` remove restaurantes sintéticos sem referências e todo run grava um JSON de auditoria. |

```bash
cd backend
python scripts/init_db.py                          # aplica até a migração 0006

python scripts/generate_synthetic_restaurants.py --count 150 --dry-run
python scripts/generate_synthetic_restaurants.py --count 150 --yes
python scripts/enrich_restaurants.py --fill-delivery --dry-run
python scripts/enrich_restaurants.py --fill-delivery --yes

python scripts/simulate.py backfill --users 300 --days 21 --run-id exp1 --yes
python -m app.ml.train --source db
python scripts/simulate.py live --run-id exp1 --rounds 5 --yes
python scripts/simulate.py live --run-id exp1-unseen --unseen-users --rounds 5 --yes
python scripts/simulate.py report --run-id exp1 --by-cohort --by-persona
python scripts/simulate.py cleanup --run-id exp1 --dry-run
```

### Segurança operacional

Os comandos que escrevem seguem o mesmo contrato:

- exibem o banco de destino antes de qualquer operação;
- `--dry-run` mostra o que mudaria e **não grava** (não exige `--yes`);
- sem `--yes` o script aborta;
- bancos de produção (ambiente `production`/`prod` ou nome com `prod`) são
  bloqueados;
- hosts remotos exigem `--allow-remote-db`.

Rode em um banco separado (`DATABASE_URL=.../foodflow_sim`): o treino lê todas
as linhas e dados simulados contaminariam um treino com usuários reais. Os logs
de sessão ficam em `backend/sim_runs/` (gitignored).

### Ordenação vs. seleção

- `ranking_quality_served` (NDCG@10): a API ordenou bem os restaurantes que
  mostrou? O ideal é calculado dentro da própria lista servida.
- `candidate_recall`: dos 10 melhores do universo elegível, quantos entraram na
  lista servida?
- `selection_coverage`: compras esperadas da lista servida ÷ compras esperadas
  do top-10 ideal, considerando **todos** os candidatos elegíveis (com viés de
  posição). `1.0` = seleção e ordenação perfeitas.

No modo `live`, o universo elegível (`nearby_candidates`, até 50 restaurantes em
10 km) é calculado **antes** de chamar a API. Usar a própria resposta como
universo mediria apenas a ordenação. Os ICs usam bootstrap de **usuários**, não
de sessões.

### Coortes e idempotência

- `--unseen-users` cria uma coorte `unseen` (offset de índice e `user_seed`
  separado), sem histórico no treino; `--require-unseen` falha se ela não
  existir.
- Pedidos, avaliações e restaurantes sintéticos guardam
  `simulation_run_id`/`simulation_mode`; interações guardam
  `metadata.sim_run`/`metadata.sim_mode`.
- Restrições alimentares não têm fallback: se nenhum item do cardápio atende à
  restrição do agente, a compra não acontece naquele restaurante.

Detalhes completos em [`docs/simulacao.md`](../docs/simulacao.md).

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

## Treino do LightGBM

```bash
cd backend
python -m app.ml.train --source db    # usa os pedidos do PostgreSQL
python -m app.ml.train --source seed  # seed determinístico, sem PostGIS
```

Flags opcionais:

```bash
python -m app.ml.train --source seed --strict-temporal --rolling-window
```

- `--strict-temporal`: exclui do treino/avaliação os atributos do restaurante
  lidos do estado atual (rating, nº de avaliações, frete e tempo de entrega),
  reduzindo risco de vazamento temporal.
- `--rolling-window`: adiciona avaliação walk-forward com múltiplas janelas
  expansíveis.

O artefato é salvo em `models/recommender.joblib` com metadados JSON (versão,
data, features e parâmetros). O relatório completo do treino é gravado em
`models/training_metrics.json` (**schema v3**) e exposto em
`GET /api/v1/ml/metrics`: alvo `purchased`, política de negativos, split
temporal, Precision@K, Recall@K, NDCG@K, MAP@K, ILD@K, novidade, cobertura,
ROC AUC/PR AUC/Brier/Log Loss, calibração com ECE, IC bootstrap por usuário,
sensibilidade a negativos observados/não observados, política temporal das
features, rolling-window opcional, baselines de popularidade/aleatório e
comparação com o modelo em produção. Se o modelo não existir ou não carregar, a
API usa o fallback por popularidade. Treine no mesmo ambiente da API: artefatos
gerados com NumPy 2.x não carregam em ambientes com NumPy 1.26 (`numpy._core`).

A promoção exige superar `max(melhor baseline, modelo em produção)` por uma
margem mínima em NDCG@K ou MAP@K, sem degradação relevante na outra métrica.
Se a produção não puder ser avaliada, a decisão é `insufficient_evidence`.
Treino `--source seed` é apenas avaliação e **não substitui** um modelo de
produção existente.

## Re-ranking LoRA (experimental)

Requer as dependências opcionais:

```bash
cd backend
pip install -r requirements-llmops.txt
python scripts/train_lora.py --source seed   # ou --source db
```

O adapter é salvo em `models/lora_reranker/` e só é carregado com
`ENABLE_LORA_RERANKER=true`. Sem dependências ou sem adapter real, o
serving usa o fallback determinístico. O endpoint
`POST /api/v1/recommendations/train-lora` apenas retorna `202`; o treino
deve ser executado offline.

Avaliação offline (split temporal, sem vazamento e sem sobrescrever o
adapter de serving):

```bash
python scripts/evaluate_lora.py --source seed
python scripts/evaluate_lora.py --source db --holdout-days 14
```

Com o seed e holdout de 7 dias, o LoRA ficou abaixo do LightGBM
(AUC 0.3574 / NDCG@5 0.2018 contra AUC 0.6727 / NDCG@5 0.5002). O
resultado se repete em janelas de 10 e 14 dias, então o LoRA permanece
experimental e **desabilitado por padrão**. O adapter publicado no
Hugging Face usa base Llama 3.2 1B, diferente do runtime MiniLM; alinhe
os dois antes de reutilizar o artefato.

A imagem Docker padrão instala apenas `requirements.txt`. Para usar LoRA
no container, faça um build com `requirements-llmops.txt` ou instale as
dependências no ambiente de serving.

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

A migração inicial (`0001`) cria a extensão PostGIS. A revisão `0002` adiciona os campos OSM em `restaurants` (`source`, `osm_type`, `osm_id`, `latitude`, `longitude`, `cuisine`, `website`, `opening_hours`, `osm_url`), a constraint única `(osm_type, osm_id)` e a tabela `user_restaurant_interactions` com índices por usuário/data. As revisões seguintes:

- `0003`: contexto experimental nas interações (`experiment_group`, `experiment_mode`, `experiment_version`, `recommendation_id`, posição, versão do modelo) e `last_synced_at`.
- `0004`: tabela `experiment_assignments` (atribuição persistente por usuário/versão).
- `0005`: tabela `menu_items` (cardápio por restaurante; `source='synthetic'` para itens de exemplo).
- `0006`: `simulation_run_id`/`simulation_mode` em restaurantes, pedidos e avaliações, além da tabela `recommendation_logs`.

Se a role do banco não for superusuária, crie a extensão antes como `postgres`:

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
```

Bancos que foram criados pela versão anterior (`Base.metadata.create_all`) não possuem `alembic_version`. O `init_db.py` detecta a tabela `restaurants` e executa `stamp head` uma única vez antes de aplicar as migrações.

## Observabilidade

Toda resposta inclui `X-Request-ID` (recebido ou gerado) e `X-Process-Time` em milissegundos. O middleware registra método, rota, status, latência e request id no log.

- `GET /health` é o liveness probe e informa se o modelo está carregado.
- `GET /ready` retorna `503` apenas se o PostgreSQL estiver indisponível; Redis e modelo são degradáveis (a API continua servindo com fallback).
- `GET /api/v1/metrics/recommendations` lê os contadores incrementados no Redis:
  - `requests`, `cache_hits`, `cache_misses`;
  - `model_scores` e `popularity_scores`;
  - `cache_hit_rate` calculado sobre o total de requisições.

As chaves ficam em `metrics:reco:*`. Se o Redis estiver fora, o endpoint responde com `redis_available: false` e zeros, sem derrubar a API.

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

Os testes cobrem feature engineering, contexto de turno, geração do dataset de treino, batch scoring, migrações Alembic (revisões `0001` a `0006`), métricas de ranking (P@K, R@K, NDCG, MAP, cobertura, ILD, novidade), split temporal por contexto, alvo `purchased`, pesos de negativos observados/não observados, métricas preditivas (ROC AUC, PR AUC, Brier, Log Loss) com disponibilidade independente, calibração (ECE), sensibilidade a negativos observados/não observados, política temporal e modo `--strict-temporal`, rolling-window, IC bootstrap por usuário, comparação com produção, promoção/rollback, readiness, round-trip do modelo, query PostGIS, persistência/detalhe de restaurantes OSM, ingestão por bbox, Street View (metadata/proxy e erros), interações e perfil de preferências, atribuição e métricas do experimento A/B (fases, coorte válida, exigência de baseline, bootstrap nulo sob H0, fallback z, Bonferroni, plano de amostra, contaminação e modo demo), simulação (dieta sem fallback, métricas de ordenação vs. seleção, guardas de escrita, UUID determinístico de restaurantes sintéticos e relatório por coorte/período), validação de schemas e contratos da API (sem depender de banco).

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
│   ├── crud.py                  # busca geoespacial, reviews, eventos, interações
│   ├── seeds.py                 # seed idempotente
│   ├── seed_data.py             # dados do seed
│   ├── services/
│   │   ├── restaurant_service.py # persistência/upsert e detalhe OSM
│   │   └── interactions.py       # registro de interações e perfil derivado
│   ├── integrations/
│   │   └── overpass_client.py    # consulta à Overpass API
│   ├── api/
│   │   ├── restaurants.py
│   │   ├── interactions.py      # interações + preferências
│   │   ├── reviews.py
│   │   ├── recommendations.py
│   │   ├── metrics.py          # contadores de cache/modelo
│   │   └── events.py
│   ├── cache/
│   │   └── redis_client.py      # scores, métricas e Redis Stream
│   ├── core/
│   │   ├── config.py
│   │   └── constants.py
│   ├── simulation/
│   │   ├── personas.py          # personas, turnos e amostragem de usuários
│   │   ├── behavior.py          # utilidade latente, funil e métricas
│   │   ├── menu_catalog.py      # cardápios sintéticos por arquétipo
│   │   ├── world.py             # catálogo do banco + usuários simulados
│   │   └── safety.py            # guardas de escrita (--yes, produção, host remoto)
│   └── ml/
│       ├── features.py          # features compartilhadas treino/serving
│       ├── recommender.py       # load/save + predict + fallback
│       ├── batch.py             # scoring em lote por usuário/turno
│       └── train.py             # dataset, treino e métricas
├── models/                      # artefatos .joblib (gitignored)
├── sim_runs/                    # logs de simulação (gitignored)
├── scripts/
│   ├── init_db.py               # migrações Alembic + seed
│   ├── ingest_osm.py            # ingestão por bbox via Overpass
│   ├── enrich_restaurants.py    # cardápio sintético + frete/prazo
│   ├── generate_synthetic_restaurants.py  # catálogo sintético
│   ├── simulate.py              # backfill, live, report e cleanup
│   └── batch_score.py           # CLI do batch scoring (cron/Task Scheduler)
└── tests/
```
