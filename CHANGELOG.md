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
- `package.json` raiz com scripts delegados
- `CHANGELOG.md`
- Batch scoring diário (`scripts/batch_score.py`) por usuário/turno com gravação no Redis
- Migrações Alembic com schema inicial, comando `db:migrate` e baseline automático (`stamp head`) para bancos legados
- Serviço `batch-scorer` no Docker Compose (profile `batch`) e scripts `batch:score`/`batch-score`
- Endpoint `POST /api/v1/reviews` com `Idempotency-Key` e atualização transacional dos agregados
- Detalhe do restaurante com as últimas 10 avaliações
- Seed idempotente com 12 restaurantes, 4 usuários, 30 pedidos e 36 avaliações
- Cache Redis com degradação graciosa, invalidação após treino e Redis Stream de eventos
- Carregamento do modelo LightGBM no lifespan da API
- Dataset de treino com `1 positivo : 3 negativos` e features leave-one-restaurant-out
- 45 testes de backend (pytest) cobrindo features, contexto de turno, treino, batch scoring, migrações, modelo, PostGIS, schemas e API
- `requirements-dev.txt`, `pytest.ini` e scripts `build`/`test` do backend

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