# Changelog

Todas as mudanças notáveis deste projeto seguem [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [Unreleased]

### Alterado
- Reorganização do repositório em monorepo: frontend movido para `frontend/`, documentação para `docs/`
- Recomendador passou a compartilhar o mesmo feature engineering entre treino e serving, com scores normalizados em `[0, 1]`
- Modelo passou a receber o turno solicitado como one-hot (`is_manha`, `is_tarde`, `is_noite`, `is_madrugada`)
- Treino gera amostras por turno, com `1 positivo : 3 negativos` em cada contexto
- API usa o modelo apenas quando o usuário tem histórico no turno; caso contrário aplica popularidade
- `scripts/init_db.py` agora aplica migrações Alembic em vez de `create_all` + DDL incremental
- Busca geoespacial agora calcula distância na mesma query (sem N+1) e usa binds nomeados
- CORS passou a ler `CORS_ORIGINS` das configurações
- README raiz e `backend/README.md` atualizados com o estado real do backend

### Adicionado
- Integração frontend ↔ API FastAPI:
  - `frontend/src/lib/api.ts`: cliente HTTP tipado com timeout, fallback e `ApiError`
  - `frontend/src/lib/config.ts`: `VITE_API_URL`, `VITE_USER_ID`, coordenadas padrão, derivação de turno
  - `frontend/src/lib/catalog.ts`: mapeamento API → tipos do frontend, enriquecimento com mock
  - `frontend/src/store/catalogStore.ts`: catálogo via API com fallback para mock
  - `frontend/src/store/locationStore.ts`: localização persistida (geolocalização ou Osasco/SP padrão)
  - `frontend/src/hooks/useCatalog.ts`, `useRecommendations.ts`, `useRestaurantSearch.ts`
  - `frontend/src/store/favoritesStore.ts`: migração de IDs mock → UUIDs da API
  - `frontend/src/store/eventsStore.ts`: `trackEvent` envia `POST /events` (best-effort)
  - `frontend/src/store/reviewsStore.ts`: `saveReview` sincroniza avaliações locais com a API
  - `frontend/src/pages/Home.tsx`, `Search.tsx`, `Favorites.tsx`, `RestaurantDetail.tsx`, `Onboarding.tsx`
  - `frontend/src/components/restaurant/UserReviewForm.tsx`: create/update/delete via API
  - `frontend/.env.example` e `src/vite-env.d.ts`: variáveis de ambiente e types do Vite
- Testes novos: `src/lib/api.test.ts` (7), `src/lib/catalog.test.ts` (8), `src/lib/config.test.ts` (5)
- 132 testes do frontend passando; build de produção OK
- Monitoramento de drift do recomendador:
  - `backend/app/services/drift.py`: `DriftMonitor` com PSI (Population Stability Index) para comparar distribuições de treino (baseline) vs serving; thresholds de warning (0.1) e alerta (0.2); degradação graciosa sem Redis
  - `backend/app/api/drift.py`: endpoint `GET /api/v1/drift` com relatório de drift por feature
  - `backend/app/ml/train.py`: salva a distribuição de treino como baseline após cada treino
  - `backend/app/ml/recommender.py`: registra features usadas em serving para cálculo de drift
  - `backend/scripts/drift_detect.py`: script CLI para detecção periódica de drift (cron/Task Scheduler)
  - `backend/scripts/drift_detect.py` adicionado ao `package.json` como `drift-detect`
- Testes novos: `tests/test_drift_monitor.py` (monitor de drift), `tests/test_drift.py` (compute_psi com seed fixo)
- Responsividade refinada para telas maiores:
  - `frontend/src/components/layout/MobileFrame.tsx`: moldura de celular com largura responsiva (430px mobile, 640px tablet, 820px desktop), altura limitada a 92vh em telas maiores
  - `frontend/src/components/layout/BottomNav.tsx`: bottom nav absoluto em mobile, não-absolute com fundo sutil e espaçamento em tablet/desktop
  - `frontend/src/components/restaurant/RestaurantCard.tsx`: suporte a `className` para controle de largura em grids responsivos
  - `frontend/src/pages/Home.tsx`: recomendados em grid 2-3 colunas (sm+/lg+), "Perto de você" em grid 2 colunas (sm+)
  - `frontend/src/pages/RestaurantDetail.tsx`: container com largura limitada (700px), cardápio em grid 2 colunas (sm+)
  - `frontend/src/pages/Search.tsx`, `Favorites.tsx`, `Orders.tsx`, `Profile.tsx`, `OrderDetail.tsx`: containers com largura limitada em telas maiores
  - `frontend/src/pages/Onboarding.tsx`: largura limitada (sm:max-w-md)
- LLMOps — re-ranking com LoRA e publicação Hugging Face:
  - `backend/app/ml/reranker.py`: `LoRAReranker` com fallback determinístico quando `transformers`/`peft`/`torch` não estão instalados; integra ao pipeline `/recommendations` após o LightGBM
  - `backend/scripts/train_lora.py`: fine-tuning LoRA sobre dataset sintético (usuário × restaurante × turno) gerado a partir dos pedidos do banco; gera artefato placeholder sem dependências de LLM
  - `backend/scripts/publish_lora.py`: publicação do adapter no Hugging Face Hub com instruções manuais
  - `backend/app/api/recommendations.py`: endpoints `POST /api/v1/recommendations/train-lora` e `POST /api/v1/recommendations/rerank`; re-ranking aplicado automaticamente nos scores do LightGBM
  - `backend/requirements-llmops.txt`: dependências opcionais (transformers, peft, torch, huggingface_hub, safetensors)
  - `backend/scripts/drift_detect.py` adicionado ao `package.json` como `drift-detect`
- Testes novos: `tests/test_reranker.py` (fallback, normalização, bônus por turno, instância global)
- Deploy de produção:
  - `backend/Dockerfile.prod`: imagem otimizada para produção (sem `--reload`, código empacotado)
  - `docker-compose.prod.yml`: compose de produção (usa `Dockerfile.prod`, variáveis de ambiente via `.env`)
  - `backend/.env.example`: variáveis de ambiente do backend (`DATABASE_URL`, `REDIS_URL`, `CORS_ORIGINS`)
  - `frontend/.env.example`: documentação de `VITE_API_URL` para desenvolvimento e produção
  - Healthcheck do backend no `docker-compose.yml` (endpoint `/ready`)
  - Endpoint `/api/v1/metrics` no formato Prometheus para scraping
- Experimento A/B de recomendações:
  - `backend/app/api/recommendations.py`: parâmetro `experiment` (`personalized`/`distance`) no endpoint `/recommendations`; atribuição determinística por hash do `user_id` quando omitido; métricas separadas por grupo (`metrics:ab:personalized:requests`, `metrics:ab:distance:requests`)
  - `backend/app/api/experiment.py`: endpoint `GET /api/v1/experiment/ab-test` com resultados acumulados (total, por grupo, share)
  - `backend/app/cache/redis_client.py`: funções `increment_ab_test_metrics` e `get_ab_test_metrics`
  - `frontend/src/lib/config.ts`: tipo `ABGroup`, `DEFAULT_AB_GROUP`, `getABGroup()`, variável `VITE_AB_GROUP`
  - `frontend/src/lib/api.ts`: parâmetro `experiment` em `getRecommendations`; função `getABTestResults`
  - `frontend/src/hooks/useRecommendations.ts`: passa o grupo A/B para a API; retorna `experimentGroup`
  - `frontend/src/pages/Home.tsx`: exibe o grupo A/B ativo na seção de recomendados
  - `frontend/src/pages/Profile.tsx`: seletor de grupo A/B (padrão/personalizado/distância) e painel de resultados acumulados
  - `frontend/.env.example`: variável `VITE_AB_GROUP`
- Aplicativo móvel React Native + Expo (`mobile/`):
  - `mobile/app.json`: configuração do app (nome FoodFlow, ícone, splash, plugins expo-router/expo-localization/expo-font)
  - `mobile/src/app/index.tsx`: tela de Onboarding com geolocalização via `expo-location`
  - `mobile/src/app/(tabs)/_layout.tsx`: navegação por abas com Expo Router (Início, Buscar, Pedidos, Perfil)
  - `mobile/src/app/(tabs)/index.tsx`: tela Home com recomendados, "Perto de você", busca e carrinho
  - `mobile/src/app/(tabs)/buscar.tsx`: tela Buscar com buscas recentes e resultados
  - `mobile/src/app/(tabs)/pedidos.tsx`: tela Pedidos com histórico
  - `mobile/src/app/(tabs)/perfil.tsx`: tela Perfil com preferências e experimento A/B
  - `mobile/src/app/restaurante/[id].tsx`: tela Detalhe do Restaurante com cardápio e informações
  - `mobile/src/app/sacola.tsx`: tela Sacola com itens, grupos por restaurante e finalização
  - `mobile/src/app/favoritos.tsx`: tela Favoritos (via tab)
  - `mobile/src/lib/api.ts`: cliente HTTP tipado com todos os endpoints da API
  - `mobile/src/lib/config.ts`: configuração com variáveis `EXPO_PUBLIC_*`
  - `mobile/src/lib/catalog.ts`: mapeamento API → tipos do frontend
  - `mobile/src/lib/dietary.ts`, `mobile/src/lib/search.ts`, `mobile/src/lib/format.ts`, `mobile/src/lib/events.ts`, `mobile/src/lib/utils.ts`: utilitários
  - `mobile/src/store/`: Zustand stores (catalog, cart, favorites, location, orders, preferences, reviews, events, address)
  - `mobile/src/data/mockData.ts`: 12 restaurantes com cardápio e avaliações
  - `mobile/src/types/index.ts`: tipos TypeScript compartilhados

### Corrigido
- `NameError` no endpoint de detalhe por falta de import de `UUID`
- `NameError` no treino por falta de imports de `pandas` e `LGBMClassifier`
- Incompatibilidade de features entre treino e inferência
- Validação de `turno` e de tipos de evento via `Literal`
- Mutável padrão em `EventIn.payload`

## [0.1.0-frontend] — 2026-11-08

### Adicionado
- Frontend MVP completo do FoodFlow (React + TypeScript + Tailwind)
- 6 telas: Onboarding, Home, Buscar, Detalhe do Restaurante, Pedidos, Perfil
- Página de Sacola (carrinho) com confirmação de pedido
- Sistema de favoritos e avaliações editáveis pelo usuário
- Filtro de raio (1/3/5/10 km) na seção "Perto de você"
- Paginação em "Recomendados" com botão "Carregar mais"
- Persistência de filtros (busca, status de pedidos, ordenação) via Zustand
- Painel de eventos e estatísticas de perfil
- 26 arquivos de teste, 109 testes passando