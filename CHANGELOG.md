# Changelog

Todas as mudanças notáveis deste projeto seguem [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [Unreleased]

### Alterado
- Reorganização do repositório em monorepo: frontend movido para `frontend/`, documentação para `docs/`

### Adicionado
- `package.json` raiz com scripts delegados
- `CHANGELOG.md`

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