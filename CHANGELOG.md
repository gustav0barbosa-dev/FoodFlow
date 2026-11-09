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
- Endpoints `PUT /api/v1/reviews/{review_id}` e `DELETE /api/v1/reviews/{review_id}` no backend

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